"""Wire contracts for atomic table-schema candidates and preview results."""

from typing import Annotated, Literal

from pydantic import Field, StrictStr

from .project_data_catalog_schemas import (
    DataFieldView,
    DataFieldWrite,
    Revision,
    Scalar,
)
from .schemas import ApiModel


class DataSchemaExisting(ApiModel):
    kind: Literal["existing"]
    field_id: StrictStr
    expected_field_revision: Revision
    definition: DataFieldWrite


class DataSchemaNew(ApiModel):
    kind: Literal["new"]
    client_id: StrictStr
    definition: DataFieldWrite
    source_column_policy: Literal["localOnly"]
    existing_record_default: Scalar = None


class DataSchemaCandidate(ApiModel):
    dataset_generation: StrictStr
    expected_table_revision: Revision
    fields: list[
        Annotated[DataSchemaExisting | DataSchemaNew, Field(discriminator="kind")]
    ]


class DataSchemaCommit(ApiModel):
    candidate: DataSchemaCandidate
    impact_revision: Revision


class DataSchemaIssue(ApiModel):
    code: str
    field_id: str | None
    client_id: str | None
    message: str
    affected_records: int | None
    task_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    run_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    reference_sources: list[str] = Field(
        default_factory=list, exclude_if=lambda value: not value
    )


class DataSchemaReferenceAvailability(ApiModel):
    automations: Literal["notImplemented"]
    sync: Literal["notImplemented"]


class DataSchemaImpact(ApiModel):
    impact_revision: Revision
    calculated_at: str
    expires_at: str
    affected_records: int
    backfill_bytes: int
    blockers: list[DataSchemaIssue]
    warnings: list[DataSchemaIssue]
    reference_availability: DataSchemaReferenceAvailability


class DataSchemaResult(ApiModel):
    action: Literal["saveSchema"]
    dataset_generation: str
    table_revision: Revision
    fields: list[DataFieldView]
    created_field_ids: dict[str, str]
    backfilled_records: int
