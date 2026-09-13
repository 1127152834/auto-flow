from typing import Literal

from pydantic import Field

from .project_data_catalog_schemas import Revision
from .project_data_impact_schemas import DataMutationBlocker
from .project_data_record_schemas import DataRecordRef
from .schemas import ApiModel


class RecordStatusTarget(ApiModel):
    record_ref: DataRecordRef
    expected_status_revision: Revision


class RecordStatusBatchRequest(ApiModel):
    status_id: str | None
    targets: list[RecordStatusTarget] = Field(min_length=1, max_length=1000)
    block_size: int = Field(default=100, ge=1, le=100, strict=True)


class RecordStatusBatchCancel(ApiModel):
    expected_operation_revision: Revision


class CancelRecordStatusesResult(ApiModel):
    operation_id: str
    subsequent_blocks_closed: Literal[True]


class CommittedStatusRevision(ApiModel):
    record_ref: DataRecordRef
    status_revision: Revision


class RecordStatusBlock(ApiModel):
    block_index: int
    targets: list[RecordStatusTarget]
    state: Literal["notStarted", "committed", "conflicted"]
    blockers: list[DataMutationBlocker]
    committed_revisions: list[CommittedStatusRevision]


class RecordStatusBatchPreview(ApiModel):
    request: RecordStatusBatchRequest
    blocks: list[RecordStatusBlock]
    checked_at: str


class RecordStatusBatchOutcome(ApiModel):
    outcome: Literal["processing", "completed", "conflicted", "cancelled", "failed"]
    request: RecordStatusBatchRequest
    blocks: list[RecordStatusBlock]
    changed_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    not_started_count: int = Field(ge=0)
    cancelled: bool
