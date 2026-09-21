from typing import Any

from fastapi import APIRouter, Query

from autoflow.application.android.diagnostics import (
    EnvironmentCheckResult,
    EnvironmentCheckService,
)
from autoflow.domain.android.ports import AndroidError

from .android_fleet_schemas import EnvironmentProfile
from .android_management_schemas import (
    BackupCreate,
    BackupRead,
    EnvironmentCheckCommand,
    ImageDelete,
    ImageRead,
    ImageRegister,
    ManagementCapabilitiesRead,
    ManagementEnvironmentRead,
    OperationRead,
    OperationVerifyCommand,
)


def _environment_response(result: EnvironmentCheckResult) -> ManagementEnvironmentRead:
    legacy = result.legacy
    platform = result.checks["platform"]
    return ManagementEnvironmentRead(
        available=result.capabilities.get("management") is True,
        platform_supported=platform.status == "pass" if platform.status in {"pass", "unsupported"} else None,
        runtime_id=result.runtime_id,
        message=str(legacy.get("message") or platform.message),
        images=list(legacy.get("images") or []),
        cpu_count=int(legacy.get("cpuCount") or 0),
        memory_mb=int(legacy.get("memoryMb") or legacy.get("memoryMB") or 0),
        checked_at=result.checked_at,
        checks={name: check.__dict__ for name, check in result.checks.items()},
        capabilities=result.capabilities,
    )


def _operation_response(record: Any) -> OperationRead:
    terminal = record.state in {"succeeded", "failed", "cancelled", "needs_verification"}
    return OperationRead(
        operation_id=record.operation_id,
        request_id=record.request_id,
        target_id=record.target_id,
        action=record.action,
        state=record.state,
        stage_code=record.stage_code,
        stage_label=record.stage_label,
        attempt=record.attempt,
        retry_of=record.retry_of,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        result_code=record.result_code,
        message=record.message,
        allowed_actions=["verify"] if record.state == "needs_verification" else ([] if terminal else ["verify"]),
    )


def android_management_router(check_service: EnvironmentCheckService, operations: Any | None = None, images: Any | None = None, profiles: Any | None = None, backups: Any | None = None, devices: Any | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/v1/android/management", tags=["android-management"])

    @router.get("/environment", response_model=ManagementEnvironmentRead)
    async def environment() -> ManagementEnvironmentRead:
        return _environment_response(await check_service.check("management-environment"))

    @router.get("/capabilities", response_model=ManagementCapabilitiesRead)
    async def capabilities() -> ManagementCapabilitiesRead:
        result = await check_service.check("management-capabilities")
        return ManagementCapabilitiesRead(
            management=result.capabilities.get("management", "unknown"),
            control=result.capabilities.get("control", "unknown"),
            images=result.capabilities.get("images", "unknown"),
            bulk=False,
            backups=False,
            workflow=False,
            reasons={
                "bulk": "AM3 尚未启用",
                "backups": "AM4 尚未启用",
                "workflow": "安卓管理不通过工作流执行入口",
            },
        )

    @router.post("/environment/checks", response_model=OperationRead, status_code=202)
    async def environment_check(body: EnvironmentCheckCommand) -> OperationRead:
        if operations is None:
            raise RuntimeError("Android operation repository is not configured")
        record = operations.accept("default", body.request_id, "environment", "check", "environment-check-v1", {})
        if record.state == "queued":
            record = operations.transition(record.operation_id, "queued", "running", {"stage_code": "checking"})
            try:
                await check_service.check(body.request_id)
            except Exception as error:  # noqa: BLE001 - a lost diagnostic result must become needs_verification
                record = operations.transition(record.operation_id, "running", "needs_verification", {"result_code": "CHECK_RESULT_UNKNOWN", "message": str(error)[:480]})
            else:
                record = operations.transition(record.operation_id, "running", "succeeded", {"stage_code": "checked"})
        return _operation_response(record)

    @router.get("/operations", response_model=list[OperationRead])
    async def operation_page(device_id: str | None = Query(default=None), cursor: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=100)) -> list[OperationRead]:
        if operations is None:
            return []
        return [_operation_response(item) for item in operations.page(device_id, cursor, limit)]

    @router.get("/operations/by-request/{request_id}", response_model=OperationRead)
    async def operation_by_request(request_id: str) -> OperationRead:
        if operations is None:
            raise RuntimeError("Android operation repository is not configured")
        return _operation_response(operations.by_request("default", request_id))

    @router.get("/operations/{operation_id}", response_model=OperationRead)
    async def operation(operation_id: str) -> OperationRead:
        if operations is None:
            raise RuntimeError("Android operation repository is not configured")
        return _operation_response(operations.get(operation_id))

    @router.post("/operations/{operation_id}/verify", response_model=OperationRead)
    async def verify(operation_id: str, body: OperationVerifyCommand) -> OperationRead:
        if operations is None:
            raise RuntimeError("Android operation repository is not configured")
        record = operations.get(operation_id)
        if record.state == "needs_verification":
            raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "尚未接入运行时核实，操作保持待核实", 503)
        return _operation_response(record)

    @router.get("/images", response_model=list[ImageRead])
    async def image_page() -> list[ImageRead]:
        if images is None:
            return []
        return [ImageRead.model_validate(item) for item in images.list()]

    @router.post("/images", response_model=ImageRead, status_code=201)
    async def register_image(body: ImageRegister) -> ImageRead:
        if images is None:
            raise RuntimeError("Android image service is not configured")
        return ImageRead.model_validate(images.register(body.model_dump(by_alias=True, mode="json")))

    @router.delete("/images/{identifier}", response_model=ImageRead)
    async def delete_image(identifier: str, body: ImageDelete) -> ImageRead:
        if images is None:
            raise RuntimeError("Android image service is not configured")
        return ImageRead.model_validate(images.delete(identifier, body.delete_content))

    @router.get("/profiles/{identifier}", response_model=EnvironmentProfile)
    async def profile(identifier: str) -> EnvironmentProfile:
        if profiles is None:
            raise RuntimeError("Android profile service is not configured")
        return EnvironmentProfile.model_validate(profiles.get("profile", identifier))

    @router.post("/profiles/{identifier}/archive", response_model=EnvironmentProfile)
    async def archive_profile(identifier: str) -> EnvironmentProfile:
        if profiles is None:
            raise RuntimeError("Android profile service is not configured")
        item = profiles.get("profile", identifier)
        item["archived"] = True
        profiles.save("profile", item)
        return EnvironmentProfile.model_validate(item)

    @router.get("/backups", response_model=list[BackupRead])
    async def backup_page() -> list[BackupRead]:
        if backups is None:
            return []
        return [BackupRead.model_validate(item) for item in backups.resources.list("backup")]

    @router.post("/devices/{identifier}/backups", response_model=BackupRead, status_code=201)
    async def backup(identifier: str, body: BackupCreate) -> BackupRead:
        if backups is None or devices is None:
            raise RuntimeError("Android backup service is not configured")
        device = devices.get(identifier)
        observed = await devices.runtime.inspect(device)
        return BackupRead.model_validate(backups.create(device, observed))

    return router
