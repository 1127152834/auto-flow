from dataclasses import dataclass, field
from typing import Literal

RuntimeState = Literal["stopped", "starting", "ready", "retained", "missing", "unknown"]
OwnerKind = Literal["none", "manualSession", "legacyWorkflow", "unknown"]
ControlState = Literal["idle", "managing", "manual", "opening_manual", "closing_manual", "recovery_required"]
OperationState = Literal[
    "queued",
    "running",
    "waiting_capacity",
    "succeeded",
    "failed",
    "cancelled",
    "needs_verification",
]


@dataclass(frozen=True)
class DeviceFacts:
    device_id: str
    revision: int = 1
    runtime_state: RuntimeState = "unknown"
    owner_kind: OwnerKind = "none"
    owner_id: str | None = None
    control: ControlState = "idle"
    operation_action: str | None = None
    operation_state: OperationState | None = None
    stale: bool = False
    retained: bool = False
    last_error: str | None = None


@dataclass(frozen=True)
class ActionPolicy:
    allowed_actions: tuple[str, ...] = ()
    blocked_reasons: dict[str, str] = field(default_factory=dict)
