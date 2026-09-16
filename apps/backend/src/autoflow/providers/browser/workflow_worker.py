from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, TextIO
from uuid import uuid4

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext, InputPromptRequest
from autoflow.domain.workflows.runs import WorkflowArtifact
from autoflow.infrastructure.filesystem.workflow_artifacts import WorkflowArtifactStore
from autoflow.infrastructure.filesystem.workflow_table_workbook import (
    OpenpyxlTableWorkbookRenderer,
)

from .workflow_session import launch_workflow_session

_MAX_INLINE_RESULT_BYTES = 64 * 1024


def run_workflow_worker(
    stopped: Event, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout
) -> int:
    try:
        command = _read_command(stdin)
        return asyncio.run(_run(command, stopped, stdout, stdin))
    except BaseException:  # noqa: BLE001 -- secrets and browser details stay isolated.
        _write(stdout, {"type": "error", "error": "Workflow worker failed"})
        return 1


async def _run(
    command: dict[str, Any],
    stopped: Event,
    stdout: TextIO,
    stdin: TextIO | None = None,
) -> int:
    command_bus = _WorkerCommandBus(
        asyncio.get_running_loop(), stopped, stdout, command
    )
    if stdin is not None:
        Thread(
            target=_watch_stdin,
            args=(stdin, stopped, command_bus.receive, command_bus.close),
            daemon=True,
        ).start()
    requires_browser = command.get("requiresBrowser", True)
    if not isinstance(requires_browser, bool):
        raise TypeError("requiresBrowser must be a boolean")
    _required_string(command, "runId")
    _required_string(command, "profileId")
    if not requires_browser:
        return await _run_in_session(command, stopped, stdout, None, command_bus)
    executable = Path(_required_environment("CLOAKBROWSER_BINARY_PATH"))
    cache = Path(_required_environment("CLOAKBROWSER_CACHE_DIR"))
    if (
        not executable.is_absolute()
        or not executable.is_file()
        or not cache.is_absolute()
    ):
        raise ValueError("workflow worker paths are invalid")
    async with launch_workflow_session(command) as browser:
        return await _run_in_session(command, stopped, stdout, browser, command_bus)


