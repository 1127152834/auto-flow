from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from threading import Event, Thread
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.credentials.redaction import redact_sensitive_text
from autoflow.infrastructure.process.browser_processes import process_birth
from autoflow.infrastructure.process.project_test_browser_worker import (
    force_process_tree,
    wait_for_cleanup,
)
from autoflow.infrastructure.process.stderr_sink import StderrSink
from autoflow.infrastructure.process.workflow_subprocess import workflow_environment

from .proxy_worker_requests import ProxyWorkerRequests

MAX_MESSAGE_BYTES = 1024 * 1024
MAX_EVENT_BYTES = 16 * 1024 * 1024
STDERR_LOG_NAME = "worker-stderr.log"
STDERR_TAIL_LINES = 50
STDERR_TAIL_LINE_CHARS = 500
# Absolute path -> its last component; URLs and relative paths are left alone.
_ABSOLUTE_PATH = re.compile(r"(?<![\w:./\\])(?:[A-Za-z]:)?[\\/](?:[^\s\\/:\"'<>|]+[\\/])+([^\s\\/:\"'<>|]*)")


def _without_partial_secret(line: str, secrets: Iterable[str]) -> str:
    """A line cut at the sink's size limit may end inside a secret, which redaction cannot match."""
    if not line.endswith(" …"):
        return line
    body = line[:-2]
    for secret in secrets:
        for length in range(min(len(secret) - 1, len(body)), 3, -1):
            if body.endswith(secret[:length]):
                return body[: len(body) - length] + " …"
    return line

WorkerStatus = Literal["succeeded", "failed", "cancelled", "timed_out"]


# Remediation M3 R3-04: workers are started with v2 (event batches); every command they receive must
# carry the same version or the worker ignores it. v1 messages from older workers are still read.
WORKER_PROTOCOL_VERSION = 2
# Remediation M3 R3-06: a pooled worker serves at most this many runs, idles at most this long.
POOL_MAX_RUNS = 50
POOL_IDLE_SECONDS = 120.0

class WorkflowWorkerError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class WorkerOutcome:
    status: WorkerStatus
    error: dict[str, str] | None
    cleanup_confirmed: bool
    reusable: bool = False


@dataclass
class _Worker:
    run_id: str
    generation: int
    directory: Path
    artifact_directory: Path
    relative_artifact_directory: str
    executable: Path | None
    task: asyncio.Task[Any]
    process: asyncio.subprocess.Process | None = None
    birth: int | None = None
    job: int | None = None
    job_attached: bool = False
    stop_requested: bool = False
    cleanup: asyncio.Task[None] | None = None
    created_directory: bool = False
    ready: bool = False
    capability: asyncio.Future[Any] | None = None
    write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    credential_read: Event | None = None
    proxy_requests: ProxyWorkerRequests | None = None
    stderr: StderrSink | None = None
    stderr_task: asyncio.Task[None] | None = None
    secrets: list[str] = field(default_factory=list)
    # Remediation M3 R3-06: a pooled process outlives its run and keeps its browser.
    session_key: str | None = None
    runs: int = 0
    parked: bool = False
    stderr_relative: str | None = None  # a pooled process keeps one log, under its first run


def project_workflow_worker_command() -> tuple[str, ...]:
    if getattr(sys, "frozen", False):
        return (sys.executable, "--project-workflow-worker")
    return (sys.executable, "-m", "autoflow", "--project-workflow-worker")


