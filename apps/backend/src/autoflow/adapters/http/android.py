from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import Field, field_validator, model_validator

from autoflow.application.android.devices import AndroidDeviceService, device_view
from autoflow.domain.android.ports import AndroidError

from .schemas import ApiModel


class AndroidImage(ApiModel):
    id: str
    name: str
    reference: str


class AndroidEnvironment(ApiModel):
    available: bool
    platform_supported: bool
    runtime_id: str
    message: str
    images: list[AndroidImage] = Field(default_factory=list)
    cpu_count: int = 0
    memory_mb: int = 0


class AndroidOperation(ApiModel):
    id: str
    action: str
    state: str
    stage: str
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class AndroidDeviceRead(ApiModel):
    device_id: str
    name: str
    runtime_id: str
    owner_run_id: str | None
    control: str
    generation: int
    width: int
    height: int
    image_id: str
    android_status: str
    last_error: str | None
    cpu: int = 1
    memory_mb: int = 1536
    dpi: int = 320
    android_version: str | None = None
    architecture: str | None = None
    data_retained: bool = False
    deleted: bool = False
    operation: AndroidOperation | None = None
    profile_id: str | None = None
    profile_name: str | None = None
    instance_type: str = "persistent"
    locale: str = "zh-CN"
    timezone: str = "Asia/Shanghai"


class AndroidRename(ApiModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("请填写有效的实例名称")
        return value


class AndroidCreate(AndroidRename):
    device_id: UUID
    image_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    width: int = Field(default=720, ge=320, le=1920, strict=True)
    height: int = Field(default=1280, ge=320, le=2560, strict=True)
    dpi: int = Field(default=320, ge=120, le=640, strict=True)
    cpu: int = Field(default=1, ge=1, le=8, strict=True)
    memory_mb: int = Field(default=1536, ge=768, le=8192, strict=True)
    start: bool = True

    @model_validator(mode="after")
    def even_dimensions(self) -> "AndroidCreate":
        if self.width % 2 or self.height % 2:
            raise ValueError("分辨率宽高须为偶数")
        return self


class AndroidDeviceCommand(ApiModel):
    request_id: UUID
    action: Literal["start", "stop", "restart", "restore", "delete", "recover"]
    delete_data: bool = False

    @model_validator(mode="after")
    def deletion_scope(self) -> "AndroidDeviceCommand":
        if self.delete_data and self.action != "delete":
            raise ValueError("只有删除实例可以指定删除数据")
        return self


def android_router(service: AndroidDeviceService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/android", tags=["android"])

    @router.get("/environment", response_model=AndroidEnvironment)
    async def environment() -> AndroidEnvironment:
        return AndroidEnvironment.model_validate(await service.environment())

    @router.get("/devices", response_model=list[AndroidDeviceRead])
    async def devices() -> list[AndroidDeviceRead]:
        return [AndroidDeviceRead.model_validate(d) for d in await service.devices()]

    @router.post("/devices", response_model=AndroidDeviceRead, status_code=202)
    async def create(body: AndroidCreate) -> AndroidDeviceRead:
        return AndroidDeviceRead.model_validate(device_view(service.management.create(body.model_dump(by_alias=True, mode="json"))))

    @router.post("/devices/{device_id}/operations", response_model=AndroidDeviceRead, status_code=202)
    async def operation(device_id: UUID, body: AndroidDeviceCommand) -> AndroidDeviceRead:
        return AndroidDeviceRead.model_validate(device_view(service.management.operate(str(device_id), body.model_dump(by_alias=True, mode="json"))))

    @router.get("/devices/{device_id}/preview", response_class=Response)
    async def preview(device_id: UUID) -> Response:
        return Response(await service.preview(str(device_id)), media_type="image/png", headers={"Cache-Control": "no-store"})

    @router.patch("/devices/{device_id}", response_model=AndroidDeviceRead)
    async def rename(device_id: UUID, body: AndroidRename) -> AndroidDeviceRead:
        return AndroidDeviceRead.model_validate(device_view(service.management.rename(str(device_id), body.name)))

    @router.get("/devices/{device_id}", response_model=AndroidDeviceRead)
    async def device(device_id: UUID) -> AndroidDeviceRead:
        for d in await service.devices():
            if d["deviceId"] == str(device_id):
                return AndroidDeviceRead.model_validate(d)
        raise AndroidError("ANDROID_NOT_FOUND", "安卓设备未登记", 404)

    return router
