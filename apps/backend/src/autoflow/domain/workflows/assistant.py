from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Literal

AssistantStatus = Literal["idle", "running", "waiting_for_action", "completed", "failed", "cancelled"]


@dataclass(frozen=True, slots=True)
class AssistantSession:
    id: str
    title: str
    messages: tuple[dict[str, Any], ...]
    status: AssistantStatus
    pending_action: dict[str, Any] | None
    revision: int
    created_at: datetime
    updated_at: datetime

    def with_changes(self, **changes: Any) -> AssistantSession:
        return replace(self, **copy.deepcopy(changes))


@dataclass(frozen=True, slots=True)
class AssistantCommand:
    id: str
    session_id: str
    request_hash: str
    status: Literal["confirmed", "completed", "failed"]
    result: dict[str, Any]
    receipt: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
