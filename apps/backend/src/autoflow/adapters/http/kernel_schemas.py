from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from autoflow.application.kernels.operations import KernelOperation
from autoflow.domain.kernels.models import (
    DefaultKernel,
    InstalledKernel,
    KernelCatalog,
    KernelRef,
    LicenseStatus,
)


def _camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class KernelApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="forbid")


class KernelRefRead(KernelApiModel):
    edition: Literal["public", "licensed"]
    version: str = Field(pattern=r"^[0-9]+(?:\.[0-9]+){3,4}$")

    def to_ref(self) -> KernelRef:
        return KernelRef(self.edition, self.version)

    @classmethod
    def from_ref(cls, value: KernelRef) -> "KernelRefRead":
        return cls(edition=value.edition, version=value.version)


class KernelReleaseRead(KernelRefRead):
    chromium_version: str
    release_channel: Literal["stable", "preview"]
    published_at: str | None
    archive: str | None
    size: int | None
    installed: bool


class InstalledKernelRead(KernelRefRead):
    executable_path: str
    size: int

    @classmethod
    def from_installed(cls, value: InstalledKernel) -> "InstalledKernelRead":
        return cls(
            edition=value.edition,
            version=value.version,
            executable_path=str(value.executable_path),
            size=value.size,
        )


class KernelCatalogRead(KernelApiModel):
    wrapper_version: str
    platform: str
    releases: list[KernelReleaseRead]
    installed: list[InstalledKernelRead]
    catalog_error: str | None

    @classmethod
    def from_catalog(cls, value: KernelCatalog) -> "KernelCatalogRead":
        return cls(
            wrapper_version=value.wrapper_version,
            platform=value.platform,
            releases=[KernelReleaseRead(**release.__dict__) for release in value.releases],
            installed=[InstalledKernelRead.from_installed(item) for item in value.installed],
            catalog_error=value.catalog_error,
        )


class InstalledKernelList(KernelApiModel):
    items: list[InstalledKernelRead]


class LicenseSeatsRead(KernelApiModel):
    active: int | None
    limit: int | None


class LicenseRead(KernelApiModel):
    configured: bool
    valid: bool
    plan: str | None
    expires: str | None
    seats: LicenseSeatsRead | None

    @classmethod
    def from_status(cls, value: LicenseStatus) -> "LicenseRead":
        return cls(
            configured=value.configured,
            valid=value.valid,
            plan=value.plan,
            expires=value.expires,
            seats=LicenseSeatsRead(**value.seats.__dict__) if value.seats else None,
        )


class LicenseWrite(KernelApiModel):
    license_key: SecretStr = Field(
        min_length=1, json_schema_extra={"writeOnly": True}
    )


class DefaultKernelRead(KernelApiModel):
    revision: int
    kernel: KernelRefRead | None

    @classmethod
    def from_default(cls, value: DefaultKernel) -> "DefaultKernelRead":
        return cls(
            revision=value.revision,
            kernel=KernelRefRead.from_ref(value.kernel) if value.kernel else None,
        )


class DefaultKernelWrite(KernelApiModel):
    expected_revision: int = Field(ge=0)
    kernel: KernelRefRead | None


class KernelDownload(KernelRefRead):
    release_channel: Literal["stable", "preview"]

    @model_validator(mode="after")
    def public_requires_stable(self) -> "KernelDownload":
        if self.edition == "public" and self.release_channel != "stable":
            raise ValueError("Public edition only supports Stable release channel")
        return self


class KernelOperationRead(KernelApiModel):
    id: str
    edition: Literal["public", "licensed"]
    requested_version: str
    resolved_version: str | None
    release_channel: Literal["stable", "preview"]
    state: Literal[
        "queued", "downloading", "verifying", "extracting", "cancelling",
        "cancelled", "completed", "failed",
    ]
    progress: int | None
    message: str | None
    error: str | None

    @classmethod
    def from_operation(cls, value: KernelOperation) -> "KernelOperationRead":
        return cls(
            id=value.id,
            edition=value.edition,
            requested_version=value.requested_version,
            resolved_version=value.resolved_version,
            release_channel=value.release_channel,
            state=value.state,
            progress=value.progress,
            message=value.message,
            error=value.error,
        )


class KernelOperationList(KernelApiModel):
    items: list[KernelOperationRead]


class KernelPathRead(KernelApiModel):
    executable_path: str
