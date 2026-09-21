"""Shared Studio command envelopes; command-specific payloads remain separate contracts."""

from itertools import pairwise
from typing import Annotated, Any, Literal, Self

from pydantic import ConfigDict, Field, JsonValue, field_validator, model_validator

from .schemas import ApiModel


class StudioCredentialField(ApiModel):
    model_config = ConfigDict(strict=True)
    key: str
    masked: str


class StudioCredentialItem(ApiModel):
    revision: int = Field(default=1, ge=1, le=9007199254740991)
    model_config = ConfigDict(strict=True)
    name: str
    description: str
    fields: list[StudioCredentialField]
    created_at: str = Field(alias="created_at")
    updated_at: str = Field(alias="updated_at")


class StudioCredentialConfirmed(ApiModel):
    model_config = ConfigDict(strict=True)
    success: Literal[True]

    @field_validator("success", mode="before")
    @classmethod
    def explicit_success(cls, value: Any) -> bool:
        if value is not True:
            raise ValueError("凭据操作必须明确确认成功")
        return True


class StudioCredentialList(StudioCredentialConfirmed):
    credentials: list[StudioCredentialItem]
    mock: bool | None = None


class StudioCredentialNames(StudioCredentialConfirmed):
    names: list[str]


class StudioCredentialUpsertRequest(ApiModel):
    model_config = ConfigDict(strict=True)
    name: str = Field(min_length=1, pattern=r"\S")
    fields: dict[str, str] = Field(min_length=1)
    description: str | None = None


class StudioCredentialSaved(StudioCredentialConfirmed):
    name: str
    mock: bool | None = None


class StudioCredentialRenameRequest(ApiModel):
    model_config = ConfigDict(strict=True)
    old_name: str = Field(alias="old_name", min_length=1, pattern=r"\S")
    new_name: str = Field(alias="new_name", min_length=1, pattern=r"\S")


