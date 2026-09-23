from datetime import datetime
from typing import Any, Literal

from pydantic import JsonValue

from .schemas import ApiModel


class NodeAttemptView(ApiModel):
    node_visit_id: str
    node_id: str
    node_name: str
    attempt: int
    status: Literal["running", "succeeded", "failed"]
    started_at: datetime | None
    completed_at: datetime | None
    error: dict[str, Any] | None


class NodeAttemptPage(ApiModel):
    items: list[NodeAttemptView]
    page: int
    page_size: int
    total: int
    sort: str


class RunLogEntry(ApiModel):
    run_id: str
    sequence: int
    event_id: str
    execution_generation: int
    node_id: str | None = None
    node_name: str | None = None
    node_visit_id: str | None = None
    attempt: int | None = None
    level: Literal["debug", "info", "warning", "error"]
    message: str
    occurred_at: datetime


class RunLogPage(ApiModel):
    items: list[RunLogEntry]
    after_sequence: int
    last_sequence: int
    has_more: bool


class RunOutputView(ApiModel):
    output_id: str
    kind: Literal["value"]
    name: str
    value: JsonValue
    run_id: str
    sequence: int
    node_id: str | None = None
    node_name: str | None = None
    node_visit_id: str | None = None
    attempt: int | None = None
    created_at: datetime


class RunOutputPage(ApiModel):
    items: list[RunOutputView]
    page: int
    page_size: int
    total: int
    sort: str


class RunArtifactView(ApiModel):
    artifact_id: str
    kind: Literal["screenshot"]
    purpose: Literal["error", "result"]
    availability: Literal["available", "unavailable"]
    node_id: str
    node_name: str
    node_visit_id: str | None = None
    event_sequence: int
    execution_generation: int
    media_type: Literal["image/png"] | None = None
    byte_size: int | None = None
    sha256: str | None = None
    created_at: datetime
    unavailable_reason: str | None = None
    content_url: str | None = None


class RunArtifactPage(ApiModel):
    items: list[RunArtifactView]
    page: int
    page_size: int
    total: int
    sort: str
