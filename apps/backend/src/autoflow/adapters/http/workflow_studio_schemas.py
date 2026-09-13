"""Shared Studio command envelopes; command-specific payloads remain separate contracts."""

from typing import Any, Literal, Self

from pydantic import ConfigDict, Field, JsonValue, model_validator

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


class StudioJsScriptState(ApiModel):
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


class StudioJsScriptClaim(ApiModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)

    request_id: str = Field(min_length=1, pattern=r"\S")
    claim_id: str = Field(min_length=1, pattern=r"\S")


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
