"""Processing unit contract (remediation M2 R2-06)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, StrictInt, StrictStr

from .project_data_record_schemas import DataRecordRef
from .project_schemas import ProjectOperationView
from .schemas import ApiModel

UnitState = Literal["pending", "succeeded", "failed_retryable", "quarantined", "needs_review", "skipped"]


class ProcessingUnitView(ApiModel):
    unit_id: str
    processing_input_id: str
    record_ref: DataRecordRef
    identity_namespace: str | None
    state: UnitState
    attempts: int
    processing_cycle: int
    cycle_attempts: int
    last_outcome: Literal["succeeded", "business", "page", "infrastructure", "unknown", "cancelled"] | None
    last_error: dict[str, Any] | None
    last_task_id: str | None
    last_at: datetime | None
    next_eligible_at: datetime | None
    revision: int
    review: dict[str, Any] | None


class ProcessingUnitPage(ApiModel):
    items: list[ProcessingUnitView]
    next_after: str | None


class ProcessingUnitChange(ApiModel):
    expected_revision: StrictInt = Field(ge=1)
    reason: StrictStr = Field(min_length=1, max_length=500)


class ProcessingUnitResolve(ProcessingUnitChange):
    decision: Literal["confirmedSucceeded", "confirmedNotPerformed", "abandon"]


class ProcessingUnitCommandResult(ApiModel):
    operation: ProjectOperationView
    unit: ProcessingUnitView
