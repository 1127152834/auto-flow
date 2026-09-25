from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

from .models import Capability, ProviderProxy

RotationMode = Literal["same_city", "same_city_carriers", "full_pool"]
RemoteKind = Literal["change_ip", "relocate", "save_rotation", "clear_rotation"]
OperationStatus = Literal["queued", "running", "succeeded", "failed", "unknown"]
ROTATION_INTERVALS = (5, 10, 30, 60)


@dataclass(frozen=True)
class RotationSchedule:
    enabled: bool = False
    mode: RotationMode | None = None
    interval_minutes: int | None = None


@dataclass(frozen=True)
class Location:
    id: str
    city: str
    country: str
    carrier: str | None
    available_slots: int
    cities: tuple[str, ...] = ()


@dataclass(frozen=True)
class RemoteState:
    proxy: ProviderProxy
    current_ip: str | None
    location_generation: int
    bound: bool | None
    country: str | None
    capabilities: tuple[Capability, ...]
    rotation_blocked_reason: str | None = None
    rotation_available: bool | None = None
    retry_after_seconds: int | None = None


@dataclass(frozen=True)
class RemoteOperation:
    id: str
    kind: RemoteKind
    target_id: str
    connection_id: str
    secret_ref: str = field(repr=False)
    idempotency_key: str
    fingerprint: str
    payload: dict
    before: dict
    status: OperationStatus
    created_at: datetime
    updated_at: datetime
    resource_revision: int | None = None
    error: dict | None = None


class RemoteProvider(Protocol):
    async def get_state(self, key: bytes, provider_id: str) -> RemoteState: ...
    async def get_locations(self, key: bytes) -> list[Location]: ...
    async def get_schedule(self, key: bytes, provider_id: str) -> RotationSchedule: ...
    async def execute(
        self, key: bytes, provider_id: str, kind: RemoteKind, payload: dict
    ) -> None: ...


class OperationRepository(Protocol):
    def find_key(self, key: str) -> RemoteOperation | None: ...
    def get(self, operation_id: str) -> RemoteOperation: ...
    def active(self, target_id: str) -> RemoteOperation | None: ...
    def latest(self, target_id: str) -> RemoteOperation | None: ...
    def reserve(
        self, operation: RemoteOperation, expected_revision: int
    ) -> RemoteOperation: ...
    def update(
        self,
        operation_id: str,
        status: OperationStatus,
        *,
        before: dict | None = None,
        error: dict | None = None,
        resource_revision: int | None = None,
    ) -> None: ...
    def recover(self) -> None: ...
