from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, JsonValue, StrictBool, StrictFloat, StrictInt, StrictStr

from .project_automation_schemas import EnvironmentPolicy, ParameterDefinition
from .schemas import ApiModel

JsonScalar = StrictStr | StrictInt | StrictFloat | StrictBool | None


class BatchStartRequest(ApiModel):
    expected_automation_revision: StrictInt = Field(ge=1)
    parameters: dict[str, JsonScalar]
    max_tasks: StrictInt | None = Field(None, ge=1, le=100)
    concurrency: StrictInt | None = Field(None, ge=1)
    environment_override: EnvironmentPolicy | None = None

    def payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_unset=True)


class BatchView(ApiModel):
    batch_id: str
    project_id: str
    automation_id: str
    automation_name: str | None = None
    start_operation_id: str
    status: str
    status_revision: int
    management_revision: int
    requested_count: int
    created_task_count: int
    active_task_count: int
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
    stop_operation: ProjectRunOperationSnapshot | None
    force_stop_allowed: bool
    force_stop_available_at: datetime | None
    configuration_snapshot: dict[str, JsonValue]


class TaskDetail(ApiModel):
    automation_name: str | None = None
    batch_started_at: datetime | None = None
    parameter_definitions: list[ParameterDefinition] = Field(default_factory=list)
    node_names: dict[str, str] = Field(default_factory=dict)
    task: TaskView
    input_snapshot: TaskInputSnapshotView
    run: RunSnapshotView


class BatchStopRequest(ApiModel):
    expected_status_revision: StrictInt = Field(ge=1)
    reason: StrictStr = Field(min_length=1, max_length=500)
