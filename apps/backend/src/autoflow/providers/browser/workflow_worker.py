from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, TextIO

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.domain.workflows.runs import WorkflowArtifact
from autoflow.infrastructure.filesystem.workflow_artifacts import WorkflowArtifactStore

from .workflow_session import launch_workflow_session


def run_workflow_worker(
    stopped: Event, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout
) -> int:
    try:
        command = _read_command(stdin)
        Thread(target=_watch_stdin, args=(stdin, stopped), daemon=True).start()
        return asyncio.run(_run(command, stopped, stdout))
    except BaseException:  # noqa: BLE001 -- secrets and browser details stay isolated.
        _write(stdout, {"type": "error", "error": "Workflow worker failed"})
        return 1


async def _run(command: dict[str, Any], stopped: Event, stdout: TextIO) -> int:
    executable = Path(_required_environment("CLOAKBROWSER_BINARY_PATH"))
    cache = Path(_required_environment("CLOAKBROWSER_CACHE_DIR"))
    if not executable.is_absolute() or not executable.is_file() or not cache.is_absolute():
        raise ValueError("workflow worker paths are invalid")
    run_id = _required_string(command, "runId")
    profile_id = _required_string(command, "profileId")
    async with launch_workflow_session(command) as browser:
        _write(stdout, {"type": "ready", "runId": run_id, "profileId": profile_id})
        document = command.get("document")
        if isinstance(document, dict):
            workflow_id = _required_string(command, "workflowId")
            artifact_root = Path(_required_string(command, "artifactRoot"))
            if not artifact_root.is_absolute():
                raise ValueError("artifactRoot must be absolute")
            artifacts = _WorkerArtifactRepository(stdout)
            context = ExecutionContext(
                variables=_initial_variables(document),
                browser=browser,
                cancellation=_ThreadCancellation(stopped),
            )
            sink = _WorkerEventSink(
                stdout,
                run_id=run_id,
                workflow_id=workflow_id,
                context=context,
                artifacts=artifacts,
                artifact_root=artifact_root,
            )
            context.events = sink
            result = await WorkflowRuntime(
                build_production_executor_registry()
            ).execute(document, context)
            terminal = "execution:completed" if result.success else "execution:failed"
            _write(
                stdout,
                {
                    "type": terminal,
                    "runId": run_id,
                    "workflowId": workflow_id,
                    "executedNodes": len(result.executed_node_ids),
                    "failedNodeId": result.failed_node_id,
                    "issues": [
                        {
                            "nodeId": issue.node_id,
                            "path": issue.path,
                            "code": issue.code,
                            "message": issue.message,
                        }
                        for issue in result.issues
                    ],
                    "error": result.node_result.error if result.node_result else None,
                },
            )
            return 0 if result.success else 2
        while not stopped.is_set():
            await asyncio.sleep(0.05)
    return 0


class _ThreadCancellation:
    def __init__(self, stopped: Event) -> None:
        self._stopped = stopped

    @property
    def cancelled(self) -> bool:
        return self._stopped.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise RuntimeError("workflow execution stopped")


class _WorkerArtifactRepository:
    def __init__(self, stdout: TextIO) -> None:
        self._stdout = stdout
        self._lock = Lock()
        self._ordinal = 0
        self._by_execution: dict[str, list[str]] = {}

    def register_artifact(
        self,
        *,
        run_id: str,
        artifact_id: str,
        node_id: str,
        execution_id: str | None,
        relative_path: str,
        size: int,
        sha256: str,
        mime_type: str,
        purpose: str,
    ) -> WorkflowArtifact:
        with self._lock:
            self._ordinal += 1
            if execution_id:
                self._by_execution.setdefault(execution_id, []).append(artifact_id)
            _write(
                self._stdout,
                {
                    "type": "artifact:registered",
                    "runId": run_id,
                    "artifactId": artifact_id,
                    "nodeId": node_id,
                    "executionId": execution_id,
                    "relativePath": relative_path,
                    "size": size,
                    "sha256": sha256,
                    "mimeType": mime_type,
                    "purpose": purpose,
                },
            )
            return WorkflowArtifact(
                run_id=run_id,
                artifact_id=artifact_id,
                ordinal=self._ordinal,
                node_id=node_id,
                execution_id=execution_id,
                relative_path=relative_path,
                size=size,
                sha256=sha256,
                mime_type=mime_type,
                purpose=purpose,
                event_sequence=0,
            )

    def take(self, execution_id: str) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._by_execution.pop(execution_id, ()))


class _WorkerEventSink:
    def __init__(
        self,
        stdout: TextIO,
        *,
        run_id: str,
        workflow_id: str,
        context: ExecutionContext,
        artifacts: _WorkerArtifactRepository,
        artifact_root: Path,
    ) -> None:
        self._stdout = stdout
        self._run_id = run_id
        self._workflow_id = workflow_id
        self._context = context
        self._artifacts = artifacts
        self._artifact_root = artifact_root

    async def publish(self, event: Mapping[str, Any]) -> None:
        event = dict(event)
        node_id = event.get("nodeId")
        execution_id = event.get("executionId")
        if isinstance(node_id, str) and isinstance(execution_id, str):
            self._context.current_node_id = node_id
            self._context.current_execution_id = execution_id
            if event.get("type") == "execution:node_start":
                self._context.artifacts = WorkflowArtifactStore(
                    self._artifact_root,
                    self._artifacts,
                ).writer(
                    run_id=self._run_id,
                    node_id=node_id,
                    execution_id=execution_id,
                    purpose="result",
                )
            elif event.get("type") == "execution:node_complete":
                event["artifactIds"] = list(self._artifacts.take(execution_id))
        _write(
            self._stdout,
            {
                **event,
                "runId": self._run_id,
                "workflowId": self._workflow_id,
            },
        )


def _initial_variables(document: dict[str, Any]) -> dict[str, Any]:
    variables = document.get("variables", [])
    if not isinstance(variables, list):
        return {}
    return {
        item["name"]: item.get("value")
        for item in variables
        if isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and item["name"]
    }


def _read_command(stdin: TextIO) -> dict[str, Any]:
    raw = stdin.readline()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError("workflow worker command must be an object")
    return value


def _watch_stdin(stdin: TextIO, stopped: Event) -> None:
    stdin.read()
    stopped.set()


def _required_string(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{key} must be a string")
    return value


def _required_environment(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise TypeError(f"{key} must be a string")
    return value


def _write(stdout: TextIO, event: dict[str, object]) -> None:
    stdout.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    stdout.flush()
