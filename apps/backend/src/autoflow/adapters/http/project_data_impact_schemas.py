from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from .project_data_catalog_schemas import DataFieldWrite, FieldResourceLocator, Revision
from .project_data_record_schemas import RecordResourceLocator
from .schemas import ApiModel

ImpactResource = Annotated[
    FieldResourceLocator | RecordResourceLocator, Field(discriminator="type")
]


class FieldImpactRequest(ApiModel):
    action: Literal["updateField"]
    target: FieldResourceLocator
    change: DataFieldWrite


class DataMutationImpact(ApiModel):
    code: str
    resource: ImpactResource
    message: str
    blocking: bool


class DataMutationBlocker(ApiModel):
    code: str
    resource: ImpactResource
    state: str
    message: str


class FieldImpactReport(ApiModel):
    impact_revision: Revision
    target: FieldResourceLocator
    change_digest: str
    expected_revisions: dict[str, Revision]
    impacts: list[DataMutationImpact]
    blockers: list[DataMutationBlocker]
    calculated_at: datetime
