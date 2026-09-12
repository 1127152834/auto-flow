from datetime import datetime
from typing import Literal

from pydantic import Field

from .project_data_catalog_schemas import Revision, Scalar
from .schemas import ApiModel

RecordKeyType = Literal["text", "integer", "uuid"]


class DataRecordKey(ApiModel):
    type: RecordKeyType
    value: str


class DataRecordRef(ApiModel):
    project_id: str
    table_id: str
    dataset_generation: str
    record_key: DataRecordKey


class RecordResourceLocator(ApiModel):
    type: Literal["record"]
    record_ref: DataRecordRef


class DataCellWrite(ApiModel):
    field_id: str
    value: Scalar


class DataCellView(DataCellWrite):
    source: Literal["local", "remote", "formula"]
    readable: bool
    error: str = Field(default_factory=str, exclude_if=lambda value: value == "")


class DataRecordSlot(ApiModel):
    slot_id: str
    target: DataRecordRef | None


class DataRecordView(ApiModel):
    ref: DataRecordRef
    values: list[DataCellView]
    record_slots: list[DataRecordSlot]
    status_id: str | None
    current_environment_id: str | None
    content_revision: Revision
    status_revision: Revision
    link_revision: Revision
    deleted: bool
    created_at: datetime
    updated_at: datetime


class DataRecordPage(ApiModel):
    items: list[DataRecordView]
    total: int
    page: int
    page_size: int
    sort: str


class DataRecordCreate(ApiModel):
    dataset_generation: str
    values: list[DataCellWrite]


class DataRecordPatch(DataRecordCreate):
    record_key_type: RecordKeyType
    expected_content_revision: Revision


class DataRecordStatusWrite(ApiModel):
    dataset_generation: str
    record_key_type: RecordKeyType
    status_id: str | None
    expected_status_revision: Revision
    expected_from_status_id: str | None = None
