from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import (
    Profile,
    ProfileBrowserProxy,
    ProfileTestBrowserSession,
    ProfileTestBrowserStatus,
)


class ProfileRepository(Protocol):
    def add(self, profile: Profile) -> None: ...
    def get(self, profile_id: str) -> Profile | None: ...
    def list(self) -> list[Profile]: ...
    def update(self, profile: Profile) -> None: ...
    def remove(self, profile_id: str) -> None: ...


class InstalledKernelLookup(Protocol):
    def is_installed(self, edition: str, version: str) -> bool: ...


@dataclass(frozen=True)
class ProxyOptionRecord:
    id: str
    name: str
    enabled: bool


@dataclass(frozen=True)
class ProxyPoolOptionRecord:
    id: str
    name: str


class ProxyOptionsLookup(Protocol):
    def list_proxies(self) -> list[ProxyOptionRecord]: ...
    def list_pools(self) -> list[ProxyPoolOptionRecord]: ...
    def proxy_is_available(self, proxy_id: str) -> bool: ...
    def pool_exists(self, pool_id: str) -> bool: ...


class ProfileDataStore(Protocol):
    def stage(self, profile_id: str) -> str | None: ...
    def restore(self, profile_id: str, token: str) -> None: ...
    def purge(self, token: str) -> None: ...
    def retry_pending(self, profile_exists: Callable[[str], bool]) -> None: ...


class ProfileUsageGuard(Protocol):
    def guard(self, profile_id: str) -> AbstractContextManager[None]: ...


class ProfileTestBrowserLauncher(Protocol):
    async def start(
        self,
        session_id: str,
        profile: Profile,
        executable: Path,
        proxy: ProfileBrowserProxy | None,
        license_key: str | None,
    ) -> ProfileTestBrowserSession: ...

    async def stop(self, profile_id: str) -> None: ...

    def statuses(self) -> list[ProfileTestBrowserStatus]: ...


@dataclass(frozen=True)
class EnvironmentOption:
    value: str
    label: str


@dataclass(frozen=True)
class ProfileEnvironmentOptions:
    locales: list[EnvironmentOption]
    timezones: list[EnvironmentOption]
    user_agent_templates: list[EnvironmentOption]
