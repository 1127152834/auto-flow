from __future__ import annotations

import platform as runtime_platform
import re
from collections.abc import Iterable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from autoflow.domain.kernels.errors import KernelCatalogError, KernelPlatformUnsupported
from autoflow.domain.kernels.models import (
    InstalledKernel,
    KernelRelease,
    ReleaseChannel,
)

_VERSION_PATTERN = re.compile(
    r"^chromium-v(?P<version>\d+(?:\.\d+)+)(?P<pro>-pro)?$", re.IGNORECASE
)
_DIRECTORY_PATTERN = re.compile(
    r"^chromium-(?P<version>\d+(?:\.\d+)+)(?P<pro>-pro)?$", re.IGNORECASE
)
_ASSET_PATTERN = re.compile(
    r"^cloakbrowser-(?P<platform>[a-z0-9-]+)\.(?:zip|tar\.gz)$", re.IGNORECASE
)
_SUPPORTED_PLATFORMS = {
    ("windows", "amd64"): "windows-x64",
    ("windows", "x86_64"): "windows-x64",
    ("darwin", "arm64"): "darwin-arm64",
    ("darwin", "x86_64"): "darwin-x64",
}


def current_platform_tag(*, system: str | None = None, machine: str | None = None) -> str:
    key = (
        (system or runtime_platform.system()).lower(),
        (machine or runtime_platform.machine()).lower(),
    )
    try:
        return _SUPPORTED_PLATFORMS[key]
    except KeyError:
        raise KernelPlatformUnsupported() from None


def executable_path(directory: Path, platform: str) -> Path:
    if platform not in _SUPPORTED_PLATFORMS.values():
        raise KernelPlatformUnsupported()
    if platform.startswith("darwin-"):
        return directory / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
    return directory / "chrome.exe"


def parse_public_catalog(payload: object, *, platform: str) -> list[KernelRelease]:
    if platform not in _SUPPORTED_PLATFORMS.values():
        raise KernelPlatformUnsupported()
    if not isinstance(payload, list):
        raise KernelCatalogError()

    releases: list[KernelRelease] = []
    for raw_release in payload:
        if not isinstance(raw_release, dict) or raw_release.get("prerelease") is True:
            continue
        match = _VERSION_PATTERN.fullmatch(str(raw_release.get("tag_name") or ""))
        if match is None or match.group("pro"):
            continue
        asset = _platform_asset(raw_release.get("assets"), platform)
        if asset is None:
            continue
        version = match.group("version")
        releases.append(
            KernelRelease(
                edition="public",
                version=version,
                chromium_version=f"Chromium {version.split('.')[0]}",
                release_channel="stable",
                published_at=_optional_string(raw_release.get("published_at")),
                archive=_optional_string(asset.get("name")),
                size=_optional_non_negative_int(asset.get("size")),
            )
        )
    return _sort_releases(releases)


def parse_licensed_catalog(releases: Iterable[object]) -> list[KernelRelease]:
    parsed: list[KernelRelease] = []
    seen: set[tuple[str, str]] = set()
    for info in releases:
        version = _attribute_string(info, "version")
        channel = _attribute_string(info, "resolved_channel")
        if version is None or channel not in {"stable", "preview"}:
            continue
        identity = (version, channel)
        if identity in seen:
            continue
        seen.add(identity)
        parsed.append(
            KernelRelease(
                edition="licensed",
                version=version,
                chromium_version=f"Chromium {version.split('.')[0]}",
                release_channel=cast(ReleaseChannel, channel),
                published_at=None,
                archive=None,
                size=None,
            )
        )
    return _sort_releases(parsed)


def scan_installed_kernels(root: Path, *, platform: str) -> list[InstalledKernel]:
    if platform not in _SUPPORTED_PLATFORMS.values():
        raise KernelPlatformUnsupported()
    try:
        directories = list(root.iterdir())
    except FileNotFoundError:
        return []

    installed: list[InstalledKernel] = []
    for directory in directories:
        match = _DIRECTORY_PATTERN.fullmatch(directory.name)
        if match is None or not directory.is_dir() or directory.is_symlink():
            continue
        executable = executable_path(directory, platform)
        if not executable.is_file():
            continue
        try:
            resolved_executable = executable.resolve()
            resolved_executable.relative_to(directory.resolve())
        except (OSError, ValueError):
            continue
        installed.append(
            InstalledKernel(
                edition="licensed" if match.group("pro") else "public",
                version=match.group("version"),
                executable_path=resolved_executable,
                size=_directory_size(directory),
            )
        )
    return sorted(installed, key=lambda item: _version_key(item.version), reverse=True)


def resolve_installed_kernel(
    executable: str | Path, installed: Sequence[InstalledKernel]
) -> InstalledKernel | None:
    candidate = Path(executable).resolve()
    return next((item for item in installed if item.executable_path.resolve() == candidate), None)


def merge_catalog(
    releases: Iterable[KernelRelease], installed: Sequence[InstalledKernel]
) -> list[KernelRelease]:
    installed_keys = {(item.edition, item.version) for item in installed}
    merged = [
        replace(release, installed=(release.edition, release.version) in installed_keys)
        for release in releases
    ]
    known = {(release.edition, release.version) for release in merged}
    for item in installed:
        if (item.edition, item.version) in known:
            continue
        merged.append(
            KernelRelease(
                edition=item.edition,
                version=item.version,
                chromium_version=f"Chromium {item.version.split('.')[0]}",
                release_channel="stable",
                published_at=None,
                archive=None,
                size=item.size,
                installed=True,
            )
        )
    return _sort_releases(merged)


def _platform_asset(assets: Any, platform: str) -> dict[str, Any] | None:
    if not isinstance(assets, list):
        return None
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        match = _ASSET_PATTERN.fullmatch(str(asset.get("name") or ""))
        if match and match.group("platform").lower() == platform:
            return asset
    return None


def _attribute_string(value: object, attribute: str) -> str | None:
    raw = getattr(value, attribute, None)
    return str(raw) if raw is not None and str(raw) else None


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_non_negative_int(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _directory_size(directory: Path) -> int:
    size = 0
    try:
        for item in directory.rglob("*"):
            if item.is_file() and not item.is_symlink():
                size += item.stat().st_size
    except OSError:
        return 0
    return size


def _sort_releases(releases: Iterable[KernelRelease]) -> list[KernelRelease]:
    return sorted(releases, key=lambda item: _version_key(item.version), reverse=True)


def _version_key(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return ()
