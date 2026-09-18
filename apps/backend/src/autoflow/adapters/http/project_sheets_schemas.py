"""Google Sheets transport models. Ownership and transactions stay in the services."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from .project_data_record_schemas import DataRecordRef
from .schemas import ApiModel

CredentialState = Literal["available", "missing", "invalid"]
SyncStatus = Literal[
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
SyncKind = Literal["pull", "push", "reconcile", "binding", "column", "systemIdentity"]


class GoogleAuthorizationCreate(ApiModel):
    project_id: str
    account_label: str
    auth_method: Literal["oauth", "service_account"]
    credential: dict[str, Any] | str


class GoogleAuthorization(ApiModel):
    authorization_token: str
    account_label: str
    writable: bool


class SheetsConnection(ApiModel):
    connection_id: str
    account_label: str
    credential_state: CredentialState
    readable: bool
    writable: bool
    updated_at: datetime


class SheetsConnectionDirectory(ApiModel):
    items: list[SheetsConnection]


class SheetsConnectionCreate(ApiModel):
    account_label: str
    authorization_token: str


class SheetsConnectionDelete(ApiModel):
    impact_revision: int
    mode: Literal["disconnect", "forgetCredential"]


class SheetsConnectionDeleteResult(ApiModel):
    connection_id: str
    disconnected: bool


class SheetsIdentityStrategy(ApiModel):
    kind: Literal["column", "system"]
    column_id: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class SheetsMappingEntry(ApiModel):
    field_id: str
    column_id: str
    direction: Literal["read", "write", "both"]
    formula: bool


class SheetsBinding(ApiModel):
    connection_id: str
    spreadsheet_id: str
    sheet_id: int
    spreadsheet_title: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    sheet_name: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    binding_epoch: int
    identity_strategy: SheetsIdentityStrategy
    mapping: list[SheetsMappingEntry]
    sync_paused: bool


class SheetsBindingWrite(ApiModel):
    connection_id: str
    spreadsheet_id: str
    sheet_id: int
    identity_strategy: SheetsIdentityStrategy
    mapping: list[SheetsMappingEntry]
    impact_revision: int
    expected_table_revision: int
    expected_binding_epoch: int | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class SheetsBindingDelete(ApiModel):
    impact_revision: int
    expected_table_revision: int


class SheetsColumn(ApiModel):
    column_id: str
    name: str
    formula: bool


class SheetsIssue(ApiModel):
    code: str
    message: str
    column_id: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class SheetsIdentitySummary(ApiModel):
    unique: bool
    missing: int = Field(ge=0)
    duplicates: int = Field(ge=0)


class SheetsOverlap(ApiModel):
    project_id: str
    table_id: str
    column_ids: list[str]


class SheetsInspection(ApiModel):
    valid: bool
    issues: list[SheetsIssue]
    columns: list[SheetsColumn]
    identity_summary: SheetsIdentitySummary
    overlaps: list[SheetsOverlap]
    spreadsheet_title: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    sheet_name: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    binding_epoch: int | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class SheetsInspectionCreate(ApiModel):
    connection_id: str
    spreadsheet_id: str
    sheet_id: int
    identity_strategy: SheetsIdentityStrategy
    mapping: list[SheetsMappingEntry]


class SheetsInspectionResult(ApiModel):
    operation: dict
    inspection: SheetsInspection


class SyncEvidence(ApiModel):
    checked_at: datetime
    target: str
    fields: list[str]
    outcome: Literal["matched", "notMatched", "ambiguous"]


class SyncError(ApiModel):
    """The failure a sync command reports back with its counts.

    ``upstreamStatus`` is -1 when the request never left (configuration or
    transport refused it) and 0 when Google accepted the request but the
    result is unknown, so a caller can tell "not sent" from "may have sent".
    """

    code: str
    message: str
    upstream_status: int | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    retryable: bool | None = Field(default=None, exclude_if=lambda value: value is None)


class SyncSummary(ApiModel):
    status: SyncStatus
    pending_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    last_confirmed_at: datetime | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class SyncOperation(ApiModel):
    sync_operation_id: str
    project_id: str
    table_id: str
    record: DataRecordRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    kind: SyncKind
    binding_epoch: int
    target_content_revision: int | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    status: SyncStatus
    status_revision: int
    operation_id: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    evidence: SyncEvidence | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    error: dict | None = Field(default=None, exclude_if=lambda value: value is None)
    created_at: datetime
    updated_at: datetime


class SyncOperationPage(ApiModel):
    items: list[SyncOperation]
    page: int
    page_size: int
    total: int


class SyncStateView(ApiModel):
    summary: SyncSummary
    binding: SheetsBinding | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class SyncPullRequest(ApiModel):
    expected_table_revision: int


class SyncPushRequest(ApiModel):
    mode: Literal["due", "allPending"]
    expected_binding_epoch: int


class SyncRunResult(ApiModel):
    """The result of one sync command, in one shape for every command type."""

    sync_operation_id: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    outcome: str | None = Field(default=None, exclude_if=lambda value: value is None)
    summary: SyncSummary | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    connection: SheetsConnection | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    binding: SheetsBinding | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    inspection: SheetsInspection | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    rows: int | None = Field(default=None, exclude_if=lambda value: value is None)
    created: int | None = Field(default=None, exclude_if=lambda value: value is None)
    refreshed: int | None = Field(default=None, exclude_if=lambda value: value is None)
    conflicts: int | None = Field(default=None, exclude_if=lambda value: value is None)
    confirmed: int | None = Field(default=None, exclude_if=lambda value: value is None)
    failed: int | None = Field(default=None, exclude_if=lambda value: value is None)
    unknown: int | None = Field(default=None, exclude_if=lambda value: value is None)
    targets: list[int] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    error: SyncError | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class SyncPauseRequest(ApiModel):
    expected_binding_epoch: int


class SyncStatusRevisionRequest(ApiModel):
    expected_status_revision: int


class SyncAbandonRequest(ApiModel):
    expected_status_revision: int
    reason: str
