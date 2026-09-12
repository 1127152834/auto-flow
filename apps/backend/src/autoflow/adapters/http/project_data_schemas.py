from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from .schemas import ApiModel


class SystemTableIdentity(ApiModel):
    mode: Literal["system"]


class FieldTableIdentity(ApiModel):
    mode: Literal["field"]
    field_id: str


class TableResourceLocator(ApiModel):
    type: Literal["table"]
    project_id: str
    table_id: str


class TableSyncSummary(ApiModel):
    status: Literal[
        "notApplicable",
        "idle",
        "pending",
        "sending",
        "verifying",
        "confirmed",
        "failed",
        "unknown",
        "paused",
    ]
    pending_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    last_confirmed_at: datetime | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class TableSlotDefinition(ApiModel):
    slot_id: str
    name: str
    target_table_id: str
    required: bool


class DataTableView(ApiModel):
    project_id: str
    table_id: str
    name: str
    description: str
    source_kind: Literal["local", "excel", "sheets", "unconfigured"]
    dataset_generation: str
    table_revision: int = Field(ge=1)
    identity: Annotated[
        SystemTableIdentity | FieldTableIdentity, Field(discriminator="mode")
    ]
    slot_definitions: list[TableSlotDefinition]
    record_count: int = Field(ge=0)
    sync_summary: TableSyncSummary
    created_at: datetime
    updated_at: datetime


class DataTablePage(ApiModel):
    items: list[DataTableView]
    page: int
    page_size: int
    total: int
    sort: str


class DataTableCreate(ApiModel):
    name: str
    description: str = ""
    source_kind: Literal["local"] = "local"


class DataTablePatch(ApiModel):
    name: str | None = None
    description: str | None = None
    expected_table_revision: int = Field(ge=1, le=9_007_199_254_740_991, strict=True)
