from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from .project_data_catalog_schemas import DataFieldWrite, Scalar
from .schemas import ApiModel


class ProjectFileSelectionCreate(ApiModel):
    selection_token: str
    path: str
    project_id: str
    window_id: int = Field(ge=0, strict=True)
    purpose: Literal["inspectExcel", "exportXlsx"]
    expires_at: datetime


class ExcelInspectionCreate(ApiModel):
    selection_token: str


class NewTarget(ApiModel):
    kind: Literal["new"]
    definition: DataFieldWrite


class ExistingTarget(ApiModel):
    kind: Literal["existing"]
    field_id: str


ExcelTarget = Annotated[NewTarget | ExistingTarget, Field(discriminator="kind")]


class ExcelMapping(ApiModel):
    column_index: int = Field(ge=0, le=499, strict=True)
    target: ExcelTarget


class SystemExcelIdentity(ApiModel):
    mode: Literal["system"]


class ColumnExcelIdentity(ApiModel):
    mode: Literal["column"]
    column_index: int = Field(ge=0, le=499, strict=True)


ExcelIdentity = Annotated[
    SystemExcelIdentity | ColumnExcelIdentity, Field(discriminator="mode")
]


class ExcelTableImportCreate(ApiModel):
    name: str
    description: str = ""
    inspection_id: str
    fingerprint: str
    sheet_id: str
    mapping: list[ExcelMapping] = Field(min_length=1, max_length=500)
    identity: ExcelIdentity


class ExcelTableReplace(ApiModel):
    inspection_id: str
    fingerprint: str
    sheet_id: str
    mapping: list[ExcelMapping] = Field(min_length=1, max_length=500)
    identity: ExcelIdentity
    expected_dataset_generation: str
    expected_table_revision: int = Field(ge=1, strict=True)
    impact_revision: int = Field(ge=1, strict=True)


class ExcelExportCreate(ApiModel):
    selection_token: str
    dataset_generation: str
    scope: Literal["all", "filter"]
    filter: str | None = None
    order_by: str | None = None
    field_ids: list[str] = Field(max_length=500)
    include_status: bool


class ExcelSheetInspection(ApiModel):
    sheet_id: str
    name: str
    headers: list[str]
    sample: list[list[Scalar]]
    row_count: int = Field(ge=0)
    ignored_empty_row_count: int = Field(ge=0)
    formula_row_count: list[int]
    identity_candidates: list[int]
    issues: list[str]


class ExcelInspectionView(ApiModel):
    inspection_id: str
    fingerprint: str
    filename: str
    expires_at: datetime
    sheets: list[ExcelSheetInspection]
    issues: list[str]


class ExcelExportResult(ApiModel):
    filename: str
    sha256: str
    record_count: int = Field(ge=0)


from .project_data_schemas import DataTableView, TableResourceLocator


class ExcelImportResult(ApiModel):
    table: DataTableView
    imported_record_count: int = Field(ge=0)
    previous_dataset_generation: str | None = None


class ExcelReplaceImpact(ApiModel):
    target: TableResourceLocator
    impact_revision: int
    expected_revisions: dict[str, str | int]
    record_count: int
    blockers: list[str]
    calculated_at: datetime


class ExcelReconcileResult(ApiModel):
    target_operation_id: str
    status: Literal["accepted", "running", "reconciling", "succeeded", "failed"]
    expected_target_revision: int | None = None
