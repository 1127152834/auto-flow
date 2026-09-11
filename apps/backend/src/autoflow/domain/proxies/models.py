from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Evidence = Literal[
    "confirmed-public",
    "confirmed-authenticated-doc",
    "fixture-verified",
    "synthetic",
    "unknown",
]


@dataclass(frozen=True)
class Capability:
    key: str
    available: bool = False
    evidence: Evidence = "unknown"
    reason: str | None = "Provider response schema has not been verified"
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int


@dataclass(frozen=True)
class Health:
    state: Literal["untested", "checking", "healthy", "unhealthy"] = "untested"
    latency_ms: float | None = None
    exit_ip: str | None = None
    checked_at: datetime | None = None
    source: Literal["local_probe", "provider_probe", "none"] = "none"
    error: dict[str, Any] | None = None


@dataclass(frozen=True)
class Connection:
    id: str
    name: str
    secret_ref: str
    status: Literal["unconfigured", "verifying", "connected", "failed"]
    revision: int
    generation: int
    sync_token: str | None
    sync_started_at: datetime | None
    last_verified_at: datetime | None
    last_synced_at: datetime | None
    last_error: dict[str, Any] | None
    capabilities: tuple[Capability, ...]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Projection:
    id: str
    connection_id: str
    provider_id: str
    name: str
    name_override: str | None
    enabled: bool
    remote_status: str | None
    remote_missing: bool
    carrier: str | None
    city: str | None
    region: str | None
    exit_ip: str | None
    http_endpoint: Endpoint | None
    socks5_endpoint: Endpoint | None
    credential_available: bool
    health: Health
    subscription_expires_at: datetime | None
    last_synced_at: datetime | None
    stale: bool
    revision: int
    generation: int
    capabilities: tuple[Capability, ...]
    created_at: datetime
    updated_at: datetime
    reference_count: int = 0

    @property
    def display_name(self) -> str:
        return self.name_override or self.name


@dataclass(frozen=True)
class ProviderProxy:
    provider_id: str
    name: str
    remote_status: str | None = None
    carrier: str | None = None
    city: str | None = None
    region: str | None = None
    exit_ip: str | None = None
    http_endpoint: Endpoint | None = None
    socks5_endpoint: Endpoint | None = None
    credential_available: bool = False
    subscription_expires_at: datetime | None = None


@dataclass(frozen=True)
class ProviderPage:
    items: tuple[ProviderProxy, ...]
    completeness: Literal["complete", "partial", "unknown"] = "unknown"
    total: int | None = None


@dataclass(frozen=True)
class ProxyGroup:
    id: str
    name: str
    description: str
    member_ids: tuple[str, ...]
    revision: int
    cursor: int
    cursor_revision: int
    created_at: datetime
    updated_at: datetime
    reference_count: int = 0


REMOTE_CAPABILITY_KEYS = (
    "remote_status",
    "locations",
    "change_ip",
    "relocate",
    "rotation_schedule",
    "ip_allowlist",
    "credentials",
    "credential_rotate",
    "usage",
    "account_summary",
    "subscription_expiry",
)


def unavailable_capabilities() -> tuple[Capability, ...]:
    return tuple(Capability(key=key) for key in REMOTE_CAPABILITY_KEYS)
