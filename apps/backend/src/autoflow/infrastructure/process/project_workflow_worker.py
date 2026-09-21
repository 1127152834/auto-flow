from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.process.browser_processes import process_birth
from autoflow.infrastructure.process.project_test_browser_worker import (
    force_process_tree,
    wait_for_cleanup,
)

MAX_MESSAGE_BYTES = 1024 * 1024
WorkerStatus = Literal["succeeded", "failed", "cancelled", "timed_out"]


class WorkflowWorkerError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class WorkerOutcome:
    status: WorkerStatus
    error: dict[str, str] | None
    cleanup_confirmed: bool


@dataclass
class _Worker:
    run_id: str
    generation: int
    directory: Path
    artifact_directory: Path
    relative_artifact_directory: str
    executable: Path
    task: asyncio.Task[Any]
    process: asyncio.subprocess.Process | None = None
    birth: int | None = None
    job: int | None = None
    job_attached: bool = False
    stop_requested: bool = False
    cleanup: asyncio.Task[None] | None = None
    created_directory: bool = False
    ready: bool = False


def project_workflow_worker_command() -> tuple[str, ...]:
    if getattr(sys, "frozen", False):
        return (sys.executable, "--project-workflow-worker")
    return (sys.executable, "-m", "autoflow", "--project-workflow-worker")


