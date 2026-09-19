from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field

from .project_automation_schemas import AutomationView
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
from .project_run_schemas import BatchView
from .project_sheets_schemas import (
    SheetsBinding,
    SheetsConnection,
    SheetsConnectionResourceLocator,
    SheetsDisconnectResult,
    SheetsInspection,
    SheetsUnbindResult,
    SyncOperation,
    SyncRunResult,
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
    automations: Literal["available"]
    data: Literal["available"]
    runs: Literal["available"]
    environments: Literal["available"]
    statistics: Literal["available"]
    sync: Literal["available"]


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


class ProjectPage(ApiModel):
    items: list[ProjectSummary]
    page: int
    page_size: int
    total: int
    sort: str


class ProjectResourceLocator(ApiModel):
    type: Literal["project"]
    project_id: str


class AutomationResourceLocator(ApiModel):
    type: Literal["automation"]
    project_id: str
    automation_id: str


class BatchResourceLocator(ApiModel):
    type: Literal["batch"]
    project_id: str
    batch_id: str


class TaskResourceLocator(ApiModel):
    type: Literal["task"]
    project_id: str
    task_id: str


class SyncResourceLocator(ApiModel):
    type: Literal["sync"]
    project_id: str
    table_id: str
    sync_operation_id: str



class EnvironmentResourceLocator(ApiModel):
    type: Literal["environment"]
    project_id: str
    environment_id: str


OverviewResourceLocator = Annotated[
    ProjectResourceLocator
    | AutomationResourceLocator
    | BatchResourceLocator
    | TaskResourceLocator
    | TableResourceLocator
    | RecordResourceLocator
    | FieldResourceLocator
    | StatusResourceLocator
    | SheetsConnectionResourceLocator
    | SyncResourceLocator
    | EnvironmentResourceLocator,
    Field(discriminator="type"),
]


class Blocker(ApiModel):
    code: str
    resource: OverviewResourceLocator
    state: str
    message: str
    operation_id: str | None = None


class Impact(ApiModel):
    code: str
    resource: OverviewResourceLocator
    message: str
    blocking: bool


class AutomationImpactView(ApiModel):
    impact_revision: int
    impacts: list[Impact]
    blockers: list[Blocker]


class ProjectLifecycleImpact(ApiModel):
    impact_revision: int
    blockers: list[Blocker]
    impacts: list[Impact]
    unsynced_count: int


class ArchiveProjectRequest(ApiModel):
    impact_revision: int
    expected_management_revision: int

    def payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class RestoreProjectRequest(ApiModel):
    expected_management_revision: int

    def payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class DeleteProjectRequest(ApiModel):
    confirmation_name: str
    impact_revision: int
    expected_management_revision: int

    def payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class AttentionItem(ApiModel):
    kind: Literal["batch", "task", "manual", "resource", "sync", "cleanup"]
    resource: OverviewResourceLocator
    severity: Literal["info", "warning", "error"]
    message: str
    occurred_at: datetime


class ActivityItem(ApiModel):
    activity_id: str
    kind: str
    resource: OverviewResourceLocator
    summary: str
    occurred_at: datetime


class DataChanges(ApiModel):
    timezone: str
    day_start: datetime
    new_records: int
    updated_records: int


class ProjectOverview(ApiModel):
    project: ProjectView
    counts: dict[str, int]
    availability: ProjectCapabilities
    activity: list[AttentionItem]
    current: list[ActivityItem]
    recent: list[ActivityItem]
    data_changes: DataChanges | None = None


class ProjectBatchResult(ApiModel):
    batch: BatchView


class DeletedResourceResult(ApiModel):
    target: OverviewResourceLocator
    deleted: Literal[True]
    workflow_id: str | None = None
    workflow_disposition: Literal["unlink", "deleteOwned"] | None = None


class ProjectOperationView(ApiModel):
    operation_id: str
    project_id: str | None
    idempotency_key: str
    kind: Literal[
        "createProject",
        "updateProject",
        "createAutomation",
        "updateAutomation",
        "startBatch",
        "stopBatch",
        "forceStopBatch",
        "followUpBatch",
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
        "connectSheets",
        "disconnectSheets",
        "inspectSheets",
        "changeSheetsBinding",
        "removeSheetsBinding",
        "syncPull",
        "syncPush",
        "reconcileSync",
        "archiveProject",
        "restoreProject",
        "deleteProject",
        "deleteAutomation",
        "deleteEnvironment",
    ]
    status: Literal["accepted", "running", "reconciling", "succeeded", "failed"]
    status_revision: int
    resource: Annotated[
        ProjectResourceLocator
        | AutomationResourceLocator
        | BatchResourceLocator
        | TableResourceLocator
        | FieldResourceLocator
        | StatusResourceLocator
        | RecordResourceLocator
        | SheetsConnectionResourceLocator,
        Field(discriminator="type"),
    ]
    result: (
        ProjectView
        | AutomationView
        | ProjectBatchResult
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
        | SheetsConnection
        | SheetsDisconnectResult
        | SheetsInspection
        | SheetsBinding
        | SheetsUnbindResult
        | SyncRunResult
        | SyncOperation
        | DeletedResourceResult
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
