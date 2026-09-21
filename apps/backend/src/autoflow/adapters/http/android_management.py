import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Query

from autoflow.application.android.bulk import AndroidBulkService
from autoflow.application.android.cleanup import CleanupService
from autoflow.application.android.diagnostics import (
    EnvironmentCheckResult,
    EnvironmentCheckService,
)
from autoflow.application.android.diagnostics_export import redact_diagnostics
from autoflow.domain.android.management_models import DeviceFacts
from autoflow.domain.android.management_rules import policy_for
from autoflow.domain.android.ports import AndroidError

from .android_fleet_schemas import EnvironmentProfile
from .android_management_schemas import (
    BackupCreate,
    BackupRead,
    BackupRestore,
    BulkAction,
    BulkCreate,
    BulkRead,
    CleanupExecute,
    CleanupPreviewCreate,
    DiagnosticRead,
    DiagnosticsCreate,
    EnvironmentCheckCommand,
    ImageDelete,
    ImagePageRead,
    ImagePullCreate,
    ImageRead,
    ImageRegister,
    ImageVerificationCreate,
    ManagementCapabilitiesRead,
    ManagementDevicePageRead,
    ManagementDeviceRead,
    ManagementEnvironmentRead,
    OperationPageRead,
    OperationRead,
    OperationVerifyCommand,
    ProfileArchiveCommand,
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


def _management_device(device: dict[str, Any]) -> ManagementDeviceRead:
    operation = device.get("operation") or {}
    facts = DeviceFacts(
        device_id=str(device["deviceId"]),
        revision=max(1, int(device.get("generation", 0) or 0)),
        runtime_state=device.get("androidStatus", "unknown"),
        owner_kind="legacyWorkflow" if device.get("ownerRunId") else ("manualSession" if device.get("control") == "manual" else "none"),
        owner_id=device.get("ownerRunId"),
        control=device.get("control", "idle"),
        operation_action=operation.get("action"),
        operation_state=operation.get("state"),
        stale=bool(device.get("stale", False)),
    )
    policy = policy_for(facts)
    return ManagementDeviceRead(
        device_id=facts.device_id,
        revision=facts.revision,
        name=str(device.get("name", "未命名设备")),
        runtime_state=facts.runtime_state,
        owner={"kind": facts.owner_kind, "id": facts.owner_id},
        observed_at=device.get("observedAt"),
        stale=facts.stale,
        spec_snapshot=dict(device.get("creationConfig") or {}),
        latest_operation=operation or None,
        allowed_actions=list(policy.allowed_actions),
        blocked_reasons=policy.blocked_reasons,
    )


def android_management_router(check_service: EnvironmentCheckService, operations: Any | None = None, images: Any | None = None, profiles: Any | None = None, backups: Any | None = None, devices: Any | None = None, bulk: AndroidBulkService | None = None, cleanup: CleanupService | None = None, resources: Any | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/v1/android/management", tags=["android-management"])

    def workspace_identity() -> str:
        return str(getattr(getattr(devices, "management", None), "workspace_identity", "default"))

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
            bulk=bulk is not None,
            backups=backups is not None,
            workflow=False,
            reasons={
                "bulk": "批量操作已注册" if bulk is not None else "批量操作服务未配置",
                "backups": "备份服务已注册" if backups is not None else "备份服务未配置",
                "workflow": "安卓管理不通过工作流执行入口",
            },
        )

    @router.get("/devices", response_model=ManagementDevicePageRead)
    async def management_devices(
        status: str | None = Query(default=None),
        profile_id: str | None = Query(default=None),
        retained: bool | None = Query(default=None),
        cursor: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> ManagementDevicePageRead:
        if devices is None:
            return ManagementDevicePageRead(items=[], next_cursor=None, total=0)
        rows = [item for item in devices.repository.list() if not item.get("deleted")]
        if status:
            rows = [item for item in rows if item.get("androidStatus", "unknown") == status]
        if profile_id:
            rows = [item for item in rows if item.get("profileId") == profile_id]
        if retained is not None:
            rows = [item for item in rows if bool(item.get("dataRetained")) is retained]
        rows.sort(key=lambda item: str(item.get("deviceId", "")))
        total = len(rows)
        if cursor:
            rows = [item for item in rows if str(item.get("deviceId")) > cursor]
        page = rows[:limit]
        return ManagementDevicePageRead(
            items=[_management_device(item) for item in page],
            next_cursor=str(page[-1]["deviceId"]) if len(rows) > limit else None,
            total=total,
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

    @router.get("/operations", response_model=OperationPageRead)
    async def operation_page(device_id: str | None = Query(default=None), cursor: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=200)) -> OperationPageRead:
        if operations is None:
            return OperationPageRead(items=[], next_cursor=None, total=0)
        items = operations.page(device_id, cursor, limit)
        total = operations.count(device_id) if hasattr(operations, "count") else len(items)
        return OperationPageRead(items=[_operation_response(item) for item in items], next_cursor=items[-1].operation_id if len(items) == limit else None, total=total)

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

    @router.get("/images", response_model=ImagePageRead)
    async def image_page() -> ImagePageRead:
        if images is None:
            return ImagePageRead(items=[], next_cursor=None, total=0)
        items = images.list()
        return ImagePageRead(items=[ImageRead.model_validate(item) for item in items], next_cursor=None, total=len(items))

    @router.post("/images", response_model=ImageRead, status_code=201)
    async def register_image(body: ImageRegister) -> ImageRead:
        if images is None:
            raise RuntimeError("Android image service is not configured")
        return ImageRead.model_validate(images.register(body.model_dump(by_alias=True, mode="json")))

    @router.post("/image-pulls", response_model=OperationRead, status_code=202)
    async def image_pull(body: ImagePullCreate) -> OperationRead:
        if images is None or not hasattr(images, "pull"):
            raise AndroidError("ANDROID_IMAGE_PULL_UNAVAILABLE", "镜像拉取适配器尚未配置", 503)
        result = await images.pull(body.request_id, body.reference)
        if operations is None:
            raise AndroidError("ANDROID_OPERATION_UNAVAILABLE", "操作记录服务尚未配置", 503)
        record = operations.accept("default", body.request_id, "image", "pull", body.reference, {"imageId": result.get("imageId")})
        return _operation_response(record)

    @router.delete("/images/{identifier}", response_model=ImageRead)
    async def delete_image(identifier: str, body: ImageDelete) -> ImageRead:
        if images is None:
            raise RuntimeError("Android image service is not configured")
        if body.delete_content and hasattr(images, "delete_content"):
            return ImageRead.model_validate(await images.delete_content(identifier))
        return ImageRead.model_validate(images.delete(identifier, body.delete_content))

    @router.post("/images/{identifier}/verifications", response_model=ImageRead, status_code=201)
    async def verify_image(identifier: str, body: ImageVerificationCreate) -> ImageRead:
        if images is None:
            raise RuntimeError("Android image service is not configured")
        return ImageRead.model_validate(images.verify(identifier, body.model_dump(by_alias=True)))

    @router.get("/profiles/{identifier}", response_model=EnvironmentProfile)
    async def profile(identifier: str) -> EnvironmentProfile:
        if profiles is None:
            raise RuntimeError("Android profile service is not configured")
        return EnvironmentProfile.model_validate(profiles.get("profile", identifier))

    @router.post("/profiles/{identifier}/archive", response_model=EnvironmentProfile)
    async def archive_profile(identifier: str, body: ProfileArchiveCommand) -> EnvironmentProfile:
        if profiles is None:
            raise RuntimeError("Android profile service is not configured")
        item = profiles.get("profile", identifier)
        if item.get("revision") != body.expected_revision:
            raise AndroidError("ANDROID_PROFILE_CONFLICT", "设备模板已更新，请重新加载", 409)
        item["archived"] = True
        profiles.save("profile", item)
        return EnvironmentProfile.model_validate(item)

    @router.get("/backups", response_model=list[BackupRead])
    async def backup_page() -> list[BackupRead]:
        if backups is None:
            return []
        return [BackupRead.model_validate(item) for item in backups.resources.list("backup")]

    @router.post("/backups", response_model=BackupRead, status_code=201)
    async def create_backup(body: BackupCreate) -> BackupRead:
        if backups is None or devices is None or body.device_id is None or body.expected_revision is None:
            raise AndroidError("ANDROID_BACKUP_REQUEST_INVALID", "备份请求缺少设备和版本", 422)
        device = devices.get(body.device_id)
        if int(device.get("generation", 1) or 1) != body.expected_revision:
            raise AndroidError("ANDROID_REVISION_CONFLICT", "设备已发生变化，请重新加载", 409)
        observed = await devices.runtime.inspect(device)
        return BackupRead.model_validate(await backups.create_with_runtime(device, observed, devices.runtime))

    @router.post("/devices/{identifier}/backups", response_model=BackupRead, status_code=201)
    async def backup(identifier: str, body: BackupCreate) -> BackupRead:
        if backups is None or devices is None:
            raise RuntimeError("Android backup service is not configured")
        device = devices.get(identifier)
        observed = await devices.runtime.inspect(device)
        return BackupRead.model_validate(await backups.create_with_runtime(device, observed, devices.runtime))

    @router.post("/backups/{identifier}/restore", status_code=202)
    async def restore_backup(identifier: str, body: BackupRestore) -> dict[str, Any]:
        if backups is None or devices is None:
            raise AndroidError("ANDROID_BACKUP_RESTORE_UNAVAILABLE", "备份恢复服务尚未配置", 503)
        record = next((item for item in backups.resources.list("backup") if item.get("id") == identifier), None)
        if record is None:
            raise AndroidError("ANDROID_BACKUP_NOT_FOUND", "备份不存在或不可恢复", 404)
        environment = await devices.environment()
        if not any(image.get("id") == record.get("imageId") for image in environment.get("images", [])):
            raise AndroidError("ANDROID_BACKUP_IMAGE_MISSING", "备份所需的精确镜像当前不可用", 409)
        config = dict(record.get("config") or {})
        if any(key not in config for key in ("width", "height", "dpi", "cpu", "memoryMb")):
            raise AndroidError("ANDROID_BACKUP_INCOMPATIBLE", "备份缺少可恢复的实例配置快照", 409)
        new_device_id = str(uuid4())
        config.update(deviceId=new_device_id, name=body.new_name, imageId=record["imageId"], instanceType="persistent", start=False)
        created = devices.management.create(config)
        task = devices.management.task
        if task is not None:
            await asyncio.shield(task)
        try:
            await backups.restore_data(identifier, created, devices.runtime)
        except BaseException:
            created.update(control="recovery_required", lastError="恢复数据卷未完成，请核实新实例")
            devices.repository.save(created)
            raise
        return {"deviceId": new_device_id, "backupId": identifier, "state": "restored"}

    @router.post("/bulk-operations", response_model=BulkRead, status_code=202)
    async def bulk_create(body: BulkCreate) -> BulkRead:
        if bulk is None:
            raise RuntimeError("Android bulk service is not configured")
        result = bulk.create("default", body.request_id, body.action, [item.model_dump(by_alias=True) for item in body.items], body.delete_data)
        return BulkRead.model_validate(bulk.run(result["id"]))

    @router.get("/bulk-operations/{identifier}", response_model=BulkRead)
    async def bulk_get(identifier: str) -> BulkRead:
        if bulk is None:
            raise RuntimeError("Android bulk service is not configured")
        return BulkRead.model_validate(bulk.get(identifier))

    @router.post("/bulk-operations/{identifier}/actions", response_model=BulkRead)
    async def bulk_action(identifier: str, body: BulkAction) -> BulkRead:
        if bulk is None:
            raise RuntimeError("Android bulk service is not configured")
        return BulkRead.model_validate(bulk.action(identifier, body.action))

    @router.post("/cleanup/previews")
    async def cleanup_preview(body: CleanupPreviewCreate) -> dict[str, Any]:
        if cleanup is None:
            raise RuntimeError("Android cleanup service is not configured")
        items = cleanup.preview(body.resource_ids, workspace_identity())
        import hashlib
        import json
        digest = hashlib.sha256(json.dumps(items, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {"items": items, "confirmationDigest": digest}

    @router.post("/cleanup")
    async def cleanup_execute(body: CleanupExecute) -> dict[str, Any]:
        if cleanup is None:
            raise RuntimeError("Android cleanup service is not configured")
        return {"items": cleanup.execute(workspace_identity(), body.confirmation_digest), "state": "accepted"}

    @router.post("/diagnostics", response_model=DiagnosticRead, status_code=202)
    async def diagnostics(body: DiagnosticsCreate) -> DiagnosticRead:
        if resources is None:
            raise RuntimeError("Android diagnostics store is not configured")
        record = {"id": body.request_id, "requestId": body.request_id, "state": "ready", "payload": redact_diagnostics({"deviceIds": body.device_ids, "includeAdvancedLogs": body.include_advanced_logs, "workflow": False}), "createdAt": datetime.now(UTC).isoformat()}
        resources.save("diagnostic", record)
        return DiagnosticRead.model_validate(record)

    return router
