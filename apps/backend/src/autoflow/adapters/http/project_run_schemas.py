from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, JsonValue, StrictBool, StrictFloat, StrictInt, StrictStr

from .project_automation_schemas import EnvironmentPolicy, ParameterDefinition
from .schemas import ApiModel

JsonScalar = StrictStr | StrictInt | StrictFloat | StrictBool | None


class BatchStartRequest(ApiModel):
    debug_selection: dict[str, dict[str, JsonValue] | None] | None = None
    expected_automation_revision: StrictInt = Field(ge=1)
    parameters: dict[str, JsonScalar]
    max_tasks: StrictInt | None = Field(None, ge=1, le=100)
    concurrency: StrictInt | None = Field(None, ge=1, le=100)
    environment_override: EnvironmentPolicy | None = None

    def payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_unset=True)


class InputPreviewRequest(ApiModel):
    expected_automation_revision: StrictInt = Field(ge=1)


class FollowUpBatchRequest(ApiModel):
    mode: Literal["originalInputGroup"]
    expected_task_status_revision: StrictInt = Field(ge=1)
    parameter_overrides: dict[str, JsonScalar] = Field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_unset=True)


class InputPreviewItem(ApiModel):
    input_id: str
    alias: str
    table_display: str
    record_display: str | None
    values: list[dict[str, JsonValue]] = Field(default_factory=list)
    outcome: str
    required: bool
    detail: str | None = None
    scanned_count: int | None = Field(None, ge=0)


class InputPreviewResponse(ApiModel):
    runnable: bool
    selection_status: str
    evaluated_candidate_bindings: int = Field(ge=0)
    inputs: list[InputPreviewItem]


class BatchView(ApiModel):
    batch_id: str
    project_id: str
    automation_id: str
    automation_name: str | None = None
    start_operation_id: str
    status: str
    status_revision: int
    management_revision: int
    requested_count: int | None
    created_task_count: int
    active_task_count: int
    claim_gate_state: str | None = None
    selection_outcome: dict[str, JsonValue] | None = None
    created_at: datetime
    completed_at: datetime | None = None


class TaskView(ApiModel):
    task_id: str
    project_id: str
    batch_id: str
    run_id: str
    run_request_id: str
    status: str
    status_revision: int
    input_snapshot_id: str
    task_ordinal: int = Field(ge=1)
    automation_name: str | None = None
    batch_started_at: datetime | None = None
    input_identifier: str | None = None
    end_node_name: str | None = None
    # 任务最近一次状态时间：创建、最近节点尝试、运行开始/结束中的最新真实时间。
    last_status_at: datetime | None = None
    # 等待人工的任务随行返回那份唯一的人工事项；其它任务为 null。
    manual_item_id: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class RunSnapshotView(ApiModel):
    run_id: str
    run_request_id: str
    status: str
    status_revision: int
    execution_generation: int
    prepared_content_id: str
    capability_bindings: list[dict[str, JsonValue]]
    resource_request: dict[str, JsonValue]
    last_sequence: int
    terminal: bool
    error: dict[str, JsonValue] | None = None
    started_at: datetime | None
    finished_at: datetime | None


class TaskInputSnapshotView(ApiModel):
    input_snapshot_id: str
    task_id: str
    batch_id: str
    parameters: dict[str, JsonScalar]
    inputs: list[dict[str, JsonValue]]
    captured_at: datetime


class BatchPage(ApiModel):
    items: list[BatchView]
    page: int
    page_size: int
    total: int
    sort: str


class TaskPage(ApiModel):
    items: list[TaskView]
    page: int
    page_size: int
    total: int
    sort: str


class ProjectRunOperationSnapshot(ApiModel):
    operation_id: str
    project_id: str
    idempotency_key: str
    kind: str
    status: str
    status_revision: int
    resource: dict[str, JsonValue]
    result: dict[str, JsonValue] | None
    error: dict[str, JsonValue] | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class ProjectRunOperationAccepted(ApiModel):
    operation: ProjectRunOperationSnapshot


class BatchDetail(ApiModel):
    batch: BatchView
    status_counts: dict[str, int]
    task_count: int
    reused_input_group_count: int = Field(0, ge=0)
    unchanged_input_streak: int = Field(0, ge=0)
    stop_operation: ProjectRunOperationSnapshot | None
    force_stop_allowed: bool
    force_stop_available_at: datetime | None
    configuration_snapshot: dict[str, JsonValue]


class TaskDataWriteView(ApiModel):
    kind: str
    table_display: str
    record_display: str
    outcome: str
    node_id: str | None = None
    node_name: str | None = None
    previous_status: str | None = None
    next_status: str | None = None
    reference_display: str | None = None
    before_summary: str | None = None
    after_summary: str | None = None
    detail: str | None = None


class TaskCurrentInputView(ApiModel):
    input_id: str | None = None
    record_ref: dict[str, JsonValue]
    exists: bool
    values: list[dict[str, JsonValue]] = Field(default_factory=list)
    record_status: str | None = None
    content_revision: int | None = None
    updated_at: datetime | None = None
    changed_field_ids: list[str] = Field(default_factory=list)


class CleanupSummaryView(ApiModel):
    status: Literal[
        "notRequired", "pending", "running", "succeeded", "failed", "unknown"
    ]
    operation_id: str | None = None
    message: str | None = None


class TaskDetail(ApiModel):
    automation_name: str | None = None
    batch_started_at: datetime | None = None
    parameter_definitions: list[ParameterDefinition] = Field(default_factory=list)
    node_names: dict[str, str] = Field(default_factory=dict)
    task: TaskView
    input_snapshot: TaskInputSnapshotView
    current_inputs: list[TaskCurrentInputView] = Field(default_factory=list)
    run: RunSnapshotView
    data_writes: list[TaskDataWriteView] = Field(default_factory=list)
    cleanup: CleanupSummaryView


class BatchStopRequest(ApiModel):
    expected_status_revision: StrictInt = Field(ge=1)
    reason: StrictStr = Field(min_length=1, max_length=500)


class DebugInputRequest(ApiModel):
    expected_automation_revision: StrictInt = Field(ge=1)
    choices: dict[str, dict[str, JsonValue] | None] = Field(default_factory=dict)
    input_id: str | None = None
    cursor: str | None = None
    page_size: StrictInt = Field(50, ge=1, le=100)
    search: str = Field('', max_length=200)


class DebugInputResponse(ApiModel):
    selection_status: str
    selection: dict[str, dict[str, JsonValue] | None]
    inputs: list[dict[str, JsonValue]]
    items: list[dict[str, JsonValue]]
    next_cursor: str | None