class ProjectWorkflowWorkerManager:
    """Run-owned browser workers; a commit callback gates every event ACK."""

    supports_event_batches = True

    def __init__(
        self, temp_dir: Path, *, command: tuple[str, ...] | None = None,
        worker_env: dict[str, str] | None = None, start_timeout: float = 90,
        termination_timeout: float = 3, capacity: int = 1,
        on_capability: Callable[[str, int, dict[str, Any]], Awaitable[Any]] | None = None,
        resolve_credential: Callable[[str], Mapping[str, str]] | None = None,
        proxy_service: Any | None = None,
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
        if type(capacity) is not int or not 1 <= capacity <= 128:
            raise ValueError("Worker capacity must be an integer from 1 to 128")
        self._capacity = capacity
        self._workers: dict[str, _Worker] = {}
        self._resolve_credential = resolve_credential
        self._proxy_service = proxy_service
        self._closed = False
        self._lock = asyncio.Lock()
        self._idle: dict[str, list[_Worker]] = {}
        self._retiring: set[asyncio.Future[None]] = set()

    def set_capacity(self, capacity: int) -> None:
        """Live-browser limit; lowering it never stops running workers."""
        if type(capacity) is not int or not 1 <= capacity <= 128:
            raise ValueError("Worker capacity must be an integer from 1 to 128")
        self._capacity = capacity

    def busy(self, run_id: str | None = None) -> bool:
        return bool(self._workers) if run_id is None else run_id in self._workers

    async def run(
        self, *, run_id: str, execution_generation: int,
        execution_plan: dict[str, Any], parameters: dict[str, Any],
        variables: dict[str, Any], browser: dict[str, Any], executable: Path | None,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
        model_bindings: list[dict[str, Any]] | None = None,
        on_events: Callable[[list[dict[str, Any]]], Awaitable[None]] | None = None,
        session_key: str | None = None,
    ) -> WorkerOutcome:
        if str(UUID(run_id)) != run_id or execution_generation < 1:
            raise _protocol_error()
        current = asyncio.current_task()
        assert current is not None
        evicted: _Worker | None = None
        async with self._lock:
            if self._closed:
                raise WorkflowWorkerError("WORKFLOW_WORKER_UNAVAILABLE", "运行服务正在关闭")
            reused = self._take_idle(session_key) if session_key is not None else None
            if reused is None and len(self._workers) + self._idle_count() >= self._capacity and self._idle_count():
                evicted = self._take_any_idle()  # an idle browser yields its slot to work that needs one
            if run_id in self._workers or (reused is None and len(self._workers) + self._idle_count() >= self._capacity):
                if reused is not None:
                    self._park(reused)
                raise WorkflowWorkerError("WORKFLOW_WORKER_BUSY", "当前已有浏览器运行或清理尚未完成")
            artifact = (
                self._artifact_root / run_id / f"generation-{execution_generation}",
                f"runs/{run_id}/generation-{execution_generation}",
            )
            if reused is not None:
                worker = reused
                worker.run_id, worker.generation, worker.task = run_id, execution_generation, current
                worker.artifact_directory, worker.relative_artifact_directory = artifact
                worker.ready = worker.stop_requested = worker.parked = False
                worker.cleanup = worker.capability = worker.credential_read = None
                worker.write_lock, worker.secrets = asyncio.Lock(), []
            else:
                worker = _Worker(
                    run_id, execution_generation,
                    self._root / "pool" / uuid4().hex if session_key is not None
                    else self._root / run_id / f"generation-{execution_generation}",
                    *artifact,
                    executable.resolve(strict=True) if executable is not None else None, current,
                    session_key=session_key,
                )
            self._workers[run_id] = worker
            if self._proxy_service is not None:
                worker.proxy_requests = ProxyWorkerRequests(
                    self._proxy_service, run_id, execution_plan,
                    lambda response: self._send(worker, response),
                    lambda: self._workers.get(run_id) is worker and not worker.stop_requested and worker.cleanup is None,
                    execution_generation,
                    WORKER_PROTOCOL_VERSION,
                )
        if evicted is not None:
            await self._retire(evicted)
        try:
            if reused is not None:
                await asyncio.to_thread(self._artifact_directory_ready, worker)
                return await self._serve(worker, execution_plan, parameters, variables, browser, on_event, on_events, model_bindings)
            # Remediation M3 AC3-02: directory creation is slow enough on Windows to stall the loop.
            await asyncio.to_thread(self._run_directories_ready, worker)
            env = workflow_environment({**os.environ, **self._worker_env})
            env.pop("CLOAKBROWSER_LICENSE_KEY", None)
            env.pop("CLOAKBROWSER_BINARY_PATH", None)
            if worker.executable is not None:
                env["CLOAKBROWSER_BINARY_PATH"] = str(worker.executable)
            env.update({
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
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                env=env, limit=MAX_EVENT_BYTES, **group,
            ))
            try:
                worker.process = await asyncio.shield(spawn)
            except asyncio.CancelledError:
                worker.process = await wait_for_cleanup(spawn)
                self._start_stderr(worker)
                self._capture_birth(worker)
                await wait_for_cleanup(asyncio.create_task(self._attach_job(worker, job_name)))
                raise
            self._start_stderr(worker)
            self._capture_birth(worker)
            await self._attach_job(worker, job_name)
            if session_key is not None:
                return await self._serve(worker, execution_plan, parameters, variables, browser, on_event, on_events, model_bindings)
            await self._send(worker, {
                "type": "start", "protocolVersion": WORKER_PROTOCOL_VERSION, "runId": run_id,
                "executionGeneration": execution_generation,
                "executionPlan": execution_plan, "parameters": parameters,
                "variables": variables, "browser": browser,
                "modelBindings": model_bindings or [],
            })
            outcome = await self._exchange(worker, on_event, on_events)
            assert worker.process is not None and worker.process.stdin is not None
            # No more commands follow the terminal envelope. Release the worker's
            # sole stdin reader before waiting for interpreter/process shutdown.
            worker.ready = False
            worker.process.stdin.close()
            if (
                worker.stop_requested
                and outcome.status == "cancelled"
                and worker.process.returncode is None
            ):
                # asyncio.to_thread work cannot be cancelled. Once the worker
                # confirms cancellation and async cleanup, the owned process is
                # the cancellation boundary; waiting cannot make native work stop.
                await self._cleanup(worker)
                return outcome
            try:
                await asyncio.wait_for(worker.process.wait(), self._termination_timeout)
            except TimeoutError:
                if outcome.status == "succeeded":
                    raise
                if worker.process.returncode is None:
                    # Failed native to_thread work can outlive asyncio.run. Only
                    # a still-live process needs forced cleanup; a natural crash
                    # must retain its unexpected exit code and fail validation.
                    worker.stop_requested = True
                    await self._cleanup(worker)
                    return outcome
            if (worker.process.returncode not in {0, 1}
                or (outcome.status == "succeeded" and worker.process.returncode != 0)):
                raise await self._lost(worker, "执行进程异常退出，需核验运行结果")
            await self._cleanup(worker)
            return outcome
        finally:
            # Cancellation and callback failure still have to finish owned cleanup.
            if not worker.parked:
                await self._cleanup(worker)

    async def _serve(
        self, worker: _Worker, execution_plan: dict[str, Any], parameters: dict[str, Any],
        variables: dict[str, Any], browser: dict[str, Any],
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
        on_events: Callable[[list[dict[str, Any]]], Awaitable[None]] | None,
        model_bindings: list[dict[str, Any]] | None,
    ) -> WorkerOutcome:
        """One run on a pooled process; a clean, reusable finish parks it for the next run."""
        assert worker.process is not None and worker.process.stdin is not None
        worker.runs += 1
        await self._send(worker, {
            "type": "start", "protocolVersion": WORKER_PROTOCOL_VERSION, "runId": worker.run_id,
            "executionGeneration": worker.generation, "pooled": True,
            "artifactDirectory": str(worker.artifact_directory),
            "artifactRelativeDirectory": worker.relative_artifact_directory,
            "executionPlan": execution_plan, "parameters": parameters,
            "variables": variables, "browser": browser, "modelBindings": model_bindings or [],
        })
        outcome = await self._exchange(worker, on_event, on_events)
        worker.ready = False
        if (outcome.reusable and outcome.status in {"succeeded", "failed"} and not worker.stop_requested
                and worker.process.returncode is None and worker.runs < POOL_MAX_RUNS and not self._closed):
            if worker.proxy_requests is not None:
                await worker.proxy_requests.close()
                worker.proxy_requests = None
            async with self._lock:
                if self._workers.get(worker.run_id) is worker:
                    self._workers.pop(worker.run_id)
                self._park(worker)
            return outcome
        # Not parked: the process ends now; a clean finish waits for a shutdown, anything else exits itself.
        if outcome.reusable and worker.process.returncode is None:
            await self._write(worker, {"type": "shutdown"})
        worker.process.stdin.close()
        try:
            await asyncio.wait_for(worker.process.wait(), self._termination_timeout)
        except TimeoutError:
            worker.stop_requested = True
        await self._cleanup(worker)
        return outcome

    def _run_directories_ready(self, worker: _Worker) -> None:
        worker.directory.mkdir(parents=True, exist_ok=False)
        worker.created_directory = True  # set where it was made, so a cancelled await still cleans it up
        self._artifact_directory_ready(worker)

    def _artifact_directory_ready(self, worker: _Worker) -> None:
        worker.artifact_directory.mkdir(parents=True, exist_ok=True)
        worker.artifact_directory.resolve(strict=True).relative_to(self._artifact_root)

    def _idle_count(self) -> int:
        return sum(len(items) for items in self._idle.values())

    def _park(self, worker: _Worker) -> None:
        assert worker.session_key is not None
        worker.parked = True
        self._idle.setdefault(worker.session_key, []).append(worker)
        asyncio.get_running_loop().call_later(POOL_IDLE_SECONDS, self._expire, worker)

    def _take_idle(self, key: str) -> _Worker | None:
        items = self._idle.get(key, [])
        while items:
            worker = items.pop()
            if worker.process is not None and worker.process.returncode is None:
                return worker
            self._background(self._retire(worker))  # died while idle
        return None

    def _take_any_idle(self) -> _Worker | None:
        for items in self._idle.values():
            if items:
                return items.pop(0)
        return None

    def _expire(self, worker: _Worker) -> None:
        items = self._idle.get(worker.session_key or "", [])
        if worker in items and worker.parked:
            items.remove(worker)
            self._background(self._retire(worker))

    def _background(self, work: Awaitable[None]) -> None:
        task = asyncio.ensure_future(work)
        self._retiring.add(task)
        task.add_done_callback(self._retiring.discard)

    async def _retire(self, worker: _Worker) -> None:
        """End an idle pooled process: ask it to close its browser, then clean up what it owned."""
        worker.parked = False
        worker.cleanup = None
        process = worker.process
        if process is not None and process.returncode is None and process.stdin is not None:
            try:
                await self._write(worker, {"type": "shutdown"})
                process.stdin.close()
                await asyncio.wait_for(process.wait(), self._termination_timeout)
            except Exception:  # noqa: BLE001 -- the owned-process cleanup below still kills it
                worker.stop_requested = True
        await self._cleanup(worker)

    def _start_stderr(self, worker: _Worker) -> None:
        """Keep draining stderr for the whole life of the process; a full pipe would stall it."""
        process = worker.process
        if process is None or process.stderr is None or worker.stderr_task is not None:
            return
        worker.stderr = StderrSink(worker.artifact_directory / STDERR_LOG_NAME)
        worker.stderr_relative = f"{worker.relative_artifact_directory}/{STDERR_LOG_NAME}"
        worker.stderr_task = asyncio.create_task(worker.stderr.drain(process.stderr))

    async def _finish_stderr(self, worker: _Worker, wait: float) -> None:
        task, sink = worker.stderr_task, worker.stderr
        if task is not None and not task.done():
            try:
                await asyncio.wait_for(asyncio.shield(task), wait)
            except Exception:  # noqa: BLE001, S110 -- diagnostics must never change the outcome
                pass
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if sink is not None:
            try:
                await asyncio.wait_for(sink.close(), 2)
            except Exception:  # noqa: BLE001, S110
                pass

    async def _lost(self, worker: _Worker, message: str, code: str = "WORKFLOW_WORKER_LOST") -> WorkflowWorkerError:
        details = await self._diagnostics(worker, code)
        located = details.get("diagnosticLog")
        # The path is in the message itself so it survives any consumer that drops structured details.
        return WorkflowWorkerError(code, f"{message}；诊断日志：{located}" if located else message, details)

    async def _diagnostics(self, worker: _Worker, cause: str) -> dict[str, Any]:
        """Safe, bounded evidence for an unknown result: where the log is and a redacted tail."""
        details: dict[str, Any] = {"causeCode": cause}
        sink = worker.stderr
        if sink is None:
            return details
        await self._finish_stderr(worker, 1.0)
        if sink.write_failed:
            details["diagnosticLogUnavailable"] = "write_failed"
        elif sink.written_bytes:
            details["diagnosticLog"] = worker.stderr_relative
        else:
            details["diagnosticLogUnavailable"] = "no_output"
        if sink.dropped or sink.truncated:
            details["diagnosticLogIncomplete"] = True
        try:
            lines = [
                _ABSOLUTE_PATH.sub(
                    r"\1", redact_sensitive_text(_without_partial_secret(line, worker.secrets), worker.secrets)
                )[:STDERR_TAIL_LINE_CHARS]
                for line in sink.tail(STDERR_TAIL_LINES)
            ]
            if lines:
                details["stderrTail"] = lines
                details["stderrTailRedacted"] = True
        except Exception:  # noqa: BLE001 -- unsure it is safe, so it is not exposed
            details["stderrTailOmitted"] = "redaction_failed"
        return details

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
        on_events: Callable[[list[dict[str, Any]]], Awaitable[None]] | None = None,
    ) -> WorkerOutcome:
        while True:
            message = (
                await self._read(worker) if worker.ready else
                await asyncio.wait_for(self._read(worker), self._start_timeout)
            )
            if not worker.ready:
                if message.get("type") == "ready":
                    worker.ready = True
                    if worker.stop_requested:
                        await self._send_stop(worker)
                    continue
                # Browser launch can fail before ready. Still require the normal
                # terminal cleanup proof, child exit and owned-process cleanup.
                if (message.get("type") != "finished"
                    or message.get("status") not in {"failed", "cancelled"}):
                    raise _protocol_error()
            if message.get("type") == "proxy:request":
                if worker.proxy_requests is None:
                    raise _protocol_error()
                worker.proxy_requests.receive(message)
                continue
            if message.get("type") == "eventBatch":
                # Remediation M3 R3-04: process events committed together, one ACK for the batch.
                events = message.get("events")
                batch_id = message.get("batchId")
                if (message.get("protocolVersion") != 2 or not isinstance(batch_id, str) or not batch_id
                        or not isinstance(events, list) or not events or len(events) > 1000):
                    raise _protocol_error()
                for event in events:
                    self._check_event(worker, event)
                if on_events is not None:
                    await on_events(events)
                else:
                    for event in events:
                        await on_event(event)
                if worker.proxy_requests is not None:
                    for event in events:
                        worker.proxy_requests.observe(event)
                await self._send(worker, {
                    "type": "events_committed", "batchId": batch_id,
                    "executionGeneration": worker.generation,
                })
                continue
            if message.get("type") == "event":
                event = self._check_event(worker, message.get("event"))
                await on_event(event)
                if worker.proxy_requests is not None:
                    worker.proxy_requests.observe(event)
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
                    if message.get('operation') == 'initializeBrowser':
                        executable = Path(reply['result']['executablePath']).resolve(strict=True)
                        if worker.executable is not None and worker.executable != executable:
                            raise _protocol_error()
                        worker.executable = executable
                except ProjectError as rejected:
                    reply["error"] = {"code": rejected.code, "message": f"项目能力请求未完成：{rejected.message}"}
                # Unknown failures may follow a commit. Fence the run rather than
                # telling the worker it is safe to execute an error branch.
                await self._send(worker, reply)
            elif message.get("type") == "credential:read":
                request_id, name, field_name = (message.get(key) for key in ("requestId", "name", "field"))
                if not isinstance(request_id, str) or not request_id or not isinstance(name, str) or not isinstance(field_name, str):
                    raise _protocol_error()
                value = await self._read_credential(worker, name, field_name)
                await self._send(worker, {
                    "type": "credential:result", "protocolVersion": WORKER_PROTOCOL_VERSION,
                    "runId": worker.run_id, "executionGeneration": worker.generation,
                    "requestId": request_id, "value": value,
                })
            elif message.get("type") == "execution:command_applied":
                command_id, request_id = message.get("commandId"), message.get("requestId")
                if not isinstance(command_id, str) or not command_id or not isinstance(request_id, str) or not request_id:
                    raise _protocol_error()
                await on_event({
                    "eventId": command_id, "runId": worker.run_id,
                    "executionGeneration": worker.generation, "kind": "interaction",
                    "nodeId": None, "nodeVisitId": None, "attempt": None,
                    "occurredAt": datetime.now(UTC).isoformat(),
                    "payload": {"type": "execution:command_applied", "commandId": command_id, "requestId": request_id},
                })
            elif message.get("type") == "finished":
                if message.get("cleanupConfirmed") is not True:
                    raise WorkflowWorkerError("WORKFLOW_CLEANUP_FAILED", "浏览器清理尚未确认")
                status = message.get("status")
                if status not in {"succeeded", "failed", "cancelled", "timed_out"}:
                    raise _protocol_error()
                error = None if status == "succeeded" else _terminal_error(status, message.get("error"), worker.secrets)
                return WorkerOutcome(cast(WorkerStatus, status), error, True, message.get("reusable") is True)
            elif message.get("type") == "error":
                raise WorkflowWorkerError("WORKFLOW_CLEANUP_FAILED", "执行进程未确认完成，需核验清理结果")
            else:
                raise _protocol_error()

    @staticmethod
    def _check_event(worker: _Worker, event: Any) -> dict[str, Any]:
        if (not isinstance(event, dict) or type(event.get("executionGeneration")) is not int
            or event.get("runId") != worker.run_id
            or event.get("executionGeneration") != worker.generation
            or not isinstance(event.get("eventId"), str) or not event["eventId"]
            or "sequence" in event):
            raise _protocol_error()
        return event

    async def _capability_while_alive(self, worker: _Worker, message: dict[str, Any]) -> Any:
        assert self._on_capability is not None and worker.process is not None
        capability = asyncio.ensure_future(self._on_capability(worker.run_id, worker.generation, message))
        worker.capability = capability
        exited = asyncio.create_task(worker.process.wait())
        try:
            done, _ = await asyncio.wait({capability, exited}, return_when=asyncio.FIRST_COMPLETED)
            if exited in done:
                raise await self._lost(worker, "执行进程失联，运行结果待核验")
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
                raise await self._lost(worker, "执行进程失联，运行结果待核验")
            if len(raw) > MAX_EVENT_BYTES or not raw.endswith(b"\n"):
                raise _protocol_error()
            value = json.loads(raw)
        except (ValueError, UnicodeError):
            raise _protocol_error() from None
        if (not isinstance(value, dict) or type(value.get("protocolVersion")) is not int
            or type(value.get("executionGeneration")) is not int
            or value.get("protocolVersion") not in {1, 2}
            or value.get("runId") != worker.run_id
            or value.get("executionGeneration") != worker.generation):
            raise _protocol_error()
        return value

    async def _read_credential(self, worker: _Worker, name: str, field_name: str) -> str | None:
        resolver = self._resolve_credential
        if not name or not field_name or resolver is None or worker.stop_requested or (worker.credential_read is not None and not worker.credential_read.is_set()):
            return None
        done, discard = Event(), Event()
        result: list[str] = []
        worker.credential_read = done

        def read() -> None:
            try:
                value = resolver(name).get(field_name)
                if isinstance(value, str) and not discard.is_set():
                    result.append(value)
                    worker.secrets.append(value)  # so stderr diagnostics can be redacted
            except Exception:  # noqa: BLE001 -- source leaves unavailable credential references intact.
                result.clear()
            finally:
                done.set()

        # Match Studio's existing native-keychain boundary: at most one blocked
        # daemon read per owned run; stop/cleanup never waits for a system prompt.
        Thread(target=read, daemon=True, name="project-workflow-credential-read").start()
        try:
            async with asyncio.timeout(3):
                while not done.is_set():
                    if self._workers.get(worker.run_id) is not worker or worker.stop_requested:
                        return None
                    await asyncio.sleep(.02)
            return result[0] if result else None
        except TimeoutError:
            return None
        finally:
            discard.set()
            if done.is_set():
                worker.credential_read = None

    async def _send(self, worker: _Worker, message: dict[str, Any]) -> None:
        async with worker.write_lock:
            if message.get("type") in {"input_prompt_result", "js_script_result", "webhook_result"} and (
                self._workers.get(worker.run_id) is not worker or worker.stop_requested or not worker.ready or worker.cleanup is not None
            ):
                raise WorkflowWorkerError("WORKFLOW_INTERACTION_UNAVAILABLE", "交互请求已结束或执行代次已失效")
            if message.get("type") == "credential:result" and (self._workers.get(worker.run_id) is not worker or worker.stop_requested or worker.cleanup is not None):
                return
            await self._write(worker, message)

    async def _write(self, worker: _Worker, message: dict[str, Any]) -> None:
        assert worker.process is not None and worker.process.stdin is not None
        if worker.process.returncode is not None:
            raise await self._lost(worker, "执行进程已退出")
        data = (json.dumps(message, ensure_ascii=False, allow_nan=False) + "\n").encode()
        if len(data) > MAX_MESSAGE_BYTES:
            raise _protocol_error()
        worker.process.stdin.write(data)
        await worker.process.stdin.drain()

    async def send_command(self, run_id: str, execution_generation: int, command: dict[str, Any]) -> None:
        worker = self._workers.get(run_id)
        if (worker is None or worker.run_id != run_id or type(execution_generation) is not int
            or worker.generation != execution_generation or worker.stop_requested or not worker.ready
            or worker.cleanup is not None):
            raise WorkflowWorkerError("WORKFLOW_INTERACTION_UNAVAILABLE", "交互请求已结束或执行代次已失效")
        if (command.get("type") not in {"input_prompt_result", "js_script_result", "webhook_result"}
            or not isinstance(command.get("commandId"), str) or not command["commandId"]
            or not isinstance(command.get("requestId"), str) or not command["requestId"]):
            raise _protocol_error()
        await self._send(worker, {**command, "protocolVersion": WORKER_PROTOCOL_VERSION, "runId": run_id,
                                  "executionGeneration": execution_generation})

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

        ):
            return
        relative = PurePosixPath(relative_path)
        prefix = PurePosixPath(worker.relative_artifact_directory)
        if relative.as_posix() != relative_path or "\\" in relative_path or ".." in relative.parts or not relative.is_relative_to(prefix):
            return
        suffix = relative.relative_to(prefix)
        legacy = suffix == PurePosixPath(f"{artifact_id}.png")
        if not legacy and (len(suffix.parts) < 2 or suffix.parts[0] != "artifacts"):
            return
        candidate = worker.artifact_directory / Path(*suffix.parts)
        if candidate.resolve() != candidate.absolute():
            return
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
                strict_ownership=True, graceful=not worker.stop_requested,
            )
        if worker.capability is not None:
            if not worker.capability.done():
                worker.capability.cancel()
            await asyncio.gather(worker.capability, return_exceptions=True)
        if worker.created_directory:
            try:
                shutil.rmtree(worker.directory)
            except FileNotFoundError:
                pass
        if worker.proxy_requests is not None:
            await worker.proxy_requests.close()
            worker.proxy_requests = None
        await self._finish_stderr(worker, 2.0)
        async with self._lock:
            if self._workers.get(worker.run_id) is worker:
                self._workers.pop(worker.run_id)

    async def shutdown(self) -> None:
        self._closed = True
        idle = [worker for items in self._idle.values() for worker in items]
        self._idle.clear()
        results = await asyncio.gather(
            *(self.force_stop(identity) for identity in tuple(self._workers)),
            *(self._retire(worker) for worker in idle), *tuple(self._retiring), return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                raise result


# Long enough for a node headline plus the bounded executor reason (event_translation.MAX_REASON_CHARS).
MAX_TERMINAL_REASON_CHARS = 1100


def _terminal_error(status: object, reported: object, secrets: Iterable[str | bytes]) -> dict[str, str]:
    """The worker's own failure reason (remediation M1 R1-03), or a fixed sentence when it is unusable.

    The reason was already shown in the node log; it is re-redacted here because
    the run error is served on more surfaces than the log.
    """
    if isinstance(reported, dict):
        code, text = reported.get("code"), reported.get("message")
        if (isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code)
                and isinstance(text, str) and text.strip() and len(text) <= MAX_TERMINAL_REASON_CHARS):
            return {"code": code, "message": redact_sensitive_text(text.strip(), secrets)}
    return {"code": f"WORKFLOW_{str(status).upper()}", "message": "工作流未完整成功，请查看已提交的节点记录"}


def _protocol_error() -> WorkflowWorkerError:
    return WorkflowWorkerError("WORKFLOW_WORKER_PROTOCOL_INVALID", "执行进程消息无效")
