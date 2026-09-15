from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack
from dataclasses import dataclass
from inspect import isawaitable
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from autoflow.domain.kernels.models import KernelRef
from autoflow.domain.workflows.browser import WorkflowBrowserBusy, WorkflowWorkerSession
from autoflow.infrastructure.filesystem.kernel_installations import kernel_target_lock
from autoflow.infrastructure.filesystem.locking import ExclusiveFileLock
from autoflow.infrastructure.process.browser_processes import process_birth
from autoflow.infrastructure.process.test_browser_worker import stop_process_tree

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")


class WorkflowWorkerBusy(RuntimeError):
    pass


class ProfileGuard(Protocol):
    def guard(self, profile_id: str) -> AbstractContextManager[None]: ...


class WorkflowResourceCoordinator:
    def __init__(self, profile_guard: ProfileGuard, kernels_root: Path) -> None:
        self._profile_guard = profile_guard
        self._kernels_root = kernels_root
        self._owner_id: str | None = None
        self._stack: ExitStack | None = None
        self._lock = asyncio.Lock()

    @property
    def owner_id(self) -> str | None:
        return self._owner_id

    async def acquire(
        self, owner_id: str, profile_id: str, kernel: KernelRef
    ) -> None:
        async with self._lock:
            if self._owner_id is not None:
                raise WorkflowBrowserBusy("当前工作区已有活跃浏览器会话")
            stack = ExitStack()
            try:
                workspace_lock = ExclusiveFileLock(
                    self._kernels_root / ".studio-browser-session.lock"
                )
                if not workspace_lock.acquire():
                    raise WorkflowBrowserBusy("当前工作区已有活跃浏览器会话")
                stack.callback(workspace_lock.release)
                stack.enter_context(self._profile_guard.guard(profile_id))
                kernel_lock = kernel_target_lock(
                    self._kernels_root, kernel.edition, kernel.version
                )
                if not kernel_lock.acquire():
                    raise WorkflowBrowserBusy("所选 CloakBrowser 内核正在使用")
                stack.callback(kernel_lock.release)
            except Exception as error:
                stack.close()
                if isinstance(error, WorkflowBrowserBusy):
                    raise
                raise WorkflowBrowserBusy("Profile 或 CloakBrowser 内核正在使用") from error
            self._owner_id = owner_id
            self._stack = stack

    async def release(self, owner_id: str) -> None:
        async with self._lock:
            if self._owner_id != owner_id or self._stack is None:
                raise WorkflowBrowserBusy("浏览器资源所有者不匹配")
            stack = self._stack
            self._stack = None
            self._owner_id = None
            stack.close()


@dataclass(slots=True)
class _RunningWorker:
    session: WorkflowWorkerSession
    process: asyncio.subprocess.Process
    directory: Path
    executable: Path
    birth: int | None
    monitor: asyncio.Task[None]


@dataclass(slots=True)
class _StartingWorker:
    task: asyncio.Task[Any]
    directory: Path
    executable: Path
    process: asyncio.subprocess.Process | None = None
    birth: int | None = None


