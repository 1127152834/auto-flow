"""CloakBrowser adapters with explicit worker-only wrapper entry points.

Task 5 must set ``CLOAKBROWSER_CACHE_DIR`` to its task-specific staging directory
before calling ``load_licensed_catalog``, ``validate_license_with_wrapper``, or
``download_with_wrapper``. The sidecar process supplies those calls through the
injected ports and must never import the stateful wrapper directly.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import httpx

from autoflow.domain.kernels.errors import (
    KernelVersionInvalid,
    LicenseInUse,
    LicenseInvalid,
    LicenseValidationUnavailable,
)
from autoflow.domain.kernels.models import (
    InstalledKernel,
    KernelCatalog,
    LicenseSeats,
    LicenseStatus,
)
from autoflow.domain.kernels.ports import LicenseStore, LicenseValidator

from .catalog import (
    current_platform_tag,
    is_valid_kernel_version,
    merge_catalog,
    parse_licensed_catalog,
    parse_public_catalog,
    scan_installed_kernels,
)

GITHUB_RELEASES_URL = "https://api.github.com/repos/CloakHQ/CloakBrowser/releases"
WRAPPER_VERSION = "0.5.9"


class _Response(Protocol):
    def raise_for_status(self) -> _Response: ...
    def json(self) -> object: ...


class _HttpClient(Protocol):
    async def get(self, url: str, **kwargs: object) -> _Response: ...


class CloakBrowserCatalogProvider:
    def __init__(
        self,
        kernels_dir: Path,
        *,
        licensed_catalog: Callable[[], Sequence[object]],
        platform: str | None = None,
        client: _HttpClient | None = None,
    ) -> None:
        self._kernels_dir = kernels_dir
        self._platform = platform or current_platform_tag()
        self._client = client
        self._licensed_catalog = licensed_catalog

    def installed(self) -> list[InstalledKernel]:
        return scan_installed_kernels(self._kernels_dir, platform=self._platform)

    def is_installed(self, edition: str, version: str) -> bool:
        return any(
            item.edition == edition and item.version == version for item in self.installed()
        )

    async def catalog(self) -> KernelCatalog:
        installed = self.installed()
        releases = []
        failed = False
        try:
            payload = await self._fetch_public_releases()
            releases.extend(parse_public_catalog(payload, platform=self._platform))
        except Exception:  # noqa: BLE001 -- sanitize every remote/parser failure.
            failed = True
        try:
            licensed = await asyncio.to_thread(self._licensed_catalog)
            releases.extend(parse_licensed_catalog(licensed))
        except Exception:  # noqa: BLE001 -- wrapper failures are not typed.
            failed = True
        return KernelCatalog(
            wrapper_version=WRAPPER_VERSION,
            platform=self._platform,
            releases=tuple(merge_catalog(releases, installed)),
            installed=tuple(installed),
            catalog_error="CloakBrowser catalog is unavailable" if failed else None,
        )

    async def _fetch_public_releases(self) -> object:
        params = {"per_page": 100}
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "AutoFlow/0.1",
        }
        if self._client is not None:
            response = await self._client.get(
                GITHUB_RELEASES_URL, params=params, headers=headers
            )
        else:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(
                    GITHUB_RELEASES_URL, params=params, headers=headers
                )
        response.raise_for_status()
        return response.json()


def load_licensed_catalog() -> list[object]:
    """Worker-only: call after setting its task-specific cache, before wrapper import."""
    from cloakbrowser.license import (  # type: ignore[import-untyped]
        get_pro_latest_release,
    )

    return [
        info
        for channel in ("stable", "preview")
        if (info := get_pro_latest_release(channel)) is not None
    ]


def validate_license_with_wrapper(license_key: str) -> LicenseStatus:
    """Worker-only: validate after setting its task-specific cache, before import."""
    try:
        from cloakbrowser import validate_license  # type: ignore[import-untyped]
        from cloakbrowser.license import get_session_seats

        info = validate_license(license_key)
    except Exception:  # noqa: BLE001 -- wrapper errors must not expose the key.
        raise LicenseValidationUnavailable() from None
    if info is None:
        raise LicenseValidationUnavailable()
    seats = None
    if info is not None and bool(getattr(info, "valid", False)):
        try:
            seats = get_session_seats(license_key)
        except Exception:  # noqa: BLE001 -- missing seat data does not invalidate a key.
            seats = None
    return parse_license_status(info, seats=seats, configured=True)


def download_with_wrapper(
    *,
    license_key: str | None,
    browser_version: str | None,
    release_channel: str,
) -> str:
    """Worker-only: download after setting its task-specific cache, before import."""
    if browser_version is not None and not is_valid_kernel_version(browser_version):
        raise KernelVersionInvalid()
    from cloakbrowser import ensure_binary as wrapper_ensure_binary

    return str(
        wrapper_ensure_binary(
            license_key=license_key,
            browser_version=browser_version,
            release_channel=release_channel,
        )
    )


def parse_license_status(
    info: object | None,
    *,
    seats: object | None,
    configured: bool,
    now: datetime | None = None,
) -> LicenseStatus:
    if info is None:
        return LicenseStatus(configured, False, None, None, None)
    plan = _optional_string(getattr(info, "plan", None))
    expires = _optional_string(getattr(info, "expires", None))
    valid = bool(getattr(info, "valid", False)) and not _is_expired(expires, now)
    seat_status = None
    if valid and seats is not None:
        active = _optional_int(getattr(seats, "active", None))
        limit = _optional_int(getattr(seats, "limit", None))
        if active is not None or limit is not None:
            seat_status = LicenseSeats(active, limit)
    return LicenseStatus(configured, valid, plan, expires, seat_status)


class CloakBrowserLicenseProvider:
    def __init__(self, store: LicenseStore, validator: LicenseValidator) -> None:
        self._store = store
        self._validator = validator

    def status(self) -> LicenseStatus:
        key = self._store.read()
        if key is None:
            return LicenseStatus(False, False, None, None, None)
        return replace(self._validate(key), configured=True)

    def connect(self, license_key: str) -> LicenseStatus:
        key = license_key.strip()
        if not key:
            raise LicenseInvalid()
        status = replace(self._validate(key), configured=True)
        if not status.valid:
            raise LicenseInvalid()
        self._store.write(key)
        return status

    def disconnect(self, *, has_active_licensed_operation: bool) -> None:
        if has_active_licensed_operation:
            raise LicenseInUse()
        self._store.delete()

    def _validate(self, key: str) -> LicenseStatus:
        try:
            return self._validator(key)
        except (LicenseInvalid, LicenseValidationUnavailable):
            raise
        except Exception:  # noqa: BLE001 -- worker/provider errors must not expose the key.
            raise LicenseValidationUnavailable() from None


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _is_expired(expires: str | None, now: datetime | None) -> bool:
    if expires is None:
        return False
    try:
        parsed = datetime.fromisoformat(expires)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed <= (now or datetime.now(UTC))
    except ValueError:
        return False
