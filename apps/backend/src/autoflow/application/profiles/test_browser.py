import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4

from autoflow.domain.kernels.errors import LicenseInvalid
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.errors import (
    KernelNotInstalled,
    ProfileTestBrowserBusy,
    ProfileTestBrowserUnavailable,
)
from autoflow.domain.profiles.models import (
    Profile,
    ProfileBrowserProxy,
    ProfileTestBrowserSession,
    ProfileTestBrowserStatus,
)
from autoflow.domain.profiles.ports import ProfileTestBrowserLauncher

from .service import ProfileService


@dataclass
class _StartOperation:
    task: asyncio.Task[object]
    state: Literal["starting", "stopping"] = "starting"


class ProfileTestBrowserService:
    def __init__(
        self,
        profiles: ProfileService,
        installed_kernels: Callable[[], Sequence[InstalledKernel]],
        resolve_proxy: Callable[[Profile, str], Awaitable[ProfileBrowserProxy | None]],
        read_license: Callable[[], str | None],
        launcher: ProfileTestBrowserLauncher,
    ) -> None:
        self._profiles = profiles
        self._installed_kernels = installed_kernels
        self._resolve_proxy = resolve_proxy
        self._read_license = read_license
        self._launcher = launcher
        self._starts: dict[str, _StartOperation] = {}
        self._closes: dict[str, asyncio.Task[None]] = {}
        self._lock = Lock()

    async def start(self, profile_id: str) -> ProfileTestBrowserSession:
        current = asyncio.current_task()
        assert current is not None
        with self._lock:
            if (
                profile_id in self._starts
                or profile_id in self._closes
                or any(item.profile_id == profile_id for item in self._launcher.statuses())
            ):
                raise ProfileTestBrowserBusy
            operation = _StartOperation(current)
            self._starts[profile_id] = operation
        try:
            try:
                async with asyncio.timeout(110):
                    profile = self._profiles.get(profile_id)
                    executable = self._kernel_executable(profile)
                    session_id = str(uuid4())
                    proxy = await self._resolve_proxy(profile, session_id)
                    license_key = (
                        self._read_license()
                        if profile.spec.browser_edition == "licensed"
                        else None
                    )
                    if profile.spec.browser_edition == "licensed" and not license_key:
                        raise LicenseInvalid
                    return await self._launcher.start(
                        session_id, profile, executable, proxy, license_key
                    )
            except TimeoutError:
                raise ProfileTestBrowserUnavailable from None
        except asyncio.CancelledError:
            with self._lock:
                stopped_by_request = operation.state == "stopping"
            if stopped_by_request:
                raise ProfileTestBrowserUnavailable from None
            raise
        finally:
            with self._lock:
                if (
                    self._starts.get(profile_id) is operation
                    and operation.state == "starting"
                ):
                    self._starts.pop(profile_id, None)

    async def stop(self, profile_id: str) -> None:
        with self._lock:
            closing = self._closes.get(profile_id)
            if closing is None:
                operation = self._starts.get(profile_id)
                active = any(
                    item.profile_id == profile_id for item in self._launcher.statuses()
                )
                if operation is None and not active:
                    return
                if operation is not None:
                    operation.state = "stopping"
                closing = asyncio.create_task(
                    self._close(profile_id, operation),
                    name=f"close-test-browser-{profile_id}",
                )
                self._closes[profile_id] = closing
        await asyncio.shield(closing)

    def statuses(self) -> list[ProfileTestBrowserStatus]:
        items = {item.profile_id: item for item in self._launcher.statuses()}
        with self._lock:
            for profile_id, operation in self._starts.items():
                current = items.get(profile_id)
                if operation.state == "stopping":
                    items[profile_id] = ProfileTestBrowserStatus(
                        profile_id,
                        current.session_id if current else None,
                        "stopping",
                    )
                elif current is None:
                    items[profile_id] = ProfileTestBrowserStatus(
                        profile_id, None, "starting"
                    )
            for profile_id in self._closes:
                current = items.get(profile_id)
                items[profile_id] = ProfileTestBrowserStatus(
                    profile_id,
                    current.session_id if current is not None else None,
                    "stopping",
                )
        return sorted(items.values(), key=lambda item: item.profile_id)

    def active(self, profile_id: str) -> bool:
        return any(item.profile_id == profile_id for item in self.statuses())

    async def _close(
        self, profile_id: str, operation: _StartOperation | None
    ) -> None:
        current = asyncio.current_task()
        try:
            if operation is not None:
                operation.task.cancel()
                await asyncio.gather(operation.task, return_exceptions=True)
            await self._launcher.stop(profile_id)
        finally:
            with self._lock:
                if self._starts.get(profile_id) is operation:
                    self._starts.pop(profile_id, None)
                if self._closes.get(profile_id) is current:
                    self._closes.pop(profile_id, None)

    def _kernel_executable(self, profile: Profile) -> Path:
        for kernel in self._installed_kernels():
            if (
                kernel.edition == profile.spec.browser_edition
                and kernel.version == profile.spec.browser_version
            ):
                return kernel.executable_path
        raise KernelNotInstalled
