from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from autoflow.domain.profiles.errors import (
    ProfileTestBrowserBusy,
    ProfileTestBrowserUnavailable,
)
from autoflow.domain.profiles.models import (
    Profile,
    ProfileBrowserProxy,
    ProfileTestBrowserSession,
    ProfileTestBrowserStatus,
)
from autoflow.infrastructure.process.project_browser_processes import (
    OwnedProcesses,
    capture_processes,
    living_processes,
    process_birth,
    signal_processes,
)

__test__ = False

DEFAULT_START_TIMEOUT = 90.0
DEFAULT_TERMINATION_TIMEOUT = 3.0


def test_browser_worker_command() -> tuple[str, ...]:
    if getattr(sys, "frozen", False):
        return (sys.executable, "--test-browser-worker")
    return (sys.executable, "-m", "autoflow", "--test-browser-worker")


@dataclass
class _RunningBrowser:
    profile_id: str
    process: asyncio.subprocess.Process
    directory: Path
    monitor: asyncio.Task[None]


class TestBrowserWorkerManager:
    def __init__(
        self,
        temp_dir: Path,
        *,
        command: tuple[str, ...] | None = None,
        worker_env: dict[str, str] | None = None,
        start_timeout: float = DEFAULT_START_TIMEOUT,
        termination_timeout: float = DEFAULT_TERMINATION_TIMEOUT,
    ) -> None:
        self._base = (temp_dir / "test-browser").resolve()
        self._root = self._base / uuid4().hex
        self._command = command or test_browser_worker_command()
        self._worker_env = worker_env or {}
        self._start_timeout = start_timeout
        self._termination_timeout = termination_timeout
        self._starting: dict[str, asyncio.subprocess.Process | None] = {}
        self._starting_sessions: dict[str, str] = {}
        self._sessions: dict[str, _RunningBrowser] = {}
        self._stopping: set[str] = set()
        self._shutting_down = False
        self._lock = asyncio.Lock()
        self._start_tasks: dict[str, asyncio.Task[Any]] = {}
        self._stop_tasks: dict[str, asyncio.Task[None]] = {}
        self._births: dict[int, int | None] = {}
        self._executables: dict[int, Path] = {}

    async def start(
        self,
        session_id: str,
        profile: Profile,
        executable: Path,
        proxy: ProfileBrowserProxy | None,
        license_key: str | None,
    ) -> ProfileTestBrowserSession:
        directory = self._root / session_id
        process: asyncio.subprocess.Process | None = None
        current = asyncio.current_task()
        assert current is not None
        async with self._lock:
            if self._shutting_down:
                raise ProfileTestBrowserUnavailable
            if (
                profile.id in self._starting
                or profile.id in self._stopping
                or self._session_for_profile(profile.id) is not None
            ):
                raise ProfileTestBrowserBusy
            self._starting[profile.id] = None
            self._starting_sessions[profile.id] = session_id
            self._start_tasks[profile.id] = current
        try:
            directory.mkdir(parents=True, exist_ok=False)
            env = os.environ.copy()
            env.update(self._worker_env)
            env.pop("CLOAKBROWSER_LICENSE_KEY", None)
            env["CLOAKBROWSER_BINARY_PATH"] = str(executable.resolve(strict=True))
            env["CLOAKBROWSER_CACHE_DIR"] = str(directory)
            env.update(
                {"TMPDIR": str(directory), "TMP": str(directory), "TEMP": str(directory)}
            )
            spawn = asyncio.create_task(
                asyncio.create_subprocess_exec(
                    *self._command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    env=env,
                    **_process_group_options(),
                )
            )
            try:
                process = await asyncio.shield(spawn)
            except asyncio.CancelledError:
                try:
                    process = await _wait_for_spawn(spawn)
                    self._births[process.pid] = process_birth(process.pid) if sys.platform != "win32" else None
                    self._executables[process.pid] = executable
                except BaseException:  # noqa: BLE001 -- preserve cancellation.
                    process = None
                raise
            self._births[process.pid] = process_birth(process.pid) if sys.platform != "win32" else None
            self._executables[process.pid] = executable
            async with self._lock:
                if self._shutting_down:
                    raise ProfileTestBrowserUnavailable
                self._starting[profile.id] = process
            assert process.stdin is not None and process.stdout is not None
            payload = browser_worker_payload(session_id, profile, proxy, license_key)
            process.stdin.write((json.dumps(payload) + "\n").encode())
            await process.stdin.drain()
            raw = await asyncio.wait_for(
                process.stdout.readline(), timeout=self._start_timeout
            )
            message = json.loads(raw)
            if (
                process.returncode is not None
                or not isinstance(message, dict)
                or message.get("type") != "ready"
                or message.get("sessionId") != session_id
                or message.get("profileId") != profile.id
                or message.get("fingerprintSeed") != profile.fingerprint_seed
            ):
                raise ProfileTestBrowserUnavailable
            warning = message.get("warning")
            if warning is not None and not isinstance(warning, str):
                raise ProfileTestBrowserUnavailable
            monitor = asyncio.create_task(
                self._monitor(session_id, profile.id, process, directory)
            )
            async with self._lock:
                if self._shutting_down:
                    monitor.cancel()
                    raise ProfileTestBrowserUnavailable
                self._starting.pop(profile.id, None)
                self._starting_sessions.pop(profile.id, None)
                self._start_tasks.pop(profile.id, None)
                self._stopping.discard(profile.id)
                self._sessions[session_id] = _RunningBrowser(
                    profile.id, process, directory, monitor
                )
            return ProfileTestBrowserSession(
                session_id, profile.id, profile.fingerprint_seed, warning
            )
        except ProfileTestBrowserBusy:
            raise
        except BaseException as error:
            async with self._lock:
                self._stopping.add(profile.id)
            if process is not None:
                cleanup = asyncio.create_task(self._stop_process_tree(process, directory))
                await wait_for_cleanup(cleanup)
            shutil.rmtree(directory, ignore_errors=True)
            async with self._lock:
                self._starting.pop(profile.id, None)
                self._starting_sessions.pop(profile.id, None)
                self._stopping.discard(profile.id)
            if isinstance(error, asyncio.CancelledError):
                raise
            raise ProfileTestBrowserUnavailable from None
        finally:
            async with self._lock:
                if self._start_tasks.get(profile.id) is current:
                    self._start_tasks.pop(profile.id, None)

    async def stop(self, profile_id: str) -> None:
        async with self._lock:
            closing = self._stop_tasks.get(profile_id)
            if closing is None:
                starting = self._start_tasks.get(profile_id)
                session = self._session_for_profile(profile_id)
                process = self._starting.get(profile_id)
                if starting is None and session is None and process is None:
                    return
                self._stopping.add(profile_id)
                if starting is None and session is None:
                    assert process is not None
                    closing = asyncio.create_task(self._stop_pending_start(profile_id, process))
                elif starting is not None:
                    starting.cancel()
                    closing = asyncio.create_task(
                        self._wait_for_start_cleanup(profile_id, starting),
                        name=f"stop-starting-test-browser-{profile_id}",
                    )
                else:
                    assert session is not None
                    closing = asyncio.create_task(
                        self._stop_running(session),
                        name=f"stop-test-browser-{profile_id}",
                    )
                self._stop_tasks[profile_id] = closing
        await asyncio.shield(closing)

    def statuses(self) -> list[ProfileTestBrowserStatus]:
        items = [
            ProfileTestBrowserStatus(
                profile_id,
                self._starting_sessions.get(profile_id),
                "stopping" if profile_id in self._stopping else "starting",
            )
            for profile_id in self._starting
        ]
        items.extend(
            ProfileTestBrowserStatus(
                item.profile_id,
                session_id,
                "stopping" if item.profile_id in self._stopping else "running",
            )
            for session_id, item in self._sessions.items()
        )
        return sorted(items, key=lambda item: item.profile_id)

    def active_processes(self) -> list[int]:
        processes = [process for process in self._starting.values() if process]
        processes.extend(item.process for item in self._sessions.values())
        return [process.pid for process in processes if process.returncode is None]

    def busy(self) -> bool:
        return bool(self._starting or self._sessions)

    async def shutdown(self) -> None:
        async with self._lock:
            self._shutting_down = True
            profiles = set(self._starting) | {item.profile_id for item in self._sessions.values()}
        await asyncio.gather(*(self.stop(profile_id) for profile_id in profiles), return_exceptions=True)
        if self.busy():
            raise ProfileTestBrowserUnavailable
        shutil.rmtree(self._root, ignore_errors=True)
        try:
            self._base.rmdir()
        except OSError:
            pass

    async def _monitor(
        self,
        session_id: str,
        profile_id: str,
        process: asyncio.subprocess.Process,
        directory: Path,
    ) -> None:
        try:
            await process.wait()
            # A clean worker exit does not prove that Chromium descendants exited.
            await self._force_process_tree(process, directory)
        except Exception:  # noqa: BLE001 -- retain session ownership for an explicit stop retry.
            async with self._lock:
                self._stopping.add(profile_id)
            return
        shutil.rmtree(directory, ignore_errors=True)
        async with self._lock:
            self._sessions.pop(session_id, None)
            self._stopping.discard(profile_id)

    async def _stop_pending_start(self, profile_id: str, process: asyncio.subprocess.Process) -> None:
        directory = self._root / self._starting_sessions[profile_id]
        try:
            await self._stop_process_tree(process, directory)
            shutil.rmtree(directory, ignore_errors=True)
            async with self._lock:
                self._starting.pop(profile_id, None)
                self._starting_sessions.pop(profile_id, None)
                self._stopping.discard(profile_id)
        finally:
            async with self._lock:
                self._stop_tasks.pop(profile_id, None)

    async def _wait_for_start_cleanup(
        self, profile_id: str, task: asyncio.Task[Any]
    ) -> None:
        try:
            await asyncio.gather(task, return_exceptions=True)
            if profile_id in self._starting:
                raise ProfileTestBrowserUnavailable
        finally:
            async with self._lock:
                if profile_id not in self._starting:
                    self._stopping.discard(profile_id)
                if self._stop_tasks.get(profile_id) is asyncio.current_task():
                    self._stop_tasks.pop(profile_id, None)

    async def _stop_running(self, session: _RunningBrowser) -> None:
        try:
            await self._stop_process_tree(session.process, session.directory)
            await session.monitor
            shutil.rmtree(session.directory, ignore_errors=True)
            async with self._lock:
                for session_id, item in list(self._sessions.items()):
                    if item is session:
                        self._sessions.pop(session_id, None)
                self._stopping.discard(session.profile_id)
        finally:
            async with self._lock:
                if self._stop_tasks.get(session.profile_id) is asyncio.current_task():
                    self._stop_tasks.pop(session.profile_id, None)

    def _session_for_profile(self, profile_id: str) -> _RunningBrowser | None:
        return next(
            (item for item in self._sessions.values() if item.profile_id == profile_id),
            None,
        )

    async def _stop_process_tree(self, process: asyncio.subprocess.Process, directory: Path | None = None) -> None:
        await stop_process_tree(process, self._termination_timeout, directory,
                                self._executables.get(process.pid), self._births.get(process.pid))
        self._births.pop(process.pid, None)
        self._executables.pop(process.pid, None)

    async def _force_process_tree(self, process: asyncio.subprocess.Process, directory: Path | None = None) -> None:
        await force_process_tree(process, self._termination_timeout, directory,
                                 self._executables.get(process.pid), self._births.get(process.pid))
        self._births.pop(process.pid, None)
        self._executables.pop(process.pid, None)


