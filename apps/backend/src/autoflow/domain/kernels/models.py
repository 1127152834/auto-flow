from dataclasses import dataclass
from pathlib import Path
from typing import Literal

KernelEdition = Literal["public", "licensed"]
ReleaseChannel = Literal["stable", "preview"]


@dataclass(frozen=True)
class KernelRef:
    edition: KernelEdition
    version: str


@dataclass(frozen=True)
class DefaultKernel:
    revision: int
    kernel: KernelRef | None


@dataclass(frozen=True)
class KernelRelease:
    edition: KernelEdition
    version: str
    chromium_version: str
    release_channel: ReleaseChannel
    published_at: str | None
    archive: str | None
    size: int | None
    installed: bool = False


@dataclass(frozen=True)
class InstalledKernel:
    edition: KernelEdition
    version: str
    executable_path: Path
    size: int


@dataclass(frozen=True)
class LicenseSeats:
    active: int | None
    limit: int | None


@dataclass(frozen=True)
class LicenseStatus:
    configured: bool
    valid: bool
    plan: str | None
    expires: str | None
    seats: LicenseSeats | None


@dataclass(frozen=True)
class KernelCatalog:
    wrapper_version: str
    platform: str
    releases: tuple[KernelRelease, ...]
    installed: tuple[InstalledKernel, ...]
    catalog_error: str | None = None
