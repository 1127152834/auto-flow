from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

Evidence = Literal[
    "confirmed-public",
    "confirmed-authenticated-doc",
    "fixture-verified",
    "synthetic",
    "unknown",
]


class ApiError(BaseModel):
    code: str
    message: str
    request_id: str
    field_errors: dict[str, Any] = Field(default_factory=dict)
    retry_after_seconds: int | None = None
    outcome_unknown: bool = False


class ErrorResponse(BaseModel):
    error: ApiError


class Capability(BaseModel):
    key: str
    available: bool
    evidence: Evidence
    reason: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)


class Endpoint(BaseModel):
    host: str
    port: int = Field(ge=1, le=65535)


class HealthSnapshot(BaseModel):
    state: Literal["untested", "checking", "healthy", "unhealthy"] = "untested"
    latency_ms: float | None = Field(default=None, ge=0)
    exit_ip: str | None = None
    checked_at: datetime | None = None
    source: Literal["local_probe", "provider_probe", "none"] = "none"
    error: ApiError | None = None


class ConnectionView(BaseModel):
    id: str
    name: str
    has_secret: bool
    status: Literal["unconfigured", "verifying", "connected", "failed"]
    revision: int = Field(ge=0)
    last_verified_at: datetime | None = None
    last_synced_at: datetime | None = None
    last_error: ApiError | None = None
    capabilities: list[Capability] = Field(default_factory=list)


class ConnectionList(BaseModel):
    items: list[ConnectionView]


class ConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    api_key: SecretStr = Field(json_schema_extra={"writeOnly": True}, repr=False)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        if not (value := value.strip()):
            raise ValueError("name must not be blank")
        return value

    @field_validator("api_key")
    @classmethod
    def reject_blank_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("api_key must not be blank")
        return value


class ConnectionUpdate(BaseModel):
    expected_revision: int = Field(ge=0)
    name: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def trim_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not (value := value.strip()):
            raise ValueError("name must not be blank")
        return value

    @model_validator(mode="after")
    def require_change(self) -> "ConnectionUpdate":
        if self.name is None:
            raise ValueError("at least one change is required")
        return self


class ApiKeyUpdate(BaseModel):
    expected_revision: int = Field(ge=0)
    api_key: SecretStr = Field(json_schema_extra={"writeOnly": True}, repr=False)

    @field_validator("api_key")
    @classmethod
    def reject_blank_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("api_key must not be blank")
        return value


class SyncSnapshot(BaseModel):
    last_synced_at: datetime | None = None
    stale: bool
    completeness: Literal["complete", "partial", "unknown"]
    synced_count: int = Field(ge=0)
    provider_total: int | None = Field(default=None, ge=0)
    remote_missing_count: int = Field(ge=0)
    last_error: ApiError | None = None


class ProxyView(BaseModel):
    id: str
    connection_id: str
    name: str
    name_override: str | None = None
    enabled: bool
    remote_status: str | None = None
    remote_missing: bool
    carrier: str | None = None
    city: str | None = None
    region: str | None = None
    exit_ip: str | None = None
    http_endpoint: Endpoint | None = None
    socks5_endpoint: Endpoint | None = None
    credential_available: bool
    health: HealthSnapshot
    subscription_expires_at: datetime | None = None
    last_synced_at: datetime | None = None
    stale: bool
    revision: int = Field(ge=0)
    reference_count: int = Field(ge=0)
    capabilities: list[Capability] = Field(default_factory=list)


class ProxyPage(BaseModel):
    items: list[ProxyView]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    matched_count: int = Field(ge=0)


class ProxyUpdate(BaseModel):
    expected_revision: int = Field(ge=0)
    name_override: str | None = Field(default=None, max_length=120)
    enabled: bool | None = None

    @field_validator("name_override")
    @classmethod
    def normalize_name_override(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def require_change(self) -> "ProxyUpdate":
        if "name_override" not in self.model_fields_set and self.enabled is None:
            raise ValueError("at least one change is required")
        return self


class ProbeRequest(BaseModel):
    protocol: Literal["http", "socks5"] = "http"


class ExpectedRevision(BaseModel):
    expected_revision: int = Field(ge=0)


class RelocateRequest(ExpectedRevision):
    location_id: str = Field(min_length=1)


class RotationScheduleUpdate(ExpectedRevision):
    mode: Literal["same_city", "same_city_carriers", "full_pool"]
    interval_minutes: Literal[5, 10, 30, 60]


class IpAllowlistUpdate(ExpectedRevision):
    enabled: bool
    ipv4s: list[str]


class ResourceReference(BaseModel):
    id: str
    name: str


class ProxyReferences(BaseModel):
    profiles: list[ResourceReference] = Field(default_factory=list)
    groups: list[ResourceReference] = Field(default_factory=list)


class GroupView(BaseModel):
    id: str
    name: str
    description: str
    member_ids: list[str]
    revision: int = Field(ge=0)
    reference_count: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class GroupPage(BaseModel):
    items: list[GroupView]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    matched_count: int = Field(ge=0)


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    member_ids: list[str]
    acknowledge_risk: bool = False

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        if not (value := value.strip()):
            raise ValueError("name must not be blank")
        return value


class GroupUpdate(GroupCreate):
    expected_revision: int = Field(ge=0)


class GroupReferences(BaseModel):
    profiles: list[ResourceReference] = Field(default_factory=list)


class LocationView(BaseModel):
    cities: list[str] = Field(default_factory=list)
    country: str | None = None
    available_slots: int | None = Field(default=None, ge=0)
    id: str
    city: str
    region: str | None = None
    carrier: str | None = None
    availability: Literal["available", "unavailable", "unknown"] = "unknown"


class LocationList(BaseModel):
    items: list[LocationView]
    fetched_at: datetime | None = None
    stale: bool


class AccountSummary(BaseModel):
    balance: str | None = None
    currency: str | None = None
    fetched_at: datetime | None = None


class RotationSchedule(BaseModel):
    enabled: bool
    mode: Literal["same_city", "same_city_carriers", "full_pool"] | None = None
    interval_minutes: int | None = Field(default=None, ge=1, le=60)


class IpAllowlist(BaseModel):
    enabled: bool
    ipv4s: list[str]


class CredentialView(BaseModel):
    credential_available: bool
    username: str | None = None
    can_copy: bool
    can_rotate: bool


class UsagePoint(BaseModel):
    at: datetime
    value: float


class UsageView(BaseModel):
    available: bool
    unit: str | None = None
    total: float | None = None
    points: list[UsagePoint] = Field(default_factory=list)
    fetched_at: datetime | None = None


class OperationView(BaseModel):
    id: str
    kind: str
    target_id: str
    status: Literal["queued", "running", "succeeded", "failed", "unknown"]
    resource_revision: int | None = Field(default=None, ge=0)
    error: ApiError | None = None
    created_at: datetime
    updated_at: datetime


ResourceT = TypeVar("ResourceT")


class ActionResult(BaseModel, Generic[ResourceT]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: Literal["completed", "accepted", "failed"]
    operation_id: str | None = None
    resource: ResourceT | None = None
    error: ApiError | None = None
