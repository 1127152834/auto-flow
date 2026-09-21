from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from .schemas import ApiModel


class OwnerRead(ApiModel):
    kind: Literal["none", "manualSession", "legacyWorkflow", "unknown"]
    id: str | None = None


class ManagementDeviceRead(ApiModel):
    device_id: str
    revision: int = Field(ge=1)
    name: str
    runtime_state: Literal["stopped", "starting", "ready", "retained", "missing", "unknown"]
    owner: OwnerRead
    observed_at: datetime | None
    stale: bool
    spec_snapshot: dict[str, Any]
    latest_operation: dict[str, Any] | None
    allowed_actions: list[str]
    blocked_reasons: dict[str, str]


class EnvironmentCheckRead(ApiModel):
    status: Literal["pass", "fail", "unknown", "unsupported"]
    code: str | None = None
    message: str
    action: str | None = None


class ManagementEnvironmentRead(ApiModel):
    available: bool
    platform_supported: bool | None
    runtime_id: str
    message: str
    images: list[dict[str, Any]] = Field(default_factory=list)
    cpu_count: int = 0
    memory_mb: int = 0
    checked_at: datetime
    checks: dict[str, EnvironmentCheckRead]
    capabilities: dict[str, bool | str]


class ManagementCapabilitiesRead(ApiModel):
    management: bool | str
    control: bool | str
    images: bool | str
    bulk: bool | str
    backups: bool | str
    workflow: bool
    reasons: dict[str, str]


class OperationRead(ApiModel):
    operation_id: str
    request_id: str
    target_id: str
    action: str
    state: str
    stage_code: str
    stage_label: str
    attempt: int
    retry_of: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_code: str | None = None
    message: str | None = None
    allowed_actions: list[str] = Field(default_factory=list)


class EnvironmentCheckCommand(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)


class OperationVerifyCommand(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)


class ImageRead(ApiModel):
    id: str
    image_id: str
    name: str
    reference: str
    revision: int
    state: str
    verification: dict[str, Any]
    created_at: datetime


class ImageRegister(ApiModel):
    id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    name: str = Field(min_length=1, max_length=120)
    reference: str = Field(min_length=1, max_length=255)


class ImageDelete(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)
    delete_content: bool = False


class BackupRead(ApiModel):
    id: str
    device_id: str
    image_id: str
    format_version: int
    sha256: str
    bytes: int
    created_at: datetime
    state: str


class BackupCreate(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)
