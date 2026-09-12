from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from autoflow.domain.profiles.models import Profile, ProfileBrowserProxy
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import PreparedWorkflow
from autoflow.infrastructure.process.browser_processes import process_birth
from autoflow.infrastructure.process.test_browser_worker import (
    DEFAULT_START_TIMEOUT,
    DEFAULT_TERMINATION_TIMEOUT,
    _process_group_options,
    _wait_for_spawn,
    _worker_payload,
    stop_process_tree,
)


def workflow_worker_command() -> tuple[str, ...]:
    if getattr(sys, "frozen", False):
        return (sys.executable, "--workflow-worker")
    return (sys.executable, "-m", "autoflow", "--workflow-worker")


def _failed(code: str = "workflow_worker_failed", message: str = "工作流执行进程失败") -> dict[str, Any]:
    return {"state": "failed", "error": {
        "code": code, "message": message, "nodeId": None, "path": [],
    }}


class WorkflowWorkerManager:
    def __init__(
        self, temp_root: Path, runs_root: Path, *,
        command: tuple[str, ...] | None = None,
        worker_env: dict[str, str] | None = None,
        start_timeout: float = DEFAULT_START_TIMEOUT,
        termination_timeout: float = DEFAULT_TERMINATION_TIMEOUT,
    ) -> None:
        self._root = temp_root.resolve() / "workflow-workers" / uuid4().hex
        self._runs_root = runs_root.resolve()
        self._command = command or workflow_worker_command()
        self._worker_env = worker_env or {}
        self._start_timeout, self._termination_timeout = start_timeout, termination_timeout
        self._tasks: dict[str, asyncio.Task[dict[str, Any]]] = {}
        self._stopping: set[str] = set()
        self._started: set[str] = set()
        self._shutting_down = False
        self._pending_cleanup: dict[str, tuple[asyncio.subprocess.Process, Path, Path, int | None]] = {}

    async def execute(
        self, run_id: str, prepared: PreparedWorkflow, profile: Profile,
        executable: Path, proxy: ProfileBrowserProxy | None, license_key: str | None,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> dict[str, Any]:
        if self._shutting_down or self.busy():
            raise WorkflowError("workflow_worker_busy", "工作流执行器正在使用中", 409)
        if not run_id or run_id in {".", ".."} or "/" in run_id or "\\" in run_id:
            raise WorkflowError("workflow_run_id_invalid", "运行标识无效", 422)
        task = asyncio.create_task(
            self._execute(run_id, prepared, profile, executable, proxy, license_key, on_event),
            name=f"workflow-worker-{run_id}",
        )
        self._tasks[run_id] = task
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            self._cancel(run_id)
            return await self._wait_cleanup(task)

    async def stop(self, run_id: str) -> None:
        task = self._tasks.get(run_id)
        if task is None:
            return
        if task.done() and run_id in self._pending_cleanup:
            self._stopping.add(run_id)
            task = asyncio.create_task(self._retry_cleanup(run_id))
            self._tasks[run_id] = task
        else:
            self._cancel(run_id)
        await self._wait_cleanup(task)

    async def _retry_cleanup(self, run_id: str) -> dict[str, Any]:
        process, directory, executable, birth = self._pending_cleanup[run_id]
        try:
            await stop_process_tree(process, self._termination_timeout, directory, executable, birth)
        except Exception:  # noqa: BLE001 -- retain cleanup ownership and expose only a safe retryable error.
            raise WorkflowError("WORKFLOW_CLEANUP_FAILED", "浏览器清理尚未完成，请重试停止", 503) from None
        self._pending_cleanup.pop(run_id, None)
        shutil.rmtree(directory, ignore_errors=True)
        self._stopping.discard(run_id)
        self._started.discard(run_id)
        self._tasks.pop(run_id, None)
        return {"state": "cancelled", "error": None}

    async def shutdown(self) -> None:
        self._shutting_down = True
        for run_id in tuple(self._tasks):
            await self.stop(run_id)
        shutil.rmtree(self._root, ignore_errors=True)

    def busy(self) -> bool:
        return bool(self._tasks)

    def _cancel(self, run_id: str) -> None:
        if run_id not in self._stopping and run_id in self._tasks:
            self._stopping.add(run_id)
            if run_id in self._started:
                self._tasks[run_id].cancel()

    @staticmethod
    async def _wait_cleanup(task: asyncio.Task[Any]) -> Any:
        # Repeated cancellation must not release the caller's resource locks early.
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        return task.result()

    async def _execute(
        self, run_id: str, prepared: PreparedWorkflow, profile: Profile,
        executable: Path, proxy: ProfileBrowserProxy | None, license_key: str | None,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> dict[str, Any]:
        process: asyncio.subprocess.Process | None = None
        birth = None
        directory = self._root / run_id
        result = _failed()
        self._started.add(run_id)
        try:
            if run_id in self._stopping:
                raise asyncio.CancelledError
            directory.mkdir(parents=True, exist_ok=False)
            env = {**os.environ, **self._worker_env}
            env.pop("CLOAKBROWSER_LICENSE_KEY", None)
            env.update({
                "CLOAKBROWSER_BINARY_PATH": str(executable.resolve(strict=True)),
                "CLOAKBROWSER_CACHE_DIR": str(directory),
                "TMPDIR": str(directory), "TMP": str(directory), "TEMP": str(directory),
            })
            spawn = asyncio.create_task(asyncio.create_subprocess_exec(
                *self._command, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                env=env, limit=64 * 1024, **_process_group_options(),
            ))
            try:
                process = await asyncio.shield(spawn)
                birth = process_birth(process.pid) if sys.platform != "win32" else None
            except asyncio.CancelledError:
                process = await _wait_for_spawn(spawn)
                birth = process_birth(process.pid) if sys.platform != "win32" else None
                raise
            assert process.stdin is not None and process.stdout is not None
            payload = _worker_payload(run_id, profile, proxy, license_key)
            payload.pop("startUrl")
            payload.update({
                "runId": run_id, "headless": profile.spec.headless,
                "document": prepared.document, "nodeIds": prepared.node_ids,
                "variables": prepared.variables, "runsRoot": str(self._runs_root),
            })
            process.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode())
            await asyncio.wait_for(process.stdin.drain(), timeout=self._start_timeout)
            # Parent watchdog also covers a wedged driver. Each node enforces its precise
            # total budget inside the worker; the parent allows bounded event/IO overhead.
            read_timeout = self._start_timeout
            nodes = {node["id"]: node for node in prepared.document["nodes"]}
            while True:
                raw = await asyncio.wait_for(process.stdout.readline(), timeout=read_timeout)
                if not raw:
                    break
                event = json.loads(raw)
                if not isinstance(event, dict):
                    raise TypeError("Invalid worker event")
                if event.get("type") == "finished":
                    if event.get("state") not in {"succeeded", "failed", "cancelled"}:
                        raise ValueError("Invalid worker result")
                    result = {"state": event["state"], "error": event.get("error")}
                    break
                if event.get("type") not in {"ready", "node_started", "node_succeeded", "node_failed", "log"}:
                    raise ValueError("Invalid worker event")
                if event["type"] == "node_started":
                    node = nodes[event["nodeId"]]
                    read_timeout = float(node["config"]["timeoutSeconds"]) + self._termination_timeout + 1
                else:
                    read_timeout = self._start_timeout
                await on_event(event)
        except asyncio.CancelledError:
            result = {"state": "cancelled", "error": None}
        except TimeoutError:
            result = _failed("workflow_worker_timeout", "工作流执行进程响应超时")
        except Exception:  # noqa: BLE001 -- raw subprocess, browser and secret errors stay private.
            result = _failed()
        finally:
            if process is not None:
                self._pending_cleanup[run_id] = (process, directory, executable, birth)
                cleanup = asyncio.create_task(stop_process_tree(process, self._termination_timeout, directory, executable, birth))
                try:
                    await self._wait_cleanup(cleanup)
                except Exception:  # noqa: BLE001 -- a failed cleanup is not a terminal run.
                    raise WorkflowError("WORKFLOW_CLEANUP_FAILED", "浏览器清理尚未完成，请重试停止", 503) from None
                self._pending_cleanup.pop(run_id, None)
            shutil.rmtree(directory, ignore_errors=True)
            if run_id in self._stopping:
                result = {"state": "cancelled", "error": None}
            self._stopping.discard(run_id)
            self._started.discard(run_id)
            self._tasks.pop(run_id, None)
        return result
