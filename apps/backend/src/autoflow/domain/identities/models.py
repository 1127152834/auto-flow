from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Identity:
    """One account's browser identity: its own seed, region, proxy binding and login environment."""

    identity_id: str
    project_id: str
    name: str
    seed: int
    template_profile_id: str | None
    environment_id: str | None
    created_at: datetime
    updated_at: datetime
