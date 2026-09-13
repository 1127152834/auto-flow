from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field, JsonValue, field_validator, model_validator

from .schemas import ApiModel
from .workflow_schemas import WorkflowDocument, WorkflowIssue, WorkflowLayout

RunState = Literal[
    "starting", "running", "finishing", "stopping", "succeeded", "failed",
    "cancelled", "interrupted", "waiting_manual", "resuming",
]


class BrowserTarget(ApiModel):
    kind: Literal["browser"]
    profile_id: UUID


class AndroidTarget(ApiModel):
    kind: Literal["android"]
    device_id: UUID


RunTarget = Annotated[BrowserTarget | AndroidTarget, Field(discriminator="kind")]


class Handoff(ApiModel):
    handoff_id: str
    node_id: str
    state: str
    prompt: str
    deadline_at: datetime
    native_session_id: str | None
    error: str | None
    receipts: dict[str, str] = Field(default_factory=dict)


class HandoffCommand(ApiModel):
    request_id: UUID


class RunStart(ApiModel):
    run_id: str
    document: WorkflowDocument
    layout: WorkflowLayout
    profile_id: str | None = None
    target: RunTarget | None = None

    @field_validator("run_id", "profile_id")
    @classmethod
    def canonical_uuid(cls, value: str | None) -> str | None:
        return str(UUID(value)) if value is not None else None

    @model_validator(mode="after")
    def target_required(self) -> "RunStart":
        if (self.target is None) == (self.profile_id is None):
            raise ValueError("请仅提供 target 或 profileId")
        return self


class RunError(ApiModel):
    code: str
    message: str
    node_id: str | None
    path: list[str]


class LoopIteration(ApiModel):
    loop_node_id: str
    iteration: int


class RunArtifact(ApiModel):
    execution_id: str | None = None
    loop_path: list[LoopIteration] = Field(default_factory=list)
    ordinal: int | None = None
    id: str
    node_id: str
    kind: Literal["json", "image"]
    name: str
    mime_type: str
    relative_path: str
    output_path: str | None
    preview: str


class RunArtifacts(ApiModel):
    items: list[RunArtifact]
    next_cursor: int | None


class RunSummary(ApiModel):
    execution_count: int = 0
    current_execution_id: str | None = None
    current_loop_path: list[LoopIteration] = Field(default_factory=list)
    artifact_count: int = 0
    run_id: str
    workflow_id: str
    name: str
    profile_id: str | None
    profile_name: str | None
    target: RunTarget
    target_name: str
    state: RunState
    current_node_id: str | None
    started_at: datetime
    finished_at: datetime | None
    latest_seq: int
    completed_node_ids: list[str]
    error: RunError | None


    @model_validator(mode="before")
    @classmethod
    def legacy_target(cls, value: Any) -> Any:
        if isinstance(value, dict):
            value = dict(value)
            value.setdefault("target", {"kind": "browser", "profileId": value.get("profileId")})
            value.setdefault("targetName", value.get("profileName"))
        return value


class RunRead(RunSummary):
    next_artifact_cursor: int | None = None

    @model_validator(mode="before")
    @classmethod
    def hide_internal_receipts(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: item for key, item in value.items() if key != "handoffReceipts"}
        return value

    document: WorkflowDocument
    layout: WorkflowLayout
    profile_snapshot: dict[str, JsonValue] | None
    target_snapshot: dict[str, JsonValue] = Field(default_factory=dict)
    handoff: Handoff | None = None
    node_order: list[str]
    artifacts: list[RunArtifact]
    warnings: list[WorkflowIssue]


class RunList(ApiModel):
    items: list[RunSummary]
    active_run_id: str | None
    next_offset: int | None


class RunEvent(ApiModel):
    execution_id: str | None = None
    loop_path: list[LoopIteration] = Field(default_factory=list)
    branch: str | None = None
    run_id: str
    seq: int
    timestamp: datetime
    type: str
    node_id: str | None
    level: Literal["info", "warning", "error"]
    message: str
    duration_ms: float | None = Field(ge=0)
    artifact_id: str | None
    error: RunError | None


class RunEvents(ApiModel):
    items: list[RunEvent]
    has_more: bool
    next_seq: int
