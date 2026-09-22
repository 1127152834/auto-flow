from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, JsonValue, field_validator, model_validator

from .android import AndroidRename
from .schemas import ApiModel


class EnvironmentProfile(AndroidRename):
    id: UUID
    revision: int = Field(default=0, ge=0, strict=True)
    image_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    width: int = Field(default=720, ge=320, le=1920, strict=True)
    height: int = Field(default=1280, ge=320, le=2560, strict=True)
    dpi: int = Field(default=320, ge=120, le=640, strict=True)
    cpu: int = Field(default=1, ge=1, le=8, strict=True)
    memory_mb: int = Field(default=1536, ge=768, le=8192, strict=True)
    locale: str = Field(default="zh-CN", pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")
    timezone: str = "Asia/Shanghai"
    shell_root: Literal["unknown", "available", "unavailable"] = "unknown"
    application_root: Literal["unknown", "available", "unavailable"] = "unknown"
    archived: bool = False

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("请选择有效时区") from None
        return value

    @model_validator(mode="after")
    def even(self) -> "EnvironmentProfile":
        if self.width % 2 or self.height % 2:
            raise ValueError("分辨率须为偶数")
        return self


class BatchCreate(AndroidRename):
    batch_id: UUID
    profile_id: UUID
    profile_revision: int = Field(ge=1, strict=True)
    quantity: int = Field(default=1, ge=1, le=20, strict=True)
    instance_type: Literal["persistent", "temporary"] = "persistent"
    start: bool = True
    width: int = Field(default=720, ge=320, le=1920, strict=True)
    height: int = Field(default=1280, ge=320, le=2560, strict=True)
    locale: str = Field(default="zh-CN", pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")
    timezone: str = "Asia/Shanghai"

    @model_validator(mode="after")
    def values(self) -> "BatchCreate":
        if self.width % 2 or self.height % 2:
            raise ValueError("分辨率须为偶数")
        EnvironmentProfile.valid_timezone(self.timezone)
        return self


class BatchItem(ApiModel):
    device_id: str
    name: str
    state: str
    error: str | None = None


class BatchRead(ApiModel):
    id: str
    created_at: str
    state: str
    request: BatchCreate
    items: list[BatchItem]


class AllocationCreate(ApiModel):
    request_id: UUID
    workflow_id: UUID
    profile_id: UUID
    mode: Literal["specified", "automatic", "temporary"]
    device_id: UUID | None = None
    values: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def selection(self) -> "AllocationCreate":
        if (self.mode == "specified") != (self.device_id is not None):
            raise ValueError("指定设备模式必须且仅能指定一台设备")
        return self


class AllocationRead(ApiModel):
    id: str
    created_at: str
    state: str
    workflow_name: str
    profile_name: str
    device_id: str | None = None
    device_name: str | None = None
    run_id: str | None = None
    error: str | None = None
    request: AllocationCreate


class SessionCreate(ApiModel):
    request_id: UUID
    device_id: UUID
    access: Literal["manual", "readonly"] = "manual"
    client_session_id: str | None = Field(default=None, min_length=1, max_length=128)


class SessionRead(ApiModel):
    id: str
    device_id: str
    generation: int
    access: Literal["manual", "readonly"]
    endpoint: Literal["embedded", "native"] = "embedded"
    state: str
    width: int
    height: int
    latest_operation: str | None = None
    client_session_id: str | None = None


class SessionHeartbeat(ApiModel):
    client_session_id: str = Field(min_length=1, max_length=128)
    generation: int = Field(ge=0, strict=True)


class ControlCommand(ApiModel):
    generation: int = Field(ge=0, strict=True)
    sequence: int = Field(ge=1, strict=True)
    kind: Literal["key", "touch", "text", "rotate", "release"]
    action: int = Field(default=0, ge=0, le=3, strict=True)
    keycode: int = Field(default=0, ge=0, le=288, strict=True)
    x: int = Field(default=0, ge=0, le=4095, strict=True)
    y: int = Field(default=0, ge=0, le=4095, strict=True)
    width: int = Field(default=720, ge=1, le=4096, strict=True)
    height: int = Field(default=1280, ge=1, le=4096, strict=True)
    text: str = Field(default="", max_length=10000)

    @model_validator(mode="after")
    def bounds(self) -> "ControlCommand":
        if self.kind == "touch" and (self.x >= self.width or self.y >= self.height):
            raise ValueError("触控坐标超出画面")
        if self.kind == "key" and self.action not in {0, 1}:
            raise ValueError("按键动作无效")
        return self


class SessionAction(ApiModel):
    generation: int = Field(ge=0, strict=True)
    action: Literal["end", "embedded", "native", "takeover", "resume"]
    request_id: UUID


class AppLaunch(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)
    generation: int = Field(ge=0, strict=True)
    package_name: str = Field(
        pattern=r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$", max_length=240
    )


class AppAction(ApiModel):
    request_id: str = Field(min_length=1, max_length=128)
    generation: int = Field(ge=0, strict=True)
    package_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$", max_length=240)
    action: Literal["stop", "uninstall", "clearData"]


class BatchAction(ApiModel):
    action: Literal["cancel", "retry"]


class AppRecord(ApiModel):
    package_name: str
    version_code: int | None = None
    version_name: str | None = None
    system: bool
    protected: bool


class AppInfo(ApiModel):
    packages: list[str]
    applications: list[AppRecord] = Field(default_factory=list)
    current_package: str | None
    shell_root: str
    application_root: str


class DeviceRunRead(ApiModel):
    run_id: str
    workflow_name: str
    state: str
    current_node_id: str | None = None
    current_step: int = 0
    total_steps: int = 0
    steps: list[dict[str, JsonValue]]
    handoff: dict[str, JsonValue] | None = None
    started_at: str
