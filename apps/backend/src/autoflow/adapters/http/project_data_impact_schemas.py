from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from .project_data_catalog_schemas import (
    DataFieldWrite,
    FieldResourceLocator,
    Revision,
    StatusResourceLocator,
)
from .project_data_record_schemas import RecordResourceLocator
from .project_data_schemas import TableResourceLocator
from .project_sheets_schemas import (
    SheetsConnectionResourceLocator,
    SheetsIdentityStrategy,
    SheetsMappingEntry,
)
from .schemas import ApiModel

ImpactTarget = Annotated[
    FieldResourceLocator
    | RecordResourceLocator
    | StatusResourceLocator
    | TableResourceLocator
    | SheetsConnectionResourceLocator,
    Field(discriminator="type"),
]

ImpactResource = ImpactTarget


class FieldImpactRequest(ApiModel):
    action: Literal["updateField"]
    target: FieldResourceLocator
    change: DataFieldWrite


class StatusDeleteImpactRequest(ApiModel):
    action: Literal["deleteStatus"]
    target: StatusResourceLocator


class RecordDeleteImpactRequest(ApiModel):
    action: Literal["deleteRecord"]
    target: RecordResourceLocator


class SheetsDisconnectChange(ApiModel):
    mode: Literal["disconnect", "forgetCredential"]


class SheetsDisconnectImpactRequest(ApiModel):
    """The frozen `disconnectSheets` action of the shared impact contract."""

    action: Literal["disconnectSheets"]
    target: SheetsConnectionResourceLocator
    change: SheetsDisconnectChange


class SheetsBindingChange(ApiModel):
    """The exact binding a caller intends to publish, minus its CAS revisions."""

    connection_id: str
    spreadsheet_id: str
    sheet_id: int
    identity_strategy: SheetsIdentityStrategy
    mapping: list[SheetsMappingEntry]


class SheetsBindingImpactRequest(ApiModel):
    """First binding and rebinding share one confirmation: the published change."""

    action: Literal["changeSheetsBinding"]
    target: TableResourceLocator
    change: SheetsBindingChange


class SheetsUnbindChange(ApiModel):
    mode: Literal["remove"]


class SheetsUnbindImpactRequest(ApiModel):
    action: Literal["removeSheetsBinding"]
    target: TableResourceLocator
    change: SheetsUnbindChange


MutationImpactRequest = Annotated[
    FieldImpactRequest
    | StatusDeleteImpactRequest
    | RecordDeleteImpactRequest
    | SheetsDisconnectImpactRequest
    | SheetsBindingImpactRequest
    | SheetsUnbindImpactRequest,
    Field(discriminator="action"),
]


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


class DeletionImpactReport(ApiModel):
    impact_revision: Revision
    target: StatusResourceLocator | RecordResourceLocator = Field(discriminator="type")
    change_digest: str
    expected_revisions: dict[str, Revision]
    impacts: list[DataMutationImpact]
    blockers: list[DataMutationBlocker]
    calculated_at: datetime


class SheetsImpactReport(ApiModel):
    """The confirmation a Sheets connection or binding command quotes back."""

    impact_revision: Revision
    target: TableResourceLocator | SheetsConnectionResourceLocator = Field(
        discriminator="type"
    )
    change_digest: str
    expected_revisions: dict[str, Revision]
    impacts: list[DataMutationImpact]
    blockers: list[DataMutationBlocker]
    calculated_at: datetime
