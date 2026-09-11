from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Any, Literal
from uuid import uuid4

from autoflow.application.kernels.operations import (
    TERMINAL_OPERATION_STATES,
    KernelOperation,
    transition_operation,
)
from autoflow.infrastructure.database.kernel_operations import (
    SqlAlchemyKernelOperationRepository,
)
from autoflow.infrastructure.events.kernel_events import KernelEventBroker
from autoflow.providers.kernel.catalog import (
    current_platform_tag,
    executable_path,
    is_valid_kernel_version,
)

DEFAULT_TERMINATION_TIMEOUT = 3.0


class KernelWorkerManagerError(RuntimeError):
    code = "KERNEL_WORKER_ERROR"


class KernelWorkerManagerBusy(KernelWorkerManagerError):
    code = "KERNEL_BUSY"


class KernelOperationNotFound(KernelWorkerManagerError):
    code = "KERNEL_OPERATION_NOT_FOUND"


class KernelWorkerProtocolError(KernelWorkerManagerError):
    pass


@dataclass(frozen=True)
class KernelInstallJob:
    edition: Literal["public", "licensed"]
    requested_version: str
    release_channel: Literal["stable", "preview"]
    license_key: str | None = field(default=None, repr=False)


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
    ) -> None:
        self._kernels_dir = kernels_dir.resolve()
        self._repository = repository
        self._events = events
        self._command = command or kernel_worker_command()
        self._worker_env = worker_env or {}
        self._platform = platform
        self._termination_timeout = termination_timeout
        self._running: dict[str, _RunningWorker] = {}
        self._lock = asyncio.Lock()

    def recover_interrupted(self) -> list[KernelOperation]:
        recovered: list[KernelOperation] = []
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

    async def start(self, job: KernelInstallJob) -> KernelOperation:
        if not is_valid_kernel_version(job.requested_version):
            raise ValueError("invalid kernel version")
        if job.edition == "licensed" and not job.license_key:
            raise ValueError("licensed downloads require a license")
        if job.edition == "public" and job.release_channel != "stable":
            raise ValueError("public downloads require the stable channel")
        async with self._lock:
            if any(item.process.returncode is None for item in self._running.values()):
                raise KernelWorkerManagerBusy("A kernel installation is already active")
            operation = KernelOperation.new(
                operation_id=str(uuid4()),
                edition=job.edition,
                requested_version=job.requested_version,
                release_channel=job.release_channel,
            )
            self._repository.save(operation)
            self._publish()
            staging = self._kernels_dir / ".staging" / operation.id
            staging.mkdir(parents=True, exist_ok=False)
            env = os.environ.copy()
            env.update(self._worker_env)
            env["CLOAKBROWSER_CACHE_DIR"] = str(staging)
            try:
                process = await asyncio.create_subprocess_exec(
                    *self._command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    env=env,
                )
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                failed = transition_operation(
                    operation, "failed", error="Kernel worker could not start"
                )
                self._repository.save(failed)
                self._publish()
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
            try:
                process.stdin.write((json.dumps(payload) + "\n").encode())
                await process.stdin.drain()
                process.stdin.close()
            except Exception as error:
                process.stdin.close()
                await self._stop_process(process)
                shutil.rmtree(staging, ignore_errors=True)
                failed = transition_operation(
                    operation, "failed", error="Kernel worker could not start"
                )
                self._repository.save(failed)
                self._publish()
                raise KernelWorkerManagerError("Kernel worker could not start") from error
            task = asyncio.create_task(self._monitor(operation.id, process, staging))
            self._running[operation.id] = _RunningWorker(process, task, staging)
            return operation

    async def cancel(self, operation_id: str) -> KernelOperation:
        async with self._lock:
            operation = self._required(operation_id)
            if operation.state in TERMINAL_OPERATION_STATES:
                return operation
            running = self._running.get(operation_id)
            if operation.state != "cancelling":
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
        return [
            ActiveKernelProcess(item.process.pid, self._command)
            for item in self._running.values()
            if item.process.returncode is None
        ]

    async def shutdown(self) -> None:
        for operation_id in tuple(self._running):
            await self.cancel(operation_id)

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
            shutil.rmtree(staging, ignore_errors=True)
            self._running.pop(operation_id, None)

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

    def _publish(self) -> None:
        self._events.publish(self.snapshot())


def _optional_message(value: object) -> str | None:
    return value if isinstance(value, str) else None
