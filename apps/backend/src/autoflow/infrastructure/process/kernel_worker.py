from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, TypeVar
from uuid import uuid4

from autoflow.application.kernels.operations import (
    TERMINAL_OPERATION_STATES,
    KernelInstallJob,
    KernelOperation,
    transition_operation,
)
from autoflow.domain.kernels.errors import (
    KernelBusy,
    KernelOperationNotFound,
    KernelWorkerUnavailable,
    LicenseValidationUnavailable,
)
from autoflow.domain.kernels.models import LicenseSeats, LicenseStatus
from autoflow.infrastructure.database.kernel_operations import (
    SqlAlchemyKernelOperationRepository,
)
from autoflow.infrastructure.events.kernel_events import KernelEventBroker
from autoflow.infrastructure.filesystem.locking import ExclusiveFileLock
from autoflow.providers.kernel.catalog import (
    current_platform_tag,
    executable_path,
    is_valid_kernel_version,
)

DEFAULT_TERMINATION_TIMEOUT = 3.0
DEFAULT_RPC_TIMEOUT = 20.0
_T = TypeVar("_T")


class KernelWorkerManagerError(KernelWorkerUnavailable):
    pass


class KernelWorkerManagerBusy(KernelBusy):
    pass


class KernelWorkerProtocolError(KernelWorkerManagerError):
    pass


@dataclass(frozen=True)
class ActiveKernelProcess:
    pid: int
    args: tuple[str, ...]


@dataclass
class _RunningWorker:
    process: asyncio.subprocess.Process
    task: asyncio.Task[KernelOperation]
    staging: Path


def kernel_worker_command() -> tuple[str, ...]:
    if getattr(sys, "frozen", False):
        return (sys.executable, "--kernel-worker")
    return (sys.executable, "-m", "autoflow", "--kernel-worker")