async def _run_in_session(
    command: dict[str, Any],
    stopped: Event,
    stdout: TextIO,
    browser: Any,
    command_bus: _WorkerCommandBus,
) -> int:
    run_id = _required_string(command, "runId")
    profile_id = _required_string(command, "profileId")
    ready: dict[str, Any] = {
        "type": "ready",
        "runId": run_id,
        "profileId": profile_id,
    }
    child_pid = getattr(browser, "browser_pid", None)
    if isinstance(child_pid, int):
        ready["childPid"] = child_pid
    _write(stdout, ready)
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
            table_workbooks=OpenpyxlTableWorkbookRenderer(),
            input_prompts=command_bus,
        )
        command_bus.bind_context(context)
        sink = _WorkerEventSink(
            stdout,
            run_id=run_id,
            workflow_id=workflow_id,
            context=context,
            artifacts=artifacts,
            artifact_root=artifact_root,
        )
        context.events = sink
        result = await WorkflowRuntime(build_production_executor_registry()).execute(
            document, context
        )
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
            raise asyncio.CancelledError


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
                    cancellation=self._context.cancellation,
                )
            elif event.get("type") == "execution:node_complete":
                await self._externalize_large_result(event, execution_id)
                event["artifactIds"] = list(self._artifacts.take(execution_id))
        _write(
            self._stdout,
            {
                **event,
                "runId": self._run_id,
                "workflowId": self._workflow_id,
            },
        )

    async def _externalize_large_result(
        self, event: dict[str, Any], execution_id: str
    ) -> None:
        value = event.get("data")
        if value is None:
            return
        encoded = json.dumps(
            value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
        if len(encoded) <= _MAX_INLINE_RESULT_BYTES:
            return
        writer = self._context.artifacts
        if writer is None:
            raise RuntimeError("节点大结果缺少产物写入器")
        await writer.write_bytes(
            name=f"node-results/{execution_id}.json",
            content=encoded,
            mime_type="application/json",
        )
        event["data"] = {
            "externalized": True,
            "mimeType": "application/json",
            "size": len(encoded),
        }


def _initial_variables(document: dict[str, Any]) -> dict[str, Any]:
    variables = document.get("variables", [])
    if not isinstance(variables, list):
        return {}
    return {
        item["name"]: item.get("value")
        for item in variables
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"]
    }


def _read_command(stdin: TextIO) -> dict[str, Any]:
    raw = stdin.readline()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError("workflow worker command must be an object")
    return value


class _WorkerCommandBus:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        stopped: Event,
        stdout: TextIO,
        command: dict[str, Any],
    ) -> None:
        self._loop = loop
        self._stopped = stopped
        self._stdout = stdout
        self._run_id = _required_string(command, "runId")
        workflow_id = command.get("workflowId")
        self._workflow_id = workflow_id if isinstance(workflow_id, str) else ""
        self._context: ExecutionContext | None = None
        self._pending: dict[str, asyncio.Future[str | None]] = {}

    def bind_context(self, context: ExecutionContext) -> None:
        self._context = context

    def receive(self, command: dict[str, Any]) -> None:
        if not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._apply, command)

    def close(self) -> None:
        if not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._cancel_pending)

    async def request_input(
        self, request: InputPromptRequest, *, timeout_seconds: float
    ) -> str | None:
        context = self._context
        if context is None:
            raise RuntimeError("输入请求上下文尚未就绪")
        request_id = str(uuid4())
        future: asyncio.Future[str | None] = self._loop.create_future()
        self._pending[request_id] = future
        await _publish_prompt(context, request_id, request)
        status = "expired"
        try:
            value = (
                await asyncio.wait_for(future, timeout_seconds)
                if timeout_seconds > 0
                else await future
            )
            status = "cancelled" if value is None else "answered"
            return value
        finally:
            self._pending.pop(request_id, None)
            if context.events is not None:
                await context.events.publish(
                    {
                        "type": "execution:input_prompt_closed",
                        "requestId": request_id,
                        "nodeId": context.current_node_id,
                        "executionId": context.current_execution_id,
                        "status": status,
                    }
                )

    def _apply(self, command: dict[str, Any]) -> None:
        if command.get("type") != "input_prompt_result":
            return
        request_id = command.get("requestId")
        command_id = command.get("commandId")
        value = command.get("value")
        future = self._pending.get(request_id) if isinstance(request_id, str) else None
        if future is None or future.done() or not isinstance(command_id, str):
            return
        if value is not None and not isinstance(value, str):
            return
        future.set_result(value)
        _write(
            self._stdout,
            {
                "type": "execution:command_applied",
                "runId": self._run_id,
                "workflowId": self._workflow_id,
                "commandId": command_id,
                "requestId": request_id,
            },
        )

    def _cancel_pending(self) -> None:
        for future in self._pending.values():
            if not future.done():
                future.cancel()


async def _publish_prompt(
    context: ExecutionContext, request_id: str, request: InputPromptRequest
) -> None:
    if context.events is None:
        raise RuntimeError("输入请求事件服务不可用")
    await context.events.publish(
        {
            "type": "execution:input_prompt",
            "requestId": request_id,
            "nodeId": context.current_node_id,
            "executionId": context.current_execution_id,
            "variableName": request.variable_name,
            "title": request.title,
            "message": request.message,
            "defaultValue": request.default_value,
            "inputMode": request.input_mode,
            "minValue": request.min_value,
            "maxValue": request.max_value,
            "maxLength": request.max_length,
            "required": request.required,
            "selectOptions": list(request.select_options)
            if request.select_options is not None
            else None,
        }
    )


def _watch_stdin(
    stdin: TextIO,
    stopped: Event,
    receive: Any,
    close: Any,
) -> None:
    try:
        while raw := stdin.readline():
            try:
                command = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(command, dict):
                receive(command)
    finally:
        stopped.set()
        close()


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
