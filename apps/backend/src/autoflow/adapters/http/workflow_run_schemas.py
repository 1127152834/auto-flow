import json
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import Field, JsonValue, field_validator, model_validator

from .schemas import ApiModel
from .workflow_schemas import WorkflowDocument, WorkflowIssue, WorkflowLayout

RunState = Literal[
    "starting", "running", "pausing", "paused", "failed_paused", "finishing", "stopping", "succeeded", "failed",
    "cancelled", "interrupted",
]


class DebugOptions(ApiModel):
    start: Literal['entry', 'node', 'until'] = 'entry'
    target_node_id: str | None = None
    breakpoints: list[str] = Field(default_factory=list, max_length=2000)
    values: dict[str, JsonValue] = Field(default_factory=dict)


class DebugCommand(ApiModel):
    command_id: str = Field(min_length=1, max_length=120, pattern=r'^[a-zA-Z0-9_-]+$')
    expected_revision: int = Field(ge=0, strict=True)
    pause_id: str | None = None
    action: Literal['pause', 'resume', 'step', 'breakpoints', 'variables', 'page', 'pages']
    breakpoints: list[str] = Field(default_factory=list, max_length=2000)
    values: dict[str, JsonValue] = Field(default_factory=dict)
    page_id: str | None = None
    page_alias: str | None = Field(default=None, max_length=120)
    url: str | None = None
    focus: bool = False


    @field_validator('url')
    @classmethod
    def navigation_url(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = urlsplit(value)
            if parsed.scheme not in {'http', 'https'} or not parsed.hostname or any(c.isspace() for c in parsed.netloc):
                raise ValueError('请输入有效 HTTP/HTTPS 导航地址')
            _ = parsed.port
        return value

    @field_validator('values')
    @classmethod
    def finite_values(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        json.dumps(value, allow_nan=False)
        return value


class DebugCommandRead(ApiModel):
    command_id: str
    state: Literal['accepted', 'applied', 'rejected', 'interrupted']
    debug: dict[str, JsonValue] | None = None
    data: dict[str, JsonValue] | None = None
    error: dict[str, str] | None = None


class DebugVariables(ApiModel):
    checkpoint_id: str | None = None
    items: list[dict[str, JsonValue]]
    next_offset: int | None = None
    diagnostic_artifacts: list[dict[str, JsonValue]] = Field(default_factory=list)
    next_cursor: int | None = None


class RunStart(ApiModel):
    mode: Literal['run', 'debug'] = 'run'
    debug: DebugOptions | None = None
    run_id: str
    document: WorkflowDocument
    layout: WorkflowLayout
    profile_id: str

    @model_validator(mode='after')
    def valid_debug_mode(self) -> 'RunStart':
        if self.mode == 'run' and self.debug is not None:
            raise ValueError('普通运行不能携带调试参数')
        if self.debug is not None:
            json.dumps(self.debug.values, allow_nan=False)
        return self

    @field_validator("run_id", "profile_id")
    @classmethod
    def canonical_uuid(cls, value: str) -> str:
        return str(UUID(value))


class RunError(ApiModel):
    code: str
    message: str
    node_id: str | None
    path: list[str]


class LoopIteration(ApiModel):
    loop_node_id: str
    iteration: int


class RunArtifact(ApiModel):
    purpose: Literal["result", "diagnostic"] = "result"
    event_seq: int = 0
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
    node_execution_counts: dict[str, int] = Field(default_factory=dict)
    mode: Literal["run", "debug"] = "run"
    debug: dict[str, JsonValue] | None = None
    execution_count: int = 0
    current_execution_id: str | None = None
    current_loop_path: list[LoopIteration] = Field(default_factory=list)
    artifact_count: int = 0
    run_id: str
    workflow_id: str
    name: str
    profile_id: str
    profile_name: str
    state: RunState
    current_node_id: str | None
    started_at: datetime
    finished_at: datetime | None
    latest_seq: int
    completed_node_ids: list[str]
    error: RunError | None


class RunRead(RunSummary):
    debug_options: DebugOptions | None = None
    artifact_ordinal: int = 0
    next_artifact_cursor: int | None = None
    document: WorkflowDocument
    layout: WorkflowLayout
    profile_snapshot: dict[str, JsonValue]
    node_order: list[str]
    artifacts: list[RunArtifact]
    warnings: list[WorkflowIssue]


class RunList(ApiModel):
    items: list[RunSummary]
    active_run_id: str | None
    next_offset: int | None


class RunEvent(ApiModel):
    debug: dict[str, JsonValue] | None = None
    reason: str | None = None
    response: dict[str, JsonValue] | None = None
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