def browser_worker_payload(
    session_id: str,
    profile: Profile,
    proxy: ProfileBrowserProxy | None,
    license_key: str | None,
) -> dict[str, Any]:
    spec = profile.spec
    return {
        "sessionId": session_id,
        "profileId": profile.id,
        "fingerprintSeed": profile.fingerprint_seed,
        "startUrl": spec.start_url,
        "locale": spec.locale,
        "timezone": spec.timezone,
        "geoip": spec.geoip,
        "humanize": spec.humanize,
        "humanPreset": spec.human_preset,
        "userAgent": spec.user_agent,
        "viewport": spec.viewport,
        "colorScheme": spec.color_scheme,
        "extensionPaths": spec.extension_paths,
        "expertArgs": spec.expert_args,
        "browserVersion": spec.browser_version,
        "releaseChannel": spec.release_channel,
        "proxy": (
            {"server": proxy.server, "username": proxy.username, "password": proxy.password}
            if proxy
            else None
        ),
        "licenseKey": license_key,
    }


def _process_group_options() -> dict[str, Any]:
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


async def _wait_for_spawn(
    task: asyncio.Task[asyncio.subprocess.Process],
) -> asyncio.subprocess.Process:
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()


async def wait_for_cleanup(task: asyncio.Task[Any]) -> Any:
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()


