import asyncio
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from threading import Lock
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
)
from autoflow.domain.profiles.ports import ProfileTestBrowserLauncher

from .service import ProfileService


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
        self._starting: set[str] = set()
        self._lock = Lock()

    async def start(self, profile_id: str) -> ProfileTestBrowserSession:
        with self._lock:
            if profile_id in self._starting:
                raise ProfileTestBrowserBusy
            self._starting.add(profile_id)
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
        finally:
            with self._lock:
                self._starting.discard(profile_id)

    def _kernel_executable(self, profile: Profile) -> Path:
        for kernel in self._installed_kernels():
            if (
                kernel.edition == profile.spec.browser_edition
                and kernel.version == profile.spec.browser_version
            ):
                return kernel.executable_path
        raise KernelNotInstalled