class WorkflowWorkerManager:
    def __init__(
        self,
        temp_dir: Path,
        *,
        command: tuple[str, ...] | None = None,
        worker_env: dict[str, str] | None = None,
        start_timeout: float = 90,
        termination_timeout: float = 3,
        on_event: Callable[[dict[str, object]], Any] | None = None,
    ) -> None:
        self._root = (temp_dir / "workflow-worker" / uuid4().hex).resolve()
        self._command = command or workflow_worker_command()
        self._worker_env = worker_env or {}
        self._start_timeout = start_timeout
        self._termination_timeout = termination_timeout
        self._on_event = on_event
        self._starting: dict[str, _StartingWorker] = {}
        self._running: dict[str, _RunningWorker] = {}
        self._failures: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def start(
        self,
        run_id: str,
        profile_id: str,
        executable: Path,
        payload: dict[str, Any],
    ) -> WorkflowWorkerSession:
        if not _SAFE_ID.fullmatch(run_id):
            raise ValueError("runId 无效")
        current = asyncio.current_task()
        assert current is not None
        directory = self._root / run_id
        state = _StartingWorker(current, directory, executable)
        async with self._lock:
            if self._starting or self._running:
                raise WorkflowWorkerBusy("当前工作区已有活跃 workflow worker")
            self._starting[run_id] = state
        process: asyncio.subprocess.Process | None = None
        birth: int | None = None
        monitor: asyncio.Task[None] | None = None
        registered: asyncio.Event | None = None
        try:
            directory.mkdir(parents=True, exist_ok=False)
            env = os.environ.copy()
            env.update(self._worker_env)
            env.pop("CLOAKBROWSER_LICENSE_KEY", None)
            env["CLOAKBROWSER_BINARY_PATH"] = str(executable.resolve(strict=True))
            env["CLOAKBROWSER_CACHE_DIR"] = str(directory)
            env.update({"TMPDIR": str(directory), "TMP": str(directory), "TEMP": str(directory)})
            process = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
                **_process_group_options(),
            )
            birth = process_birth(process.pid) if sys.platform != "win32" else None
            async with self._lock:
                state.process = process
                state.birth = birth
            assert process.stdin is not None and process.stdout is not None
            process.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode())
            await process.stdin.drain()
            raw = await asyncio.wait_for(process.stdout.readline(), self._start_timeout)
            try:
                ready = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise RuntimeError("workflow worker 启动确认无效") from None
            if (
                not isinstance(ready, dict)
                or ready.get("type") != "ready"
                or ready.get("runId") != run_id
                or ready.get("profileId") != profile_id
            ):
                raise RuntimeError("workflow worker 启动确认无效")
            child_pid = ready.get("childPid")
            session = WorkflowWorkerSession(
                run_id,
                profile_id,
                process.pid,
                child_pid if isinstance(child_pid, int) else None,
            )
            registered = asyncio.Event()
            monitor = asyncio.create_task(
                self._monitor(
                    run_id, process, directory, executable, birth, registered
                )
            )
            worker = _RunningWorker(session, process, directory, executable, birth, monitor)
            async with self._lock:
                self._starting.pop(run_id, None)
                self._running[run_id] = worker
                registered.set()
            return session
        except BaseException:
            if registered is not None:
                registered.set()
            if monitor is not None:
                monitor.cancel()
                await asyncio.gather(monitor, return_exceptions=True)
            if process is not None:
                await stop_process_tree(
                    process,
                    self._termination_timeout,
                    directory,
                    executable,
                    birth,
                )
            shutil.rmtree(directory, ignore_errors=True)
            async with self._lock:
                self._starting.pop(run_id, None)
            raise

    async def stop(self, run_id: str) -> None:
        async with self._lock:
            worker = self._running.get(run_id)
            starting = self._starting.get(run_id)
        if worker is not None:
            await stop_process_tree(
                worker.process,
                self._termination_timeout,
                worker.directory,
                worker.executable,
                worker.birth,
            )
            await worker.monitor
            return
        if starting is not None:
            if starting.process is None:
                starting.task.cancel()
            else:
                await stop_process_tree(
                    starting.process,
                    self._termination_timeout,
                    starting.directory,
                    starting.executable,
                    starting.birth,
                )
            await asyncio.gather(starting.task, return_exceptions=True)

    def active_processes(self) -> list[int]:
        processes = [state.process for state in self._starting.values() if state.process]
        processes.extend(worker.process for worker in self._running.values())
        return [process.pid for process in processes if process.returncode is None]

    def busy(self) -> bool:
        return bool(self._starting or self._running)

    def failure(self, run_id: str) -> str | None:
        return self._failures.get(run_id)

    async def shutdown(self) -> None:
        async with self._lock:
            run_ids = list(set(self._starting) | set(self._running))
        await asyncio.gather(*(self.stop(run_id) for run_id in run_ids))
        if self.busy():
            raise RuntimeError("workflow worker 清理未完成")
        shutil.rmtree(self._root, ignore_errors=True)

    async def _monitor(
        self,
        run_id: str,
        process: asyncio.subprocess.Process,
        directory: Path,
        executable: Path,
        birth: int | None,
        registered: asyncio.Event,
    ) -> None:
        await registered.wait()
        assert process.stdout is not None
        try:
            try:
                while raw := await process.stdout.readline():
                    try:
                        event = json.loads(raw)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    if isinstance(event, dict) and self._on_event is not None:
                        callback_result = self._on_event(event)
                        if isawaitable(callback_result):
                            await callback_result
                await process.wait()
            except Exception:  # noqa: BLE001 -- do not persist provider or secret text.
                self._failures[run_id] = "WORKER_EVENT_CONSUMER_FAILED"
        finally:
            await stop_process_tree(
                process, self._termination_timeout, directory, executable, birth
            )
            shutil.rmtree(directory, ignore_errors=True)
            async with self._lock:
                self._running.pop(run_id, None)


def workflow_worker_command() -> tuple[str, ...]:
    if getattr(sys, "frozen", False):
        return (sys.executable, "--workflow-worker")
    return (sys.executable, "-m", "autoflow", "--workflow-worker")


def _process_group_options() -> dict[str, Any]:
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}