async def stop_process_tree(
    process: asyncio.subprocess.Process, termination_timeout: float,
    directory: Path | None = None, executable: Path | None = None, birth: int | None = None,
) -> None:
    owned = await asyncio.to_thread(capture_processes, process.pid, birth, directory, executable) if sys.platform != "win32" else {}
    if process.stdin is not None:
        process.stdin.close()
    if process.returncode is None:
        try:
            await asyncio.wait_for(
                asyncio.shield(process.wait()), termination_timeout
            )
        except TimeoutError:
            pass
    await force_process_tree(process, termination_timeout, directory, executable, birth, owned)


async def force_process_tree(
    process: asyncio.subprocess.Process, termination_timeout: float,
    directory: Path | None = None, executable: Path | None = None, birth: int | None = None,
    owned: OwnedProcesses | None = None, *, strict_ownership: bool = False,
) -> None:
    if sys.platform == "win32":
        killer = await asyncio.create_subprocess_exec(
            "taskkill", "/pid", str(process.pid), "/t", "/f",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.wait()
        if process.returncode is None:
            try:
                process.kill()
            except (PermissionError, ProcessLookupError):
                await asyncio.wait_for(process.wait(), termination_timeout)
            await process.wait()
        return
    owned = await asyncio.to_thread(capture_processes, process.pid, birth, directory, executable, owned, strict_ownership=strict_ownership)
    await asyncio.to_thread(signal_processes, owned, signal.SIGTERM)
    if process.returncode is None:
        try:
            await asyncio.wait_for(asyncio.shield(process.wait()), termination_timeout)
        except TimeoutError:
            pass
    owned = await asyncio.to_thread(capture_processes, process.pid, birth, directory, executable, owned, strict_ownership=strict_ownership)
    await asyncio.to_thread(signal_processes, owned, signal.SIGKILL)
    if process.returncode is None:
        # A missing native identity must retain cleanup ownership, never hang shutdown.
        # Do not signal an unverified PID; a retry can capture its startup identity.
        try:
            await asyncio.wait_for(asyncio.shield(process.wait()), termination_timeout)
        except TimeoutError:
            raise RuntimeError("Worker identity or process exit is not yet confirmed") from None
    deadline = asyncio.get_running_loop().time() + max(termination_timeout, 2)
    while await asyncio.to_thread(living_processes, owned):
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError("Browser process tree cleanup did not finish")
        await asyncio.sleep(0.01)
