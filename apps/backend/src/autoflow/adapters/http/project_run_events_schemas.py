from datetime import datetime
from typing import Literal

from pydantic import JsonValue

from .schemas import ApiModel


class ProjectRunEventView(ApiModel):
    event_id: str
    run_id: str
    sequence: int
    execution_generation: int
    kind: Literal["runStatus", "nodeAttempt", "log", "output", "artifact", "checkpoint"]
    node_id: str | None = None
    node_visit_id: str | None = None
    attempt: int | None = None
    occurred_at: datetime
    payload: dict[str, JsonValue]


class ProjectRunEventPage(ApiModel):
    items: list[ProjectRunEventView]
    after_sequence: int
    last_sequence: int
    has_more: bool
    terminal: bool