class ProjectWorkflowWorkerManager:
    """Run-owned browser workers; a commit callback gates every event ACK."""

    def __init__(
        self, temp_dir: Path, *, command: tuple[str, ...] | None = None,
        worker_env: dict[str, str] | None = None, start_timeout: float = 90,
        termination_timeout: float = 3, capacity: int = 1,
        on_capability: Callable[[str, int, dict[str, Any]], Awaitable[Any]] | None = None,
    ) -> None:
        self._root = (temp_dir / "workflow-runs").resolve()
        self._artifact_root = (temp_dir.parent / "workspace" / "runs").resolve()
        self._command = command or project_workflow_worker_command()
        self._worker_env = dict(worker_env or {})
        if (sys.platform == "win32" and not getattr(sys, "frozen", False)
            and self._command[0] == sys.executable and sys.prefix != sys.base_prefix):
            # CPython's venv redirector creates its own Job after spawning the
            # interpreter. Start that interpreter directly so our named Job can
            # own it before any browser children exist; retain the same venv.
            self._command = (vars(sys)["_base_executable"], *self._command[1:])
            self._worker_env["__PYVENV_LAUNCHER__"] = sys.executable
        self._start_timeout = start_timeout
        self._termination_timeout = termination_timeout
        self._on_capability = on_capability
        if type(capacity) is not int or capacity not in {1, 2}:
            raise ValueError("Supported worker capacity is 1 or 2")
        self._capacity = capacity
        self._workers: dict[str, _Worker] = {}
        self._closed = False
        self._lock = asyncio.Lock()

    def busy(self, run_id: str | None = None) -> bool:
        return bool(self._workers) if run_id is None else run_id in self._workers

    async def run(
        self, *, run_id: str, execution_generation: int,
        execution_plan: dict[str, Any], parameters: dict[str, Any],
        variables: dict[str, Any], browser: dict[str, Any], executable: Path,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> WorkerOutcome:
        if str(UUID(run_id)) != run_id or execution_generation < 1:
            raise _protocol_error()
        current = asyncio.current_task()
        assert current is not None
        async with self._lock:
            if self._closed:
                raise WorkflowWorkerError("WORKFLOW_WORKER_UNAVAILABLE", "运行服务正在关闭")
            if run_id in self._workers or len(self._workers) >= self._capacity:
                raise WorkflowWorkerError("WORKFLOW_WORKER_BUSY", "当前已有浏览器运行或清理尚未完成")
            worker = _Worker(
                run_id, execution_generation,
                self._root / run_id / f"generation-{execution_generation}",
                self._artifact_root / run_id / f"generation-{execution_generation}",
                f"runs/{run_id}/generation-{execution_generation}",
                executable.resolve(strict=True), current,
            )
            self._workers[run_id] = worker
        try:
            worker.directory.mkdir(parents=True, exist_ok=False)
            worker.created_directory = True
            worker.artifact_directory.mkdir(parents=True, exist_ok=True)
            worker.artifact_directory.resolve(strict=True).relative_to(self._artifact_root)
            env = os.environ.copy()
            env.update(self._worker_env)
            env.pop("CLOAKBROWSER_LICENSE_KEY", None)
            env.update({
                "CLOAKBROWSER_BINARY_PATH": str(worker.executable),
                "CLOAKBROWSER_CACHE_DIR": str(worker.directory),
                "AUTOFLOW_WORKFLOW_ARTIFACT_DIR": str(worker.artifact_directory),
                "AUTOFLOW_WORKFLOW_ARTIFACT_RELATIVE_DIR": worker.relative_artifact_directory,
                "TMPDIR": str(worker.directory), "TMP": str(worker.directory),
                "TEMP": str(worker.directory),
            })
            job_name = f"Local\\AutoFlow-{run_id}-{execution_generation}-{uuid4().hex}"
            if sys.platform == "win32":
                from .windows_job import create_run_job
                env["AUTOFLOW_WORKER_JOB_NAME"] = job_name
                worker.job = create_run_job(job_name)
            group: dict[str, Any] = (
                {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}  # type: ignore[attr-defined]
                if sys.platform == "win32" else {"start_new_session": True}
            )
            spawn = asyncio.create_task(asyncio.create_subprocess_exec(
                *self._command, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                env=env, limit=MAX_MESSAGE_BYTES, **group,
            ))
            try:
                worker.process = await asyncio.shield(spawn)
            except asyncio.CancelledError:
                worker.process = await wait_for_cleanup(spawn)
                self._capture_birth(worker)
                await wait_for_cleanup(asyncio.create_task(self._attach_job(worker, job_name)))
                raise
            self._capture_birth(worker)
            await self._attach_job(worker, job_name)
            await self._send(worker, {
                "type": "start", "protocolVersion": 1, "runId": run_id,
                "executionGeneration": execution_generation,
                "executionPlan": execution_plan, "parameters": parameters,
                "variables": variables, "browser": browser,
            })
            message = await asyncio.wait_for(self._read(worker), self._start_timeout)
            if message.get("type") != "ready":
                raise _protocol_error()
            worker.ready = True
            if worker.stop_requested:
                await self._send_stop(worker)
            outcome = await self._exchange(worker, on_event)
            assert worker.process is not None
            await asyncio.wait_for(worker.process.wait(), self._termination_timeout)
            if (worker.process.returncode not in {0, 1}
                or (outcome.status == "succeeded" and worker.process.returncode != 0)):
                raise WorkflowWorkerError("WORKFLOW_WORKER_LOST", "执行进程异常退出，需核验运行结果")
            await self._cleanup(worker)
            return outcome
        finally:
            # Cancellation and callback failure still have to finish owned cleanup.
            await self._cleanup(worker)

    async def _attach_job(self, worker: _Worker, name: str) -> None:
        if sys.platform != "win32":
            return
        from .windows_job import close_worker_job, record_worker_job
        assert worker.process is not None
        if worker.birth is None:
            raise WorkflowWorkerError('WORKFLOW_CLEANUP_FAILED', '执行进程身份尚未确认')
        ownership = asyncio.create_task(asyncio.to_thread(record_worker_job, worker.directory, worker.run_id, worker.generation, name, worker.process.pid, worker.birth))
        previous = worker.job
        try:
            worker.job = await asyncio.shield(ownership)
        except asyncio.CancelledError:
            worker.job = await wait_for_cleanup(ownership)
            raise
        finally:
            if ownership.done() and not ownership.cancelled() and ownership.exception() is None:
                worker.job_attached = True
                if previous is not None:
                    close_worker_job(previous)

    def _capture_birth(self, worker: _Worker) -> None:
        assert worker.process is not None
        worker.birth = process_birth(worker.process.pid)

    async def _exchange(
        self, worker: _Worker,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> WorkerOutcome:
        while True:
            message = await self._read(worker)
            if message.get("type") == "event":
                event = message.get("event")
                if (not isinstance(event, dict) or type(event.get("executionGeneration")) is not int
                    or event.get("runId") != worker.run_id
                    or event.get("executionGeneration") != worker.generation
                    or not isinstance(event.get("eventId"), str) or not event["eventId"]
                    or "sequence" in event):
                    raise _protocol_error()
                await on_event(event)
                await self._send(worker, {
                    "type": "event_committed", "eventId": event["eventId"],
                    "executionGeneration": worker.generation,
                })
            elif message.get("type") == "capability":
                if self._on_capability is None or not isinstance(message.get("commandId"), str):
                    raise _protocol_error()
                reply: dict[str, Any] = {
                    "type": "capability_result", "commandId": message["commandId"],
                    "runId": worker.run_id, "executionGeneration": worker.generation,
                }
                try:
                    reply["result"] = await self._capability_while_alive(worker, message)
                except ProjectError as rejected:
                    reply["error"] = {"code": rejected.code, "message": "项目能力请求未完成"}
                # Unknown failures may follow a commit. Fence the run rather than
                # telling the worker it is safe to execute an error branch.
                await self._send(worker, reply)
            elif message.get("type") == "finished":
                if message.get("cleanupConfirmed") is not True:
                    raise WorkflowWorkerError("WORKFLOW_CLEANUP_FAILED", "浏览器清理尚未确认")
                status = message.get("status")
                if status not in {"succeeded", "failed", "cancelled", "timed_out"}:
                    raise _protocol_error()
                # Worker diagnostics cannot expose launch credentials or paths.
                error = None if status == "succeeded" else {
                    "code": f"WORKFLOW_{str(status).upper()}",
                    "message": "工作流未完整成功，请查看已提交的节点记录",
                }
                return WorkerOutcome(cast(WorkerStatus, status), error, True)
            elif message.get("type") == "error":
                raise WorkflowWorkerError("WORKFLOW_CLEANUP_FAILED", "执行进程未确认完成，需核验清理结果")
            else:
                raise _protocol_error()

    async def _capability_while_alive(self, worker: _Worker, message: dict[str, Any]) -> Any:
        assert self._on_capability is not None and worker.process is not None
        capability = asyncio.ensure_future(self._on_capability(worker.run_id, worker.generation, message))
        exited = asyncio.create_task(worker.process.wait())
        try:
            done, _ = await asyncio.wait({capability, exited}, return_when=asyncio.FIRST_COMPLETED)
            if exited in done:
                raise WorkflowWorkerError("WORKFLOW_WORKER_LOST", "执行进程失联，运行结果待核验")
            return await capability
        finally:
            for task in (capability, exited):
                if not task.done():
                    task.cancel()
            await asyncio.gather(capability, exited, return_exceptions=True)

    async def _read(self, worker: _Worker) -> dict[str, Any]:
        assert worker.process is not None and worker.process.stdout is not None
        try:
            raw = await worker.process.stdout.readline()
            if not raw:
                raise WorkflowWorkerError("WORKFLOW_WORKER_LOST", "执行进程失联，运行结果待核验")
            if len(raw) > MAX_MESSAGE_BYTES or not raw.endswith(b"\n"):
                raise _protocol_error()
            value = json.loads(raw)
        except (ValueError, UnicodeError):
            raise _protocol_error() from None
        if (not isinstance(value, dict) or type(value.get("protocolVersion")) is not int
            or type(value.get("executionGeneration")) is not int
            or value.get("protocolVersion") != 1
            or value.get("runId") != worker.run_id
            or value.get("executionGeneration") != worker.generation):
            raise _protocol_error()
        return value

    async def _send(self, worker: _Worker, message: dict[str, Any]) -> None:
        assert worker.process is not None and worker.process.stdin is not None
        if worker.process.returncode is not None:
            raise WorkflowWorkerError("WORKFLOW_WORKER_LOST", "执行进程已退出")
        data = (json.dumps(message, ensure_ascii=False, allow_nan=False) + "\n").encode()
        if len(data) > MAX_MESSAGE_BYTES:
            raise _protocol_error()
        worker.process.stdin.write(data)
        await worker.process.stdin.drain()

    async def _send_stop(self, worker: _Worker) -> None:
        await self._send(worker, {"type": "stop", "executionGeneration": worker.generation})

    async def stop(self, run_id: str) -> None:
        worker = self._workers.get(run_id)
        if worker is None or worker.run_id != run_id:
            return
        worker.stop_requested = True
        if worker.process is not None and worker.ready:
            await self._send_stop(worker)

    async def force_stop(self, run_id: str) -> None:
        # The caller must commit generation revocation before invoking this method.
        worker = self._workers.get(run_id)
        if worker is not None and worker.run_id == run_id:
            if worker.process is None:
                if worker.task is not asyncio.current_task():
                    worker.task.cancel()
                    await asyncio.gather(worker.task, return_exceptions=True)
                if self._workers.get(worker.run_id) is worker:
                    try:
                        await self._cleanup(worker)
                    except Exception:  # noqa: BLE001 -- preserve a retryable cleanup boundary.
                        raise WorkflowWorkerError(
                            "WORKFLOW_CLEANUP_FAILED", "执行进程清理失败，请重试核验",
                        ) from None
            else:
                await self._cleanup(worker)

    def discard_uncommitted_artifact(
        self,
        run_id: str,
        execution_generation: int,
        artifact_id: str,
        relative_path: str,
    ) -> None:
        """Remove one worker-owned artifact only after the caller proved no DB fact exists."""
        worker = self._workers.get(run_id)
        if (
            worker is None
            or worker.run_id != run_id
            or worker.generation != execution_generation
            or relative_path
            != f"{worker.relative_artifact_directory}/{artifact_id}.png"
        ):
            return
        candidate = worker.artifact_directory / f"{artifact_id}.png"
        try:
            info = candidate.lstat()
            if not candidate.is_file() or candidate.is_symlink() or info.st_nlink != 1:
                return
            candidate.unlink()
        except FileNotFoundError:
            return

    async def _cleanup(self, worker: _Worker) -> None:
        if worker.cleanup is None or (worker.cleanup.done() and worker.cleanup.exception()):
            worker.cleanup = asyncio.create_task(self._cleanup_owned(worker))
        await wait_for_cleanup(worker.cleanup)

    async def _cleanup_owned(self, worker: _Worker) -> None:
        process = worker.process
        if sys.platform == "win32":
            if worker.job is not None:
                from .windows_job import close_worker_job, terminate_worker_job
                await asyncio.to_thread(terminate_worker_job, worker.job, self._termination_timeout)
            if process is not None:
                if process.returncode is None:
                    try:
                        process.kill()
                    except (PermissionError, ProcessLookupError):
                        # TerminateProcess may race an already exiting process.
                        await asyncio.wait_for(process.wait(), self._termination_timeout)
                await process.wait()
                if worker.job is not None and not worker.job_attached:
                    # An unconfirmed launcher must not release its directory or
                    # capacity merely because the known Job became empty.
                    raise WorkflowWorkerError('WORKFLOW_CLEANUP_FAILED', '执行进程树所有权尚未确认')
            if worker.job is not None:
                close_worker_job(worker.job)
                worker.job = None
        elif process is not None:
            await force_process_tree(
                process, self._termination_timeout,
                worker.directory, worker.executable, worker.birth,
                strict_ownership=True,
            )
        if worker.created_directory:
            try:
                shutil.rmtree(worker.directory)
            except FileNotFoundError:
                pass
        async with self._lock:
            if self._workers.get(worker.run_id) is worker:
                self._workers.pop(worker.run_id)

    async def shutdown(self) -> None:
        self._closed = True
        results = await asyncio.gather(*(self.force_stop(identity) for identity in tuple(self._workers)), return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException):
                raise result


def _protocol_error() -> WorkflowWorkerError:
    return WorkflowWorkerError("WORKFLOW_WORKER_PROTOCOL_INVALID", "执行进程消息无效")
