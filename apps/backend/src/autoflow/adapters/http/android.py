from fastapi import APIRouter

from autoflow.application.android.devices import AndroidDeviceService
from autoflow.domain.android.ports import AndroidError

from .schemas import ApiModel


class AndroidEnvironment(ApiModel):
    available: bool
    platform_supported: bool
    runtime_id: str
    message: str


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


def android_router(service: AndroidDeviceService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/android", tags=["android"])

    @router.get("/environment", response_model=AndroidEnvironment)
    async def environment() -> AndroidEnvironment:
        return AndroidEnvironment.model_validate(await service.environment())

    @router.get("/devices", response_model=list[AndroidDeviceRead])
    async def devices() -> list[AndroidDeviceRead]:
        return [AndroidDeviceRead.model_validate(d) for d in await service.devices()]

    @router.get("/devices/{device_id}", response_model=AndroidDeviceRead)
    async def device(device_id: str) -> AndroidDeviceRead:
        for d in await service.devices():
            if d["deviceId"] == device_id:
                return AndroidDeviceRead.model_validate(d)
        raise AndroidError("ANDROID_NOT_FOUND", "安卓设备未登记", 404)

    return router
