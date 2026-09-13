from typing import Literal

from .project_data_catalog_schemas import Revision
from .project_data_record_schemas import RecordKeyType, RecordResourceLocator
from .schemas import ApiModel


class StatusDelete(ApiModel):
    expected_status_revision: Revision
    expected_table_revision: Revision
    impact_revision: Revision


class RecordDelete(ApiModel):
    dataset_generation: str
    record_key_type: RecordKeyType
    expected_content_revision: Revision
    expected_status_revision: Revision
    expected_link_revision: Revision
    impact_revision: Revision


class StatusDeleteResult(ApiModel):
    action: Literal["delete"]
    status_id: str
    deleted: Literal[True]
    table_revision: Revision


class RecordDeleteResult(ApiModel):
    target: RecordResourceLocator
    deleted: Literal[True]
