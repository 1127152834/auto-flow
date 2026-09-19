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
