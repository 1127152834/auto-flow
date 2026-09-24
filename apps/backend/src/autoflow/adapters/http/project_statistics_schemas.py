from datetime import datetime

from pydantic import Field

from .schemas import ApiModel


class StatisticsSample(ApiModel):
    succeeded: int
    failed: int
    cancelled: int
    timed_out: int = Field(alias="timed_out")
    interrupted: int


class StatisticsBucket(StatisticsSample):
    bucket_start: datetime
    average_duration_ms: int | None = None


class FailureDestination(ApiModel):
    automation_id: str
    name: str
    count: int
    reason_summary: str | None = None


class ProjectStatistics(ApiModel):
    from_: str
    to: str
    timezone: str
    sample: StatisticsSample
    success_rate: float | None = None
    average_duration_ms: int | None = None
    trend: list[StatisticsBucket]
    failures_by_automation: list[FailureDestination]
    result_set_id: str
    calculated_at: datetime
    expires_at: datetime


class StudioStatisticsNodeCount(ApiModel):
    node_id: str
    count: int


class StudioStatisticsWorkflowCount(ApiModel):
    workflow_id: str
    name: str
    count: int


class StudioStatisticsRun(ApiModel):
    run_id: str
    workflow_id: str
    workflow_name: str
    mode: str | None
    status: str
    started_at: str
    finished_at: str | None


class StudioProjectStatistics(ApiModel):
    project_id: str
    from_: str
    to: str
    calculated_at: str
    total_runs: int
    by_status: dict[str, int]
    success_rate: float | None
    average_duration_ms: int | None
    node_execution_count: int
    extraction_execution_count: int
    artifact_count: int
    diagnostic_count: int
    debug_count: int
    recording_count: int | None
    recording_unavailable_reason: str | None
    latest_activity_at: str | None
    failures_by_node: list[StudioStatisticsNodeCount]
    runs_by_workflow: list[StudioStatisticsWorkflowCount]
    by_trigger: dict[str, int]
    items: list[StudioStatisticsRun]
    next_cursor: int | None