class KernelWorkerManager:
    def __init__(
        self,
        *,
        kernels_dir: Path,
        repository: SqlAlchemyKernelOperationRepository,
        events: KernelEventBroker,
        command: tuple[str, ...] | None = None,
        worker_env: dict[str, str] | None = None,
        platform: str | None = None,
        termination_timeout: float = DEFAULT_TERMINATION_TIMEOUT,
        rpc_timeout: float = DEFAULT_RPC_TIMEOUT,
    ) -> None:
        self._kernels_dir = kernels_dir.resolve()
        self._repository = repository
        self._events = events
        self._command = command or kernel_worker_command()
        self._worker_env = worker_env or {}
        self._platform = platform
        self._termination_timeout = termination_timeout
        self._rpc_timeout = rpc_timeout
        self._running: dict[str, _RunningWorker] = {}
        self._rpc_tasks: set[asyncio.Task[Any]] = set()
        self._rpc_processes: set[asyncio.subprocess.Process] = set()
        self._shutting_down = False
        self._lock = asyncio.Lock()
        self._ownership = ExclusiveFileLock(self._kernels_dir / ".install.lock")
        self._cleanup_rpc_cache()

    def recover_interrupted(self) -> list[KernelOperation]:
        if not self._ownership.acquire():
            return []
        recovered: list[KernelOperation] = []
        try:
            for operation in self._repository.list_active():
                failed = transition_operation(
                    operation,
                    "failed",
                    error="应用关闭，安装中断",
                    message="安装中断",
                )
                self._repository.save(failed)
                shutil.rmtree(
                    self._kernels_dir / ".staging" / operation.id, ignore_errors=True
                )
                recovered.append(failed)
            if recovered:
                self._events.publish(self.snapshot())
            return recovered
        finally:
            self._ownership.release()

    async def start(self, job: KernelInstallJob) -> KernelOperation:
        if not is_valid_kernel_version(job.requested_version):
            raise ValueError("invalid kernel version")
        if job.edition == "licensed" and not job.license_key:
            raise ValueError("licensed downloads require a license")
        if job.edition == "public" and job.release_channel != "stable":
            raise ValueError("public downloads require the stable channel")
        async with self._lock:
            if any(item.process.returncode is None for item in self._running.values()):
                raise KernelWorkerManagerBusy()
            if not self._ownership.acquire():
                raise KernelWorkerManagerBusy()
            operation = KernelOperation.new(
                operation_id=str(uuid4()),
                edition=job.edition,
                requested_version=job.requested_version,
                release_channel=job.release_channel,
            )
            staging = self._kernels_dir / ".staging" / operation.id
            process: asyncio.subprocess.Process | None = None
            try:
                self._repository.save(operation)
                self._publish()
                staging.mkdir(parents=True, exist_ok=False)
                env = os.environ.copy()
                env.update(self._worker_env)
                env["CLOAKBROWSER_CACHE_DIR"] = str(staging)
                spawn = asyncio.create_task(
                    asyncio.create_subprocess_exec(
                        *self._command,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                        env=env,
                    )
                )
                try:
                    process = await asyncio.shield(spawn)
                except asyncio.CancelledError:
                    try:
                        process, _ = await _wait_uninterruptibly(spawn)
                    except BaseException:  # noqa: BLE001 -- preserve caller cancellation.
                        process = None
                    raise
                assert process.stdin is not None
                payload = {
                    "command": "download",
                    "cacheDir": str(staging),
                    "edition": job.edition,
                    "requestedVersion": job.requested_version,
                    "releaseChannel": job.release_channel,
                    "licenseKey": job.license_key,
                }
                process.stdin.write((json.dumps(payload) + "\n").encode())
                await process.stdin.drain()
                process.stdin.close()
            except asyncio.CancelledError:
                cleanup = asyncio.create_task(
                    self._compensate_start(
                        operation, staging, process, cancelled=True
                    )
                )
                await _wait_uninterruptibly(cleanup)
                raise
            except Exception:  # noqa: BLE001 -- every setup failure must release ownership.
                cleanup = asyncio.create_task(
                    self._compensate_start(
                        operation, staging, process, cancelled=False
                    )
                )
                _, cancelled_during_cleanup = await _wait_uninterruptibly(cleanup)
                if cancelled_during_cleanup:
                    raise asyncio.CancelledError
                raise KernelWorkerManagerError("Kernel worker could not start") from None
            task = asyncio.create_task(self._monitor(operation.id, process, staging))
            self._running[operation.id] = _RunningWorker(process, task, staging)
            return operation

    async def cancel(self, operation_id: str) -> KernelOperation:
        async with self._lock:
            operation = self._required(operation_id)
            running = self._running.get(operation_id)
            if running is None:
                if operation.state in TERMINAL_OPERATION_STATES:
                    return operation
                raise KernelWorkerManagerBusy()
            if operation.state not in TERMINAL_OPERATION_STATES and operation.state != "cancelling":
                operation = transition_operation(
                    operation, "cancelling", message="正在取消安装"
                )
                self._repository.save(operation)
                self._publish()
        if running is None:
            return operation
        process = running.process
        if process.returncode is None:
            await self._stop_process(process)
        await running.task
        return self._required(operation_id)

    async def wait(self, operation_id: str) -> KernelOperation:
        running = self._running.get(operation_id)
        if running is not None:
            await running.task
        return self._required(operation_id)

    async def wait_for_state(
        self, operation_id: str, state: str, *, timeout: float = 2.0
    ) -> KernelOperation:
        async def wait_until() -> KernelOperation:
            while (operation := self._required(operation_id)).state != state:
                if operation.state in TERMINAL_OPERATION_STATES:
                    return operation
                await asyncio.sleep(0.005)
            return operation

        return await asyncio.wait_for(wait_until(), timeout)

    def get(self, operation_id: str) -> KernelOperation:
        return self._required(operation_id)

    def snapshot(self) -> list[KernelOperation]:
        return self._repository.list()

    def active_processes(self) -> list[ActiveKernelProcess]:
        installs = [
            ActiveKernelProcess(item.process.pid, self._command)
            for item in self._running.values()
            if item.process.returncode is None
        ]
        return installs + [
            ActiveKernelProcess(process.pid, self._command)
            for process in self._rpc_processes
            if process.returncode is None
        ]

    async def shutdown(self) -> None:
        self._shutting_down = True
        rpc_tasks = tuple(self._rpc_tasks)
        for task in rpc_tasks:
            task.cancel()
        if rpc_tasks:
            await asyncio.gather(*rpc_tasks, return_exceptions=True)
        for operation_id in tuple(self._running):
            await self.cancel(operation_id)

    async def licensed_catalog(self) -> list[object]:
        message = await self._rpc("catalog", {})
        releases = message.get("releases")
        if message.get("type") != "catalog" or not isinstance(releases, list):
            raise KernelWorkerProtocolError("Invalid catalog result")
        return releases

    async def validate_license(self, license_key: str) -> LicenseStatus:
        try:
            message = await self._rpc("license", {"licenseKey": license_key})
            raw = message.get("status")
            if message.get("type") != "license" or not isinstance(raw, dict):
                raise KernelWorkerProtocolError("Invalid license result")
            configured = raw.get("configured")
            valid = raw.get("valid")
            if type(configured) is not bool or type(valid) is not bool:
                raise KernelWorkerProtocolError("Invalid license result")
            seats = raw.get("seats")
            parsed_seats = None
            if seats is not None:
                if not isinstance(seats, dict):
                    raise KernelWorkerProtocolError("Invalid license seats")
                parsed_seats = LicenseSeats(
                    _license_optional_int(seats.get("active")),
                    _license_optional_int(seats.get("limit")),
                )
            return LicenseStatus(
                configured=configured,
                valid=valid,
                plan=_optional_message(raw.get("plan")),
                expires=_optional_message(raw.get("expires")),
                seats=parsed_seats,
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 -- no worker detail or secret crosses this boundary.
            raise LicenseValidationUnavailable() from None

    async def _rpc(self, command: str, payload: dict[str, object]) -> dict[str, Any]:
        current = asyncio.current_task()
        assert current is not None
        if self._shutting_down:
            raise KernelWorkerManagerError("Kernel worker manager is shutting down")
        self._rpc_tasks.add(current)
        rpc_id = uuid4().hex
        cache = self._kernels_dir / ".rpc" / rpc_id
        cache_lock = ExclusiveFileLock(cache / ".owner.lock")
        process: asyncio.subprocess.Process | None = None
        try:
            cache.mkdir(parents=True, exist_ok=False)
            if not cache_lock.acquire():
                raise KernelWorkerManagerError("Kernel RPC cache is unavailable")
            env = os.environ.copy()
            env.update(self._worker_env)
            env["CLOAKBROWSER_CACHE_DIR"] = str(cache)
            spawn = asyncio.create_task(
                asyncio.create_subprocess_exec(
                    *self._command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    env=env,
                )
            )
            try:
                process = await asyncio.shield(spawn)
            except asyncio.CancelledError:
                with suppress(BaseException):
                    process, _ = await _wait_uninterruptibly(spawn)
                raise
            self._rpc_processes.add(process)
            command_payload = {"command": command, "cacheDir": str(cache), **payload}
            raw, _ = await asyncio.wait_for(
                process.communicate((json.dumps(command_payload) + "\n").encode()),
                timeout=self._rpc_timeout,
            )
            lines = raw.splitlines()
            if process.returncode != 0 or len(lines) != 1:
                raise KernelWorkerProtocolError("Kernel RPC worker failed")
            message = json.loads(lines[0])
            if not isinstance(message, dict) or message.get("type") == "error":
                raise KernelWorkerProtocolError("Kernel RPC worker failed")
            return message
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            raise KernelWorkerManagerError("Kernel RPC worker timed out") from None
        except KernelWorkerManagerError:
            raise
        except Exception:  # noqa: BLE001 -- child output and spawn errors are untrusted.
            raise KernelWorkerManagerError("Kernel RPC worker failed") from None
        finally:
            if process is not None:
                if process.returncode is None:
                    cleanup = asyncio.create_task(self._stop_process(process))
                    await _wait_uninterruptibly(cleanup)
                self._rpc_processes.discard(process)
            cache_lock.release()
            shutil.rmtree(cache, ignore_errors=True)
            self._rpc_tasks.discard(current)

    def _cleanup_rpc_cache(self) -> None:
        root = self._kernels_dir / ".rpc"
        try:
            entries = list(root.iterdir())
        except FileNotFoundError:
            return
        for entry in entries:
            if not entry.is_dir() or entry.is_symlink():
                continue
            lock = ExclusiveFileLock(entry / ".owner.lock")
            try:
                if not lock.acquire():
                    continue
                lock.release()
                shutil.rmtree(entry, ignore_errors=True)
            except OSError:
                lock.release()

    async def _monitor(
        self,
        operation_id: str,
        process: asyncio.subprocess.Process,
        staging: Path,
    ) -> KernelOperation:
        try:
            assert process.stdout is not None
            async for raw_line in process.stdout:
                try:
                    message = json.loads(raw_line)
                    if not isinstance(message, dict):
                        raise KernelWorkerProtocolError("Worker message must be an object")
                    if message.get("type") == "progress":
                        await self._progress(operation_id, message)
                    elif message.get("type") == "completed":
                        await self._complete(operation_id, staging, message)
                    elif message.get("type") == "error":
                        await self._fail(operation_id, "Kernel worker failed")
                    else:
                        raise KernelWorkerProtocolError("Unknown worker message")
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001 -- child output is an untrusted boundary.
                    await self._fail(operation_id, "Kernel worker protocol error")
                    if process.returncode is None:
                        await self._stop_process(process)
                    break
            return_code = await process.wait()
            async with self._lock:
                operation = self._required(operation_id)
                if operation.state == "cancelling":
                    operation = transition_operation(
                        operation, "cancelled", message="安装已取消"
                    )
                    self._repository.save(operation)
                    self._publish()
                elif operation.state not in TERMINAL_OPERATION_STATES:
                    operation = transition_operation(
                        operation,
                        "failed",
                        error="Kernel worker exited unexpectedly",
                        message="安装失败",
                    )
                    self._repository.save(operation)
                    self._publish()
                elif return_code != 0 and operation.state == "completed":
                    # Completion is committed atomically; later process teardown cannot undo it.
                    pass
                return operation
        finally:
            if process.returncode is None:
                await self._stop_process(process)
            shutil.rmtree(staging, ignore_errors=True)
            self._running.pop(operation_id, None)
            self._ownership.release()

    async def _progress(self, operation_id: str, message: dict[str, Any]) -> None:
        state = message.get("state")
        if state not in {"downloading", "verifying", "extracting"}:
            raise KernelWorkerProtocolError("Invalid progress state")
        async with self._lock:
            operation = self._required(operation_id)
            if operation.state == "cancelling":
                return
            operation = transition_operation(
                operation,
                state,
                progress=message.get("progress"),
                message=_optional_message(message.get("message")),
            )
            self._repository.save(operation)
            self._publish()

    async def _complete(
        self, operation_id: str, staging: Path, message: dict[str, Any]
    ) -> None:
        async with self._lock:
            operation = self._required(operation_id)
            if operation.state == "cancelling":
                return
            if operation.state != "extracting":
                raise KernelWorkerProtocolError("Worker completed out of order")
            resolved_version = message.get("resolvedVersion")
            relative_executable = message.get("executableRelativePath")
            if not isinstance(resolved_version, str) or not isinstance(
                relative_executable, str
            ):
                raise KernelWorkerProtocolError("Incomplete worker result")
            self._publish_install(
                operation, staging, resolved_version, relative_executable
            )
            completed = transition_operation(
                operation,
                "completed",
                resolved_version=resolved_version,
                message="安装完成",
            )
            self._repository.save(completed)
            self._publish()

    async def _fail(self, operation_id: str, error: str) -> None:
        async with self._lock:
            operation = self._required(operation_id)
            if operation.state in TERMINAL_OPERATION_STATES or operation.state == "cancelling":
                return
            failed = transition_operation(
                operation, "failed", error=error, message="安装失败"
            )
            self._repository.save(failed)
            self._publish()

    def _publish_install(
        self,
        operation: KernelOperation,
        staging: Path,
        resolved_version: str,
        relative_executable: str,
    ) -> None:
        if not is_valid_kernel_version(resolved_version):
            raise KernelWorkerProtocolError("Invalid resolved version")
        relative = PurePath(relative_executable)
        if relative.is_absolute() or ".." in relative.parts or len(relative.parts) < 2:
            raise KernelWorkerProtocolError("Invalid executable path")
        suffix = "-pro" if operation.edition == "licensed" else ""
        directory_name = f"chromium-{resolved_version}{suffix}"
        if relative.parts[0] != directory_name:
            raise KernelWorkerProtocolError("Installation identity mismatch")
        source = staging / directory_name
        reported_executable = staging.joinpath(*relative.parts)
        platform = self._platform or current_platform_tag()
        expected_executable = executable_path(source, platform)
        if reported_executable.resolve() != expected_executable.resolve():
            raise KernelWorkerProtocolError("Unexpected executable path")
        self._validate_tree(source, expected_executable)
        target = self._kernels_dir / directory_name
        if target.exists() or target.is_symlink():
            self._validate_tree(target, executable_path(target, platform))
            return
        self._kernels_dir.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
        self._validate_tree(target, executable_path(target, platform))

    @staticmethod
    def _validate_tree(root: Path, executable: Path) -> None:
        if not root.is_dir() or root.is_symlink() or not executable.is_file():
            raise KernelWorkerProtocolError("Incomplete installation")
        resolved_root = root.resolve()
        try:
            executable.resolve().relative_to(resolved_root)
            for item in root.rglob("*"):
                if item.is_symlink():
                    item.resolve().relative_to(resolved_root)
        except (OSError, ValueError):
            raise KernelWorkerProtocolError("Installation escapes staging") from None

    def _required(self, operation_id: str) -> KernelOperation:
        operation = self._repository.get(operation_id)
        if operation is None:
            raise KernelOperationNotFound(operation_id)
        return operation

    async def _stop_process(self, process: asyncio.subprocess.Process) -> None:
        try:
            process.terminate()
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(
                asyncio.shield(process.wait()), self._termination_timeout
            )
        except TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()

    async def _compensate_start(
        self,
        operation: KernelOperation,
        staging: Path,
        process: asyncio.subprocess.Process | None,
        *,
        cancelled: bool,
    ) -> None:
        try:
            if process is not None:
                if process.stdin is not None:
                    with suppress(Exception):
                        process.stdin.close()
                if process.returncode is None:
                    await self._stop_process(process)
            shutil.rmtree(staging, ignore_errors=True)
            failed = transition_operation(
                operation,
                "failed",
                error=(
                    "Kernel worker start was cancelled"
                    if cancelled
                    else "Kernel worker could not start"
                ),
            )
            self._repository.save(failed)
            self._publish()
        finally:
            self._ownership.release()

    def _publish(self) -> None:
        self._events.publish(self.snapshot())


def _optional_message(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _license_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise KernelWorkerProtocolError("Invalid license seats")
    return value


async def _wait_uninterruptibly(task: asyncio.Task[_T]) -> tuple[_T, bool]:
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    return task.result(), cancelled
