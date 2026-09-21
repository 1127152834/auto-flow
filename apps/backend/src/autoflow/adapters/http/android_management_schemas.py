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