class StudioCredentialFieldRename(ApiModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    kind: Literal["rename"]
    key: str = Field(min_length=1)
    new_key: str = Field(min_length=1, pattern=r"\S")


class StudioCredentialFieldRemove(ApiModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    kind: Literal["remove"]
    key: str = Field(min_length=1)


class StudioCredentialFieldsCommand(ApiModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    command_id: str = Field(min_length=1, max_length=128, pattern=r"\S")
    name: str = Field(min_length=1)
    expected_revision: int = Field(ge=1, le=9007199254740991)
    operations: list[Annotated[
        StudioCredentialFieldRename | StudioCredentialFieldRemove,
        Field(discriminator="kind"),
    ]] = Field(min_length=1)


class StudioCredentialFieldsConfirmed(StudioCredentialConfirmed):
    command_id: str = Field(min_length=1)
    credential: StudioCredentialItem
    mock: bool | None = None


class StudioRetentionConfig(ApiModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    enabled: bool
    recordings_max_days: int = Field(
        alias="recordings_max_days", ge=0, le=9007199254740991
    )
    recordings_max_total_mb: int = Field(
        alias="recordings_max_total_mb", ge=0, le=9007199254740991
    )
    data_max_days: int = Field(alias="data_max_days", ge=0, le=9007199254740991)
    data_max_total_mb: int = Field(alias="data_max_total_mb", ge=0, le=9007199254740991)
    cleanup_interval_hours: int = Field(
        alias="cleanup_interval_hours", ge=1, le=9007199254740991
    )


class StudioRetentionUpdate(ApiModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    enabled: bool | None = None
    recordings_max_days: int | None = Field(
        default=None, alias="recordings_max_days", ge=0, le=9007199254740991
    )
    recordings_max_total_mb: int | None = Field(
        default=None, alias="recordings_max_total_mb", ge=0, le=9007199254740991
    )
    data_max_days: int | None = Field(
        default=None, alias="data_max_days", ge=0, le=9007199254740991
    )
    data_max_total_mb: int | None = Field(
        default=None, alias="data_max_total_mb", ge=0, le=9007199254740991
    )
    cleanup_interval_hours: int | None = Field(
        default=None, alias="cleanup_interval_hours", ge=1, le=9007199254740991
    )


class StudioRetentionUsageEntry(ApiModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)
    count: int = Field(ge=0, le=9007199254740991)
    size_mb: float = Field(alias="sizeMB", ge=0)


class StudioRetentionUsage(ApiModel):
    recordings: StudioRetentionUsageEntry
    data: StudioRetentionUsageEntry


class StudioRetentionConfirmed(ApiModel):
    model_config = ConfigDict(strict=True)
    success: Literal[True]
    mock: bool | None = None

    @field_validator("success", mode="before")
    @classmethod
    def explicit_success(cls, value: Any) -> bool:
        if value is not True:
            raise ValueError("留存操作必须明确确认成功")
        return True


class StudioRetentionSaved(StudioRetentionConfirmed):
    config: StudioRetentionConfig


class StudioRetentionLoaded(StudioRetentionSaved):
    usage: StudioRetentionUsage


class StudioRetentionUsageResponse(StudioRetentionConfirmed):
    usage: StudioRetentionUsage


class StudioRetentionCleanupEntry(ApiModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)
    removed: int = Field(ge=0, le=9007199254740991)
    freed_mb: float = Field(alias="freedMB", ge=0)


class StudioRetentionCleanup(StudioRetentionConfirmed):
    recordings: StudioRetentionCleanupEntry
    data: StudioRetentionCleanupEntry


class StudioCommandReceipt(ApiModel):
    # Preserve command-specific result fields while strictly checking the shared envelope.
    model_config = ConfigDict(extra="allow", strict=True)

    command_id: str = Field(min_length=1, pattern=r"\S")
    success: bool


class StudioCommandLookup(StudioCommandReceipt):
    http_status: int = Field(ge=200, le=599)


class StudioEventCommandRequest(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    command_id: str = Field(min_length=1, max_length=128, pattern=r"\S")
    event: str = Field(min_length=1, max_length=128, pattern=r"\S")
    data: dict[str, Any]


class StudioExecutionLogEntry(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    sequence: int = Field(ge=1, le=9007199254740991)
    id: str = Field(min_length=1, pattern=r"\S")
    timestamp: str = Field(min_length=1, pattern=r"\S")
    level: Literal["debug", "info", "success", "warning", "error"]
    message: str
    node_id: str | None = None
    execution_id: str | None = None
    execution_context: dict[str, JsonValue] | None = None
    duration: float | None = Field(default=None, ge=0)
    details: dict[str, JsonValue] | None = None


class StudioExecutionLogPage(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    run_id: str = Field(min_length=1, pattern=r"\S")
    workflow_id: str = Field(min_length=1, pattern=r"\S")
    items: list[StudioExecutionLogEntry]
    total: int = Field(ge=0, le=9007199254740991)
    next_cursor: int | None = Field(default=None, ge=1, le=9007199254740991)

    @model_validator(mode="after")
    def validate_page(self) -> Self:
        if any(current.sequence <= previous.sequence for previous, current in pairwise(self.items)):
            raise ValueError("日志页必须按序号严格递增")
        if len(self.items) > self.total:
            raise ValueError("日志页条数不能超过总数")
        return self


class StudioWorkflowRunSummary(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    run_id: str = Field(min_length=1, pattern=r"\S")
    workflow_id: str = Field(min_length=1, pattern=r"\S")
    document_id: str = Field(min_length=1, pattern=r"\S")
    workflow_name: str
    status: Literal["starting", "running", "paused", "failed_paused", "completed", "failed", "stopped", "interrupted"]
    started_at: str = Field(min_length=1, pattern=r"\S")
    finished_at: str | None = None
    log_count: int = Field(ge=0, le=9007199254740991)


class StudioWorkflowRunPage(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[StudioWorkflowRunSummary]
    total: int = Field(ge=0, le=9007199254740991)
    next_cursor: int | None = Field(default=None, ge=1, le=9007199254740991)


class StudioRunResultRow(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    sequence: int = Field(ge=1, le=9007199254740991)
    node_id: str
    execution_id: str
    execution_context: dict[str, JsonValue] | None = None
    values: dict[str, JsonValue]
    large_values: dict[str, str] = Field(default_factory=dict)


class StudioRunResultPage(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    run_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    items: list[StudioRunResultRow]
    total: int = Field(ge=0, le=9007199254740991)
    through_sequence: int = Field(ge=0, le=9007199254740991)
    next_cursor: int | None = Field(ge=1, le=9007199254740991)

    @model_validator(mode="after")
    def validate_page(self) -> Self:
        if len(self.items) > self.total or any(row.sequence > self.through_sequence for row in self.items):
            raise ValueError("结果页超出固定截止位置")
        if any(right.sequence <= left.sequence for left, right in pairwise(self.items)):
            raise ValueError("结果序号必须严格递增")
        return self


class StudioRunResultValue(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    run_id: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=9007199254740991)
    key: str
    value: JsonValue


class StudioImageAsset(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    original_name: str = Field(min_length=1)
    size: int = Field(ge=0, le=9_007_199_254_740_991)
    uploaded_at: str
    folder: str
    extension: str
    path: str | None = None


class StudioImageUploadResult(ApiModel):
    asset: StudioImageAsset


class StudioImageMutationResult(ApiModel):
    success: bool = Field(strict=True)


class StudioImageRenameResult(StudioImageMutationResult):
    asset: StudioImageAsset


class StudioImageFolderCreated(StudioImageMutationResult):
    path: str


class StudioImageFolderRenamed(StudioImageMutationResult):
    new_path: str


class StudioImageFolderDeleted(StudioImageMutationResult):
    deleted_count: int = Field(strict=True, ge=0)


class StudioImageMoved(StudioImageMutationResult):
    new_folder: str


class StudioInputPromptRequest(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)

    request_id: str = Field(min_length=1)
    variable_name: str
    title: str
    message: str
    default_value: str | float | bool | None
    input_mode: Literal[
        "single",
        "multiline",
        "number",
        "integer",
        "password",
        "list",
        "file",
        "folder",
        "checkbox",
        "slider_int",
        "slider_float",
        "select_single",
        "select_multiple",
    ]
    min_value: float | None = None
    max_value: float | None = None
    max_length: int | None = None
    required: bool = True
    select_options: list[str] | None = None


class StudioInputPromptResult(ApiModel):
    model_config = ConfigDict(strict=True)

    request_id: str = Field(min_length=1)
    value: str | None


class StudioInputPromptState(ApiModel):
    request_id: str
    workflow_id: str
    node_id: str
    status: Literal["pending", "answered", "cancelled", "expired"]


class StudioSelectorTestRequest(ApiModel):
    model_config = ConfigDict(strict=True)

    selector: str = Field(min_length=1, pattern=r"\S")
    hints: dict[str, Any] | None = None
    highlight: bool = True
    session_id: str | None = Field(default=None, min_length=1, pattern=r"\S")


class StudioSelectorElement(ApiModel):
    tag: str | None = None
    text: str | None = None


class StudioSelectorAttempt(ApiModel):
    selector: str
    count: int | None = Field(default=None, strict=True, ge=0, le=9007199254740991)
    error: str | None = None


class StudioSelectorTestResult(ApiModel):
    model_config = ConfigDict(strict=True)

    success: Literal[True]
    matched: bool
    count: int = Field(ge=0, le=9007199254740991)
    matched_selector: str | None = None
    is_primary: bool | None = None
    element: StudioSelectorElement | None = None
    tried: list[StudioSelectorAttempt] | None = None
    error: str | None = None

    @model_validator(mode="after")
    def check_match_count(self) -> Self:
        if self.matched != (self.count > 0):
            raise ValueError("matched must agree with count")
        return self


class StudioSimilarElements(ApiModel):
    model_config = ConfigDict(strict=True)

    pattern: str = Field(min_length=1, pattern=r"\{index\}")
    count: int = Field(ge=1, le=9007199254740991)
    min_index: int = Field(ge=0, le=9007199254740991)
    max_index: int = Field(ge=0, le=9007199254740991)
    indices: list[int] | None = None
    selector1: str | None = None
    selector2: str | None = None

    @model_validator(mode="after")
    def check_indices(self) -> Self:
        if self.max_index < self.min_index:
            raise ValueError("maxIndex must not precede minIndex")
        if self.indices is not None and any(
            index < self.min_index or index > self.max_index for index in self.indices
        ):
            raise ValueError("indices must be within the reported range")
        return self


class StudioSimilarPickerResult(ApiModel):
    model_config = ConfigDict(strict=True)

    selected: bool
    active: bool
    similar: StudioSimilarElements | None = None

    @model_validator(mode="after")
    def check_selection(self) -> Self:
        if self.selected and self.similar is None:
            raise ValueError("selected results must contain similar elements")
        return self


class StudioBrowserPage(ApiModel):
    model_config = ConfigDict(strict=True)

    page_id: str = Field(min_length=1)
    title: str
    url: str


class StudioBrowserPages(ApiModel):
    model_config = ConfigDict(strict=True)

    session_id: str = Field(min_length=1)
    revision: int = Field(ge=0, le=9007199254740991)
    target_page_id: str | None
    pages: list[StudioBrowserPage]

    @model_validator(mode="after")
    def check_page_identity(self) -> Self:
        ids = [page.page_id for page in self.pages]
        if len(set(ids)) != len(ids):
            raise ValueError("page IDs must be unique")
        if self.target_page_id is not None and self.target_page_id not in ids:
            raise ValueError("target page must exist")
        return self


class StudioBrowserPageCommand(ApiModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    session_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0, le=9007199254740991)
    page_id: str = Field(min_length=1)
    action: Literal["select", "focus", "navigate"]
    url: str | None = None

    @model_validator(mode="after")
    def check_navigation(self) -> Self:
        if self.action == "navigate" and (self.url is None or not self.url.strip()):
            raise ValueError("navigation requires a URL")
        return self


class StudioBrowserStatus(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)

    is_open: bool
    picker_active: bool
    session_id: str | None = None
    profile_id: str | None = None
    picker_session_id: str | None = None


class StudioJsScriptRequest(ApiModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)

    request_id: str = Field(min_length=1, pattern=r"\S")
    workflow_id: str = Field(min_length=1, pattern=r"\S")
    node_id: str = Field(min_length=1, pattern=r"\S")
    code: str = Field(min_length=1, pattern=r"\S")
    variables: dict[str, JsonValue]


class StudioClaimedRequestState(ApiModel):
    request_id: str = Field(min_length=1, pattern=r"\S")
    workflow_id: str = Field(min_length=1, pattern=r"\S")
    node_id: str = Field(min_length=1, pattern=r"\S")
    status: Literal["pending", "claimed", "completed", "failed", "expired"]
    claim_id: str | None = None

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        if self.status == "claimed" and not (self.claim_id and self.claim_id.strip()):
            raise ValueError("已领取请求必须包含领取标识")
        return self


class StudioRequestClaim(ApiModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)

    request_id: str = Field(min_length=1, pattern=r"\S")
    claim_id: str = Field(min_length=1, pattern=r"\S")


class StudioJsScriptState(StudioClaimedRequestState):
    pass


class StudioJsScriptClaim(StudioRequestClaim):
    pass


class StudioSpeechState(StudioClaimedRequestState):
    pass


class StudioSpeechRequest(ApiModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)

    request_id: str = Field(min_length=1, pattern=r"\S")
    workflow_id: str = Field(min_length=1, pattern=r"\S")
    node_id: str = Field(min_length=1, pattern=r"\S")
    text: str = Field(min_length=1, pattern=r"\S")
    lang: str = Field(min_length=1, pattern=r"\S")
    rate: float = Field(ge=0.5, le=2)
    pitch: float = Field(ge=0.5, le=2)
    volume: float = Field(ge=0, le=1)


class StudioSpeechResult(StudioRequestClaim):
    success: bool = Field(strict=True)
    error: str | None = None

    @model_validator(mode="after")
    def validate_error(self) -> Self:
        if not self.success and not (self.error and self.error.strip()):
            raise ValueError("失败结果必须包含错误")
        return self


class StudioDesktopActionState(StudioClaimedRequestState):
    pass


class StudioDesktopActionRequest(ApiModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)

    request_id: str = Field(min_length=1, pattern=r"\S")
    workflow_id: str = Field(min_length=1, pattern=r"\S")
    node_id: str = Field(min_length=1, pattern=r"\S")
    action: Literal[
        "clipboard_write_text",
        "clipboard_write_image",
        "clipboard_read_text",
        "beep",
        "notification",
        "open_path",
        "system_control",
        "lock_screen",
    ]
    payload: dict[str, JsonValue]


class StudioDesktopActionResult(StudioRequestClaim):
    success: bool = Field(strict=True)
    value: JsonValue = None
    error: str | None = None

    @model_validator(mode="after")
    def validate_error(self) -> Self:
        if not self.success and not (self.error and self.error.strip()):
            raise ValueError("失败结果必须包含错误")
        return self


class StudioJsScriptResult(StudioJsScriptClaim):
    success: bool = Field(strict=True)
    result: JsonValue = None
    variables: dict[str, JsonValue] | None = None
    error: str | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.success and self.variables is None:
            raise ValueError("成功结果必须包含变量对象")
        if not self.success and not (self.error and self.error.strip()):
            raise ValueError("失败结果必须包含错误")
        return self


class StudioVariableTrackingRecord(ApiModel):
    # Keep the frozen WebRPA wire names for this existing endpoint.
    model_config = ConfigDict(alias_generator=None, strict=True, allow_inf_nan=False)

    timestamp: str
    variable_name: str
    old_value: JsonValue
    new_value: JsonValue
    node_id: str
    node_name: str
    operation: Literal["create", "update"]
    value_type: str


class StudioVariableTrackingResult(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)

    tracking: list[StudioVariableTrackingRecord]
    count: int = Field(ge=0)

    @model_validator(mode="after")
    def check_count(self) -> Self:
        if self.count != len(self.tracking):
            raise ValueError("count must equal the number of tracking records")
        return self


class StudioVariableTrackingCleared(ApiModel):
    message: str = Field(min_length=1, pattern=r"\S")


class StudioRunVariableTrackingRecord(StudioVariableTrackingRecord):
    sequence: int = Field(ge=1, le=9007199254740991)
    execution_id: str = Field(alias="executionId")
    large_values: dict[str, str] = Field(default_factory=dict, alias="largeValues")


class StudioRunVariableTrackingPage(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: str = Field(min_length=1)
    tracking: list[StudioRunVariableTrackingRecord]
    total: int = Field(ge=0, le=9007199254740991)
    through_sequence: int = Field(ge=0, le=9007199254740991)
    next_cursor: int | None = Field(default=None, ge=1, le=9007199254740991)

    @model_validator(mode="after")
    def validate_page(self) -> Self:
        if len(self.tracking) > self.total or any(row.sequence > self.through_sequence for row in self.tracking):
            raise ValueError("变量追踪页超出固定截止位置")
        if any(right.sequence <= left.sequence for left, right in pairwise(self.tracking)):
            raise ValueError("变量变化序号必须严格递增")
        return self


class StudioRunVariableTrackingCleared(StudioVariableTrackingCleared):
    run_id: str = Field(min_length=1)


class StudioBrowserScriptTarget(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    browser_session_id: str = Field(min_length=1, pattern=r"\S")
    page_id: str = Field(min_length=1, pattern=r"\S")
    revision: int = Field(ge=0, le=9007199254740991)


class StudioBrowserScriptContext(StudioBrowserScriptTarget):
    url: str
    active_request_id: str | None


class StudioBrowserScriptRequest(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: str = Field(min_length=1, pattern=r"\S")
    context: StudioBrowserScriptTarget
    code: str = Field(min_length=1, pattern=r"\S")
    variables: dict[str, JsonValue]

    @model_validator(mode="after")
    def check_size(self) -> Self:
        if len(self.model_dump_json(by_alias=True).encode("utf-8")) > 1024 * 1024:
            raise ValueError("脚本测试请求超过1MiB，未执行")
        return self


class StudioBrowserScriptState(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: str = Field(min_length=1, pattern=r"\S")
    context: StudioBrowserScriptTarget
    status: Literal["running", "completed", "failed", "cancelled", "expired"]
    has_result: bool
    result: JsonValue
    error: str | None
    execution_kind: Literal["browser", "mock"]

    @model_validator(mode="after")
    def check_state(self) -> Self:
        if self.status in {"failed", "expired"}:
            if not self.error or not self.error.strip():
                raise ValueError("失败或过期必须包含错误原因")
        elif self.error is not None:
            raise ValueError("当前状态不能包含错误")
        if self.status != "completed" and self.has_result:
            raise ValueError("只有完成状态可以包含返回值")
        if not self.has_result and self.result is not None:
            raise ValueError("没有返回值时result必须为null")
        return self


class StudioConditionalRequired(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    field: str = Field(min_length=1, pattern=r"\S")
    default: str | None
    map: dict[str, list[str]]

    @model_validator(mode="after")
    def valid_fields(self) -> Self:
        if any(not key.strip() or any(not field.strip() for field in fields) or len(fields) != len(set(fields)) for key, fields in self.map.items()):
            raise ValueError("条件必填字段无效或重复")
        return self


class StudioModuleRequiredFields(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_revision: str = Field(min_length=1, pattern=r"\S")
    covered_modules: list[str]
    required_fields: dict[str, list[str]]
    conditional_required: dict[str, StudioConditionalRequired]
    field_labels: dict[str, dict[str, str]]

    @model_validator(mode="after")
    def valid_coverage(self) -> Self:
        covered = set(self.covered_modules)
        if len(covered) != len(self.covered_modules) or any(not name.strip() for name in covered):
            raise ValueError("模块覆盖列表无效或重复")
        if any(not set(mapping).issubset(covered) for mapping in [self.required_fields.keys(), self.conditional_required.keys(), self.field_labels.keys()]):
            raise ValueError("字段规则不属于覆盖模块")
        if any(any(not field.strip() for field in fields) or len(fields) != len(set(fields)) for fields in self.required_fields.values()):
            raise ValueError("必填字段无效或重复")
        if any(not field.strip() or not label.strip() for labels in self.field_labels.values() for field, label in labels.items()):
            raise ValueError("字段标签无效")
        return self


class StudioMcpServerConfig(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True, allow_inf_nan=False)

    transport: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    cwd: str | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    disabled: bool | None = None
    auto_approve: list[str] | None = None

    @field_validator("transport")
    @classmethod
    def valid_transport(cls, value: str | None) -> str | None:
        if value and value.lower() not in {"stdio", "sse", "http", "streamable_http", "streamable-http"}:
            raise ValueError("MCP 传输方式无效")
        return value


class StudioMcpConfig(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)
    mcp_servers: dict[str, StudioMcpServerConfig]

    @model_validator(mode="after")
    def valid_names(self) -> Self:
        if any(not name.strip() for name in self.mcp_servers):
            raise ValueError("MCP 服务器名称不能为空")
        return self


class StudioMcpConfigResponse(StudioMcpConfig):
    revision: int = Field(ge=0, le=9007199254740991)


class StudioMcpSaveRequest(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    command_id: str = Field(min_length=1, max_length=128, pattern=r"\S")
    expected_revision: int = Field(ge=0, le=9007199254740991)
    config: StudioMcpConfig


class StudioMcpSaved(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)
    success: Literal[True]
    saved: Literal[True]
    command_id: str = Field(min_length=1, max_length=128, pattern=r"\S")
    revision: int = Field(ge=1, le=9007199254740991)

    @field_validator("success", "saved", mode="before")
    @classmethod
    def true_boolean(cls, value: Any) -> bool:
        if value is not True:
            raise ValueError("保存必须明确确认成功")
        return True


class StudioMcpTool(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)
    name: str
    description: str


class StudioMcpServerStatus(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)
    name: str
    transport: str
    disabled: bool
    connected: bool
    tool_count: int = Field(alias="tool_count", ge=0, le=9007199254740991)
    tools: list[StudioMcpTool]
    last_error: str | None = Field(alias="last_error")
    connected_at: str | None = Field(alias="connected_at")
    auto_approve: list[str] = Field(alias="auto_approve")


class StudioMcpStatus(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)
    servers: list[StudioMcpServerStatus]
    total_tools_injected: int = Field(alias="total_tools_injected", ge=0, le=9007199254740991)


class StudioMcpConnected(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)
    name: str
    tool_count: int = Field(alias="tool_count", ge=0, le=9007199254740991)
    transport: str


class StudioMcpFailed(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)
    name: str
    error: str


class StudioMcpReloaded(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)
    connected: list[StudioMcpConnected]
    failed: list[StudioMcpFailed]
    disabled: list[str]
    total_servers: int = Field(alias="total_servers", ge=0, le=9007199254740991)
    command_id: str = Field(min_length=1, max_length=128, pattern=r"\S")
    revision: int = Field(ge=0, le=9007199254740991)


class StudioMcpReloadRequest(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    command_id: str = Field(min_length=1, max_length=128, pattern=r"\S")
    expected_revision: int = Field(ge=0, le=9007199254740991)


class StudioMcpCommandLookup(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)
    command_id: str = Field(min_length=1, max_length=128, pattern=r"\S")
    http_status: int = Field(ge=200, le=599)


class StudioDebugPauseContext(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: str = Field(min_length=1, pattern=r"\S")
    pause_id: str = Field(min_length=1, pattern=r"\S")
    control_revision: int = Field(ge=0, le=9007199254740991)


class StudioDebugControlRequest(StudioDebugPauseContext):
    command_id: str = Field(min_length=1, pattern=r"\S")


class StudioDebugControlReceipt(StudioDebugControlRequest):
    model_config = ConfigDict(extra="allow", strict=True)
    workflow_id: str = Field(min_length=1, pattern=r"\S")
    action: Literal["resume", "step"]
    success: bool
    error: str | None


    @model_validator(mode="after")
    def valid_outcome(self) -> Self:
        if self.success and self.error is not None:
            raise ValueError("成功调试命令不能包含错误")
        if not self.success and (not self.error or not self.error.strip()):
            raise ValueError("失败调试命令必须包含原因")
        return self


class StudioDebugControlLookup(StudioDebugControlReceipt):
    http_status: int = Field(ge=200, le=599)


    @model_validator(mode="after")
    def consistent_http_status(self) -> Self:
        if self.success and self.http_status >= 400:
            raise ValueError("成功调试命令不能使用失败状态码")
        return self


class StudioDebugVariableChange(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: JsonValue


class StudioDebugVariablesRequest(StudioDebugControlRequest):
    changes: list[StudioDebugVariableChange] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        names = [change.name for change in self.changes]
        if len(names) != len(set(names)):
            raise ValueError("一次变量修改不能包含重复名称")
        if len(self.model_dump_json(by_alias=True).encode("utf-8")) > 1024 * 1024:
            raise ValueError("变量修改请求超过1MiB")
        return self


class StudioDebugVariablesReceipt(StudioDebugVariablesRequest):
    model_config = ConfigDict(extra="allow", strict=True)

    workflow_id: str = Field(min_length=1, pattern=r"\S")
    success: bool
    error: str | None

    @model_validator(mode="after")
    def valid_outcome(self) -> Self:
        if self.success and self.error is not None:
            raise ValueError("成功变量命令不能包含错误")
        if not self.success and (not self.error or not self.error.strip()):
            raise ValueError("失败变量命令必须包含原因")
        return self


class StudioPickerSessionRequest(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    session_id: str = Field(min_length=1, pattern=r"\S")


class StudioPickerSessionStartRequest(StudioPickerSessionRequest):
    url: str | None = None
    profile_id: str | None = Field(default=None, min_length=1)


class StudioPickerSessionState(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)

    success: Literal[True]
    session_id: str = Field(min_length=1, pattern=r"\S")
    active: bool
    selected: bool = False


class StudioFolderSelectRequest(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str | None = None
    initial_dir: str | None = None


class StudioFileSelectRequest(StudioFolderSelectRequest):
    file_types: list[Annotated[list[str], Field(min_length=2, max_length=2)]] | None = None


class StudioPathSelectionResult(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)

    success: bool
    path: str | None
    message: str | None = None
    error: str | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.success:
            if self.error:
                raise ValueError("successful selection cannot contain an error")
        elif self.path is not None or not (
            (self.error and self.error.strip()) or self.message == "用户取消选择"
        ):
            raise ValueError("failed selection requires an error or explicit cancellation and a null path")
        return self


class StudioRecorderStartRequest(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str = Field(min_length=1, pattern=r"\S")


class StudioRecorderReadRequest(StudioRecorderStartRequest):
    after_seq: int = Field(default=0, ge=0, le=9007199254740991)


class StudioRecorderEvent(ApiModel):
    # Action-specific payloads remain intact; this envelope freezes delivery identity.
    model_config = ConfigDict(extra="allow", strict=True)
    sequence: int = Field(ge=1, le=9007199254740991)
    type: Literal["navigate", "click", "dblclick", "input", "select", "check", "keypress", "drag", "upload", "scroll"]


class StudioRecorderStarted(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)
    success: bool
    session_id: str = Field(min_length=1, pattern=r"\S")
    recording: bool
    next_seq: int = Field(ge=0, le=9007199254740991)


class StudioRecorderStatus(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)

    success: Literal[True]
    session_id: str | None = Field(default=None, min_length=1, pattern=r"\S")
    recording: bool
    next_seq: int = Field(ge=0, le=9007199254740991)

    @model_validator(mode="after")
    def validate_session(self) -> Self:
        if (self.recording or self.next_seq > 0) and self.session_id is None:
            raise ValueError("录制状态和已确认步骤必须归属明确会话")
        return self


class StudioRecorderTail(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)
    events: list[StudioRecorderEvent]


class StudioRecorderBatch(ApiModel):
    has_more: bool = False
    model_config = ConfigDict(extra="allow", strict=True)
    success: bool
    session_id: str = Field(min_length=1, pattern=r"\S")
    next_seq: int = Field(ge=0, le=9007199254740991)
    data: list[StudioRecorderEvent]

    @model_validator(mode="after")
    def validate_sequence(self) -> Self:
        validate_recorder_tail(self.data, self.next_seq)
        return self


class StudioRecorderStopped(ApiModel):
    has_more: bool = False
    model_config = ConfigDict(extra="allow", strict=True)
    success: bool
    session_id: str = Field(min_length=1, pattern=r"\S")
    next_seq: int = Field(ge=0, le=9007199254740991)
    data: StudioRecorderTail

    @model_validator(mode="after")
    def validate_sequence(self) -> Self:
        validate_recorder_tail(self.data.events, self.next_seq)
        return self


def validate_recorder_tail(events: list[StudioRecorderEvent], next_seq: int) -> None:
    # Empty batches and the first event also need the request's afterSeq at consumption.
    if events and events[-1].sequence != next_seq:
        raise ValueError("录制确认游标与事件尾部不一致")
    if any(current.sequence != previous.sequence + 1 for previous, current in pairwise(events)):
        raise ValueError("录制事件序列必须连续且不重复")


class StudioRecordingReviewWrite(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0, le=9007199254740991)
    auto_wait: bool
    events: list[StudioRecorderEvent]


class StudioRecordingReview(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    document_id: str = Field(min_length=1, pattern=r"\S")
    revision: int = Field(ge=1, le=9007199254740991)
    auto_wait: bool
    events: list[StudioRecorderEvent]
