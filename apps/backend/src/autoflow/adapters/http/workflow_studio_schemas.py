"""Shared Studio command envelopes; command-specific payloads remain separate contracts."""

from typing import Literal

from pydantic import ConfigDict, Field

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
