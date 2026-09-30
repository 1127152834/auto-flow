from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from .schemas import ApiModel


class OwnerRead(ApiModel):
    kind: Literal["none", "manualSession", "legacyWorkflow", "unknown"]
    id: str | None = None


class ManagementDeviceRead(ApiModel):
    device_id: str
    revision: int = Field(ge=1)
    name: str
    runtime_state: Literal["stopped", "starting", "ready", "retained", "missing", "unknown"]
    restore_state: Literal["pending", "restored"] | None = None
    owner: OwnerRead
    observed_at: datetime | None
    stale: bool
    spec_snapshot: dict[str, Any]
    latest_operation: dict[str, Any] | None
    allowed_actions: list[str]
    blocked_reasons: dict[str, str]


class ManagementDevicePageRead(ApiModel):
    items: list[ManagementDeviceRead]
    next_cursor: str | None = None
    total: int


class EnvironmentCheckRead(ApiModel):
    status: Literal["pass", "fail", "unknown", "unsupported"]
    code: str | None = None
    message: str
    action: str | None = None


class ManagementEnvironmentRead(ApiModel):
    available: bool
    platform_supported: bool | None
    runtime_id: str
    message: str
    images: list[dict[str, Any]] = Field(default_factory=list)
    cpu_count: int = 0
    memory_mb: int = 0
    host_workspace_free_bytes: int | None = Field(default=None, ge=0, strict=True)
    vm_docker_free_bytes: int | None = Field(default=None, ge=0, strict=True)
    checked_at: datetime
    checks: dict[str, EnvironmentCheckRead]
    capabilities: dict[str, bool | str]


class ManagementCapabilitiesRead(ApiModel):
    management: bool | str
    control: bool | str
    images: bool | str
    bulk: bool | str
    backups: bool | str
    workflow: bool
    reasons: dict[str, str]


class OperationRead(ApiModel):
    operation_id: str
    request_id: str
    target_id: str
    action: str
    state: str
    stage_code: str
    stage_label: str
    attempt: int
    retry_of: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_code: str | None = None
    message: str | None = None
    allowed_actions: list[str] = Field(default_factory=list)


class OperationPageRead(ApiModel):
    items: list[OperationRead]
    next_cursor: str | None = None
    total: int


class EnvironmentCheckCommand(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)


class ProfileArchiveCommand(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=0, strict=True)


class OperationVerifyCommand(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)


class ImageRead(ApiModel):
    id: str
    image_id: str
    name: str
    reference: str
    revision: int
    state: str
    verification: dict[str, Any]
    validation: str = "not_tested"
    created_at: datetime
    source_digest: str | None = None
    architecture: str | None = None
    os: str | None = None
    android_version: str | None = None
    google_components: str | None = None
    references: list[dict[str, Any]] = Field(default_factory=list)


class ImagePageRead(ApiModel):
    items: list[ImageRead]
    next_cursor: str | None = None
    total: int


class ImageRegister(ApiModel):
    id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    name: str = Field(min_length=1, max_length=120)
    reference: str = Field(min_length=1, max_length=255)


class ImagePullCreate(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)
    reference: str = Field(min_length=1, max_length=255)
    allow_unknown_disk_estimate: bool = Field(default=False, strict=True)

    @field_validator("reference")
    @classmethod
    def safe_reference(cls, value: str) -> str:
        if any(char.isspace() for char in value) or value.startswith("-"):
            raise ValueError("镜像引用不能包含空白或命令选项")
        return value


class ImageDelete(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=1, strict=True)
    delete_content: bool = False


class ImageDeleteVerification(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)


class ImageVerificationCreate(ApiModel):
    check: str = Field(min_length=1, max_length=80)
    evidence: dict[str, Any] = Field(default_factory=dict)


class BackupRead(ApiModel):
    id: str
    device_id: str
    image_id: str
    format_version: int
    sha256: str
    bytes: int
    created_at: datetime
    state: str


class BackupCreate(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)
    device_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1, strict=True)


class BackupRestore(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)
    new_name: str = Field(min_length=1, max_length=80)
    allow_unknown_disk_estimate: bool = Field(default=False, strict=True)


class BackupRestoreRead(ApiModel):
    operation_id: str | None = None
    request_id: str
    target_id: str
    device_id: str
    backup_id: str
    state: str


class BulkItemCreate(ApiModel):
    device_id: str
    expected_revision: int = Field(ge=1, strict=True)


class BulkCreate(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)
    action: Literal["start", "stop", "restart", "delete"]
    items: list[BulkItemCreate] = Field(min_length=1, max_length=20)
    delete_data: bool = False


class BulkAction(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)
    action: Literal["cancelPending", "retryFailed", "verify"]


class BulkRead(ApiModel):
    id: str
    request_id: str
    action: str
    delete_data: bool
    state: str
    items: list[dict[str, Any]]
    created_at: datetime


class CleanupPreviewItem(ApiModel):
    id: str
    kind: str
    purpose: str
    revision: int = Field(ge=1)
    references: list[dict[str, Any]] = Field(default_factory=list)
    workspace_id: str
    ownership: dict[str, Any]
    size: int = Field(ge=0)
    irreversible_impact: str
    sha256: str | None = None
    path_summary: dict[str, str] | None = None
    summary: dict[str, Any]
    fingerprint: str
    reversible: bool = False


class CleanupResourcePage(ApiModel):
    items: list[CleanupPreviewItem]


class CleanupPreviewRead(ApiModel):
    items: list[CleanupPreviewItem]
    confirmation_digest: str
    preview_id: str


class CleanupRead(ApiModel):
    items: list[CleanupPreviewItem]
    state: str
    operation_id: str | None = None
    request_id: str | None = None
    preview_id: str | None = None


class CleanupPreviewCreate(ApiModel):
    resource_ids: list[str] = Field(min_length=1, max_length=200)


class CleanupExecute(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)
    preview_id: str | None = None
    confirmation_digest: str = Field(min_length=32, max_length=128)


class DiagnosticsCreate(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)
    device_ids: list[str] = Field(default_factory=list, max_length=50)
    include_advanced_logs: bool = False
    advanced_logs_consent: bool = False


class DiagnosticRead(ApiModel):
    id: str
    request_id: str
    state: str
    payload: dict[str, Any]
    created_at: datetime
    expires_at: datetime | None = None
