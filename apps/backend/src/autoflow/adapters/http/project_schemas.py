from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field

from .project_data_catalog_schemas import (
    FieldMutationResult,
    FieldResourceLocator,
    StatusMutationResult,
    StatusResourceLocator,
)
from .project_data_deletion_schemas import RecordDeleteResult, StatusDeleteResult
from .project_data_record_schemas import (
    DataRecordBatchResult,
    DataRecordView,
    RecordResourceLocator,
)
from .project_data_schema_schemas import DataSchemaResult
from .project_data_schemas import DataTableView, TableResourceLocator
from .project_data_status_batch_schemas import (
    CancelRecordStatusesResult,
    RecordStatusBatchOutcome,
)
from .project_excel_schemas import (
    ExcelExportResult,
    ExcelImportResult,
    ExcelInspectionView,
    ExcelReconcileResult,
)
from .schemas import ApiModel


class SourceDefaultProxy(ApiModel):
    mode: Literal["sourceDefault"]


class NoProxy(ApiModel):
    mode: Literal["none"]


class FixedProxy(ApiModel):
    mode: Literal["fixed"]
    proxy_id: str


class PoolProxy(ApiModel):
    mode: Literal["pool"]
    proxy_pool_id: str


ProjectProxy = Annotated[
    SourceDefaultProxy | NoProxy | FixedProxy | PoolProxy, Field(discriminator="mode")
]


class ProjectDefaultResources(ApiModel):
    profile_id: str | None
    proxy: ProjectProxy
    model_provider_id: str | None


class ProjectCapabilities(ApiModel):
    automations: Literal["notImplemented"]
    data: Literal["available"]
    runs: Literal["notImplemented"]
    environments: Literal["notImplemented"]
    statistics: Literal["notImplemented"]
    sync: Literal["notImplemented"]


class ProjectView(ApiModel):
    project_id: str
    name: str
    description: str
    management_revision: int
    lifecycle_state: Literal["active", "closing", "archived", "deleting", "deleted"]
    default_resources: ProjectDefaultResources
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None


class ProjectSummary(ProjectView):
    availability: ProjectCapabilities


class ProjectOverview(ApiModel):
    project: ProjectView
    counts: dict[str, int]
    availability: ProjectCapabilities
    activity: list[dict[str, Any]]
    recent: list[dict[str, Any]]


class ProjectPage(ApiModel):
    items: list[ProjectSummary]
    page: int
    page_size: int
    total: int
    sort: str


class ProjectResourceLocator(ApiModel):
    type: Literal["project"]
    project_id: str


class ProjectOperationView(ApiModel):
    operation_id: str
    project_id: str | None
    idempotency_key: str
    kind: Literal[
        "createProject",
        "updateProject",
        "createTable",
        "updateTable",
        "mutateField",
        "saveTableSchema",
        "mutateStatus",
        "createRecord",
        "createRecords",
        "updateRecord",
        "setRecordStatus",
        "deleteRecord",
        "setRecordStatuses",
        "cancelRecordStatuses",
        "inspectExcel",
        "importExcel",
        "exportXlsx",
        "reconcileOperation",
    ]
    status: Literal["accepted", "running", "reconciling", "succeeded", "failed"]
    status_revision: int
    resource: Annotated[
        ProjectResourceLocator
        | TableResourceLocator
        | FieldResourceLocator
        | StatusResourceLocator
        | RecordResourceLocator,
        Field(discriminator="type"),
    ]
    result: (
        ProjectView
        | DataTableView
        | FieldMutationResult
        | DataSchemaResult
        | StatusMutationResult
        | StatusDeleteResult
        | DataRecordView
        | DataRecordBatchResult
        | RecordDeleteResult
        | RecordStatusBatchOutcome
        | ExcelInspectionView
        | ExcelImportResult
        | ExcelExportResult
        | ExcelReconcileResult
        | CancelRecordStatusesResult
        | None
    )
    error: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class ProjectOperationPage(ApiModel):
    items: list[ProjectOperationView]
    page: int
    page_size: int
    total: int
    sort: str


class OperationAccepted(ApiModel):
    operation: ProjectOperationView


class ProjectOpenResult(ApiModel):
    project: ProjectView
    last_opened_at: datetime


class ProjectCreate(ApiModel):
    name: str
    description: str = ""
    default_resources: ProjectDefaultResources | None = None

    def payload(self):
        value = self.model_dump(by_alias=True, exclude_unset=True)
        return value


class ProjectPatch(ApiModel):
    name: str | None = None
    description: str | None = None
    default_resources: ProjectDefaultResources | None = None
    expected_management_revision: int = Field(ge=1, strict=True)

    def payload(self):
        return self.model_dump(by_alias=True, exclude_unset=True)


class DataRecordBatchResponse(DataRecordBatchResult):
    operation: ProjectOperationView
