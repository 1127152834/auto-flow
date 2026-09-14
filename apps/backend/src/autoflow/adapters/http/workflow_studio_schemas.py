"""Shared Studio command envelopes; command-specific payloads remain separate contracts."""

from typing import Any, Literal, Self

from pydantic import ConfigDict, Field, JsonValue, field_validator, model_validator

from .schemas import ApiModel


class StudioCommandReceipt(ApiModel):
    # Preserve command-specific result fields while strictly checking the shared envelope.
    model_config = ConfigDict(extra="allow", strict=True)

    command_id: str = Field(min_length=1, pattern=r"\S")
    success: bool


class StudioCommandLookup(StudioCommandReceipt):
    http_status: int = Field(ge=200, le=599)


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


class StudioBrowserStatus(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)

    is_open: bool
    picker_active: bool


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


class StudioMcpSaveRequest(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    config: StudioMcpConfig


class StudioMcpSaved(ApiModel):
    model_config = ConfigDict(extra="allow", strict=True)
    success: Literal[True]
    saved: Literal[True]

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


class StudioDebugPauseContext(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)
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
