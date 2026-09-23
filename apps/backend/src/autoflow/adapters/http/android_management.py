import asyncio
import hashlib
import hmac
import inspect
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Header, Query, Request

from autoflow.application.android.bulk import AndroidBulkService
from autoflow.application.android.cleanup import CleanupService
from autoflow.application.android.diagnostics import (
    EnvironmentCheckResult,
    EnvironmentCheckService,
)
from autoflow.application.android.diagnostics_export import diagnostic_snapshot
from autoflow.application.android.verification import verify_lifecycle_operation
from autoflow.domain.android.management_models import DeviceFacts
from autoflow.domain.android.management_rules import policy_for, restore_pending
from autoflow.domain.android.ports import AndroidError

from .android_fleet_schemas import EnvironmentProfile
from .android_management_schemas import (
    BackupCreate,
    BackupRead,
    BackupRestore,
    BackupRestoreRead,
    BulkAction,
    BulkCreate,
    BulkRead,
    CleanupExecute,
    CleanupPreviewCreate,
    CleanupPreviewRead,
    CleanupRead,
    CleanupResourcePage,
    DiagnosticRead,
    DiagnosticsCreate,
    EnvironmentCheckCommand,
    ImageDelete,
    ImageDeleteVerification,
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


def _management_device(device: dict[str, Any], observation: Any | None = None, *, observation_service: bool = False) -> ManagementDeviceRead:
    operation = device.get("operation") or {}
    control = device.get("control")
    manual_controls = {"manual", "opening_manual", "closing_manual"}
    if observation_service and observation is None:
        # A persisted ready flag predates this process and is not a current fact.
        runtime_state, observed_at, stale = "unknown", None, True
    else:
        runtime_state = observation.runtime_state if observation is not None else device.get("androidStatus", "unknown")
        observed_at = observation.observed_at if observation is not None else device.get("observedAt")
        stale = observation.stale if observation is not None else bool(device.get("stale", False))
    facts = DeviceFacts(
        device_id=str(device["deviceId"]),
        revision=max(1, int(device.get("generation", 0) or 0)),
        runtime_state=runtime_state,
        owner_kind="manualSession" if control in manual_controls else ("legacyWorkflow" if device.get("ownerRunId") else "none"),
        owner_id=device.get("ownerRunId"),
        control=control or "idle",
        operation_action=operation.get("action"),
        operation_state=operation.get("state"),
        stale=stale,
        restore_pending=restore_pending(device),
    )
    policy = policy_for(facts)
    return ManagementDeviceRead(
        device_id=facts.device_id,
        revision=facts.revision,
        name=str(device.get("name", "未命名设备")),
        runtime_state=facts.runtime_state,
        restore_state="pending" if facts.restore_pending else ("restored" if device.get("restoreState") == "restored" else None),
        owner={"kind": facts.owner_kind, "id": facts.owner_id},
        observed_at=observed_at,
        stale=facts.stale,
        spec_snapshot=dict(device.get("creationConfig") or {}),
        latest_operation=operation or None,
        allowed_actions=list(policy.allowed_actions),
        blocked_reasons=policy.blocked_reasons,
    )


def _backup_response(record: dict[str, Any]) -> BackupRead:
    return BackupRead.model_validate({
        "id": record["id"],
        "deviceId": record["deviceId"],
        "imageId": record["imageId"],
        "formatVersion": record["formatVersion"],
        "sha256": record["sha256"],
        "bytes": record["bytes"],
        "createdAt": record["createdAt"],
        "state": record["state"],
    })


def _diagnostic_response(record: dict[str, Any]) -> DiagnosticRead:
    return DiagnosticRead.model_validate({
        "id": record["id"],
        "requestId": record["requestId"],
        "state": record["state"],
        "payload": record["payload"],
        "createdAt": record["createdAt"],
        "expiresAt": record.get("expiresAt"),
    })


def android_management_internal_router(resources: Any, workspace_identity: Callable[[], str]) -> APIRouter:
    router = APIRouter(prefix="/internal/android/management", include_in_schema=False)

    @router.get("/diagnostics/{identifier}", response_model=DiagnosticRead)
    def diagnostic_download(
        identifier: str,
        request: Request,
        x_autoflow_host_token: str | None = Header(default=None, alias="x-autoflow-host-token"),
    ) -> DiagnosticRead:
        expected = getattr(getattr(request.app.state, "config", None), "host_token", None)
        if not expected or not hmac.compare_digest(x_autoflow_host_token or "", expected):
            raise AndroidError("ANDROID_DIAGNOSTIC_UNAUTHORIZED", "诊断下载未获授权", 401)
        workspace = workspace_identity()
        record = next(
            (
                item
                for item in resources.list("diagnostic")
                if item.get("id") == identifier and item.get("workspaceId") == workspace
            ),
            None,
        )
        if record is None:
            raise AndroidError("ANDROID_DIAGNOSTIC_NOT_FOUND", "诊断记录不存在或不属于当前工作区", 404)
        expires_at = record.get("expiresAt")
        if not isinstance(expires_at, str):
            raise AndroidError("ANDROID_DIAGNOSTIC_EXPIRED", "诊断下载授权已失效，请重新生成", 410)
        try:
            expired = datetime.fromisoformat(expires_at) <= datetime.now(UTC)
        except (TypeError, ValueError) as error:
            raise AndroidError("ANDROID_DIAGNOSTIC_EXPIRED", "诊断下载授权已失效，请重新生成", 410) from error
        if expired:
            raise AndroidError("ANDROID_DIAGNOSTIC_EXPIRED", "诊断下载授权已失效，请重新生成", 410)
        return _diagnostic_response(record)

    return router


def _profile_response(value: dict[str, Any]) -> EnvironmentProfile:
    # archiveRequestId is an internal replay key and ApiModel rejects unknown
    # fields; keep it out of every profile DTO, including GET after archive.
    return EnvironmentProfile.model_validate(
        {key: data for key, data in value.items() if key != "archiveRequestId"}
    )


def android_management_router(check_service: EnvironmentCheckService, operations: Any | None = None, images: Any | None = None, profiles: Any | None = None, backups: Any | None = None, devices: Any | None = None, bulk: AndroidBulkService | None = None, cleanup: CleanupService | None = None, resources: Any | None = None, observations: Any | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/v1/android/management", tags=["android-management"])

    def workspace_identity() -> str:
        try:
            return str(getattr(getattr(devices, "management", None), "workspace_identity", "default"))
        except RuntimeError:
            # The schema exporter binds an unavailable sentinel instead of runtime
            # services.  Resolving workspace identity is a business lookup, so it
            # must remain deferred until request handling in that mode.
            return "default"

    async def diagnostic_payload(body: DiagnosticsCreate, workspace: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "deviceIds": body.device_ids,
            "includeAdvancedLogs": body.include_advanced_logs,
            "workflow": False,
        }
        if body.include_advanced_logs:
            payload["advancedLogs"] = {
                "status": "unsupported",
                "code": "ANDROID_DIAGNOSTICS_ADVANCED_LOGS_UNSUPPORTED",
                "message": "当前未配置受控高级日志采集器",
            }
        try:
            environment = check_service.check(f"{body.request_id}:environment")
            if inspect.isawaitable(environment):
                environment = await environment
            if isinstance(environment, EnvironmentCheckResult):
                payload["environment"] = environment.as_dict()
        except Exception as error:  # noqa: BLE001 - diagnostics remain exportable when a probe is unavailable.
            payload["environment"] = {"status": "unknown", "code": "ANDROID_DIAGNOSTICS_ENVIRONMENT_UNKNOWN", "message": str(error)[:240]}
        repository = getattr(devices, "repository", None)
        if repository is not None and callable(getattr(repository, "list", None)):
            wanted = set(body.device_ids)
            runtime_workspace = getattr(getattr(devices, "runtime", None), "workspace_id", workspace)
            payload["devices"] = [
                _management_device(row).model_dump(by_alias=True, mode="json")
                for row in repository.list()
                if (not wanted or str(row.get("deviceId")) in wanted)
                and row.get("workspaceId") == runtime_workspace
                and not row.get("deleted")
            ]
        if operations is not None and callable(getattr(operations, "page", None)):
            try:
                rows = operations.page(None, None, 200, workspace_identity=workspace)
            except TypeError:
                rows = operations.page(None, None, 200)
            payload["operations"] = [_operation_response(row).model_dump(by_alias=True, mode="json") for row in rows]
        return diagnostic_snapshot(payload)

    if backups is not None and operations is not None:
        backups.operations = operations
        backups.workspace_identity = workspace_identity()

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
        profile_id: str | None = Query(default=None, alias="profileId"),
        retained: bool | None = Query(default=None),
        cursor: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> ManagementDevicePageRead:
        if devices is None:
            return ManagementDevicePageRead(items=[], next_cursor=None, total=0)
        workspace = getattr(getattr(devices, "runtime", None), "workspace_id", None) or workspace_identity()
        rows = [
            item
            for item in devices.repository.list()
            if not item.get("deleted") and item.get("workspaceId") in {None, workspace}
        ]
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
        observation_service = observations is not None and hasattr(observations, "get")
        return ManagementDevicePageRead(
            items=[_management_device(item, observations.get(str(item["deviceId"])) if observation_service else None, observation_service=observation_service) for item in page],
            next_cursor=str(page[-1]["deviceId"]) if len(rows) > limit else None,
            total=total,
        )

    @router.post("/environment/checks", response_model=OperationRead, status_code=202)
    async def environment_check(body: EnvironmentCheckCommand) -> OperationRead:
        if operations is None:
            raise RuntimeError("Android operation repository is not configured")
        record = operations.accept(workspace_identity(), body.request_id, "environment", "check", "environment-check-v1", {})
        if record.state == "queued":
            record = operations.transition(record.operation_id, "queued", "running", {"stage_code": "checking"})
            try:
                await check_service.check(body.request_id)
            except asyncio.CancelledError:
                operations.transition(record.operation_id, "running", "needs_verification", {"stage_code": "verify", "result_code": "CHECK_RESULT_UNKNOWN", "message": "请求已取消，环境检查结果未知"})
                raise
            except Exception as error:  # noqa: BLE001 - a lost diagnostic result must become needs_verification
                record = operations.transition(record.operation_id, "running", "needs_verification", {"result_code": "CHECK_RESULT_UNKNOWN", "message": str(error)[:480]})
            else:
                record = operations.transition(record.operation_id, "running", "succeeded", {"stage_code": "checked"})
        return _operation_response(record)

    @router.get("/operations", response_model=OperationPageRead)
    async def operation_page(device_id: str | None = Query(default=None, alias="deviceId"), cursor: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=200)) -> OperationPageRead:
        if operations is None:
            return OperationPageRead(items=[], next_cursor=None, total=0)
        workspace = workspace_identity()
        items = operations.page(device_id, cursor, limit + 1, workspace_identity=workspace)
        total = operations.count(device_id, workspace_identity=workspace) if hasattr(operations, "count") else len(items)
        return OperationPageRead(items=[_operation_response(item) for item in items[:limit]], next_cursor=items[limit - 1].operation_id if len(items) > limit else None, total=total)

    @router.get("/operations/by-request/{request_id}", response_model=OperationRead)
    async def operation_by_request(request_id: str) -> OperationRead:
        if operations is None:
            raise RuntimeError("Android operation repository is not configured")
        return _operation_response(operations.by_request(workspace_identity(), request_id))

    @router.get("/operations/{operation_id}", response_model=OperationRead)
    async def operation(operation_id: str) -> OperationRead:
        if operations is None:
            raise RuntimeError("Android operation repository is not configured")
        return _operation_response(operations.get(operation_id, workspace_identity()))

    @router.post("/operations/{operation_id}/verify", response_model=OperationRead)
    async def verify(operation_id: str, body: OperationVerifyCommand) -> OperationRead:
        if operations is None:
            raise RuntimeError("Android operation repository is not configured")
        record = operations.get(operation_id, workspace_identity())
        if body.request_id != record.request_id:
            raise AndroidError("ANDROID_REQUEST_CONFLICT", "核实请求编号与原操作不一致", 409)
        if record.state != "needs_verification":
            return _operation_response(record)

        def verified(changes: dict[str, Any], device: dict[str, Any] | None = None) -> Any:
            # Lifecycle verification must commit the durable operation and the
            # device projection together.  The fallback keeps lightweight test
            # repositories compatible while production uses the SQL transaction.
            transition_with_device = getattr(operations, "transition_with_device", None)
            if device is not None and callable(transition_with_device):
                return transition_with_device(record.operation_id, "needs_verification", "succeeded", changes, device)
            result = operations.transition(record.operation_id, "needs_verification", "succeeded", changes)
            if device is not None and devices is not None and hasattr(devices, "repository"):
                devices.repository.save(device)
            return result

        payload = record.payload or {}
        workspace = workspace_identity()
        if record.action == "pull":
            if images is None or not hasattr(images, "list"):
                raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "尚未接入镜像目录核实", 503)
            observed = next(
                (
                    item
                    for item in images.list()
                    if item.get("requestId") == record.request_id
                    and item.get("reference") == payload.get("reference")
                    and item.get("workspaceId") in {None, workspace}
                ),
                None,
            )
            if observed is None:
                raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "镜像拉取结果仍无法核实", 503)
            record = verified({"stage_code": "verified", "result_code": "IMAGE_PULL_VERIFIED"})
        elif record.action == "backup":
            if backups is None or not hasattr(backups, "resources"):
                raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "尚未接入备份目录核实", 503)
            backup_workspace = getattr(backups, "workspace_identity", workspace)
            observed = next(
                (
                    item
                    for item in backups.resources.list("backup")
                    if item.get("requestId") == record.request_id
                    and (not payload.get("deviceId") or item.get("deviceId") == payload.get("deviceId"))
                    and item.get("workspaceId") in {workspace, backup_workspace}
                ),
                None,
            )
            if observed is None:
                raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "备份结果仍无法核实", 503)
            record = verified({"stage_code": "verified", "result_code": "BACKUP_VERIFIED"})
        elif record.action == "restore":
            if devices is None or not hasattr(devices, "repository"):
                raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "尚未接入恢复目标核实", 503)
            observed = next(
                (
                    item
                    for item in devices.repository.list()
                    if item.get("deviceId") == record.target_id
                    and item.get("restoreRequestId") == record.request_id
                    and (not payload.get("backupId") or item.get("restoreBackupId") == payload.get("backupId"))
                    and item.get("workspaceId") in {workspace, getattr(getattr(devices, "runtime", None), "workspace_id", None)}
                    and item.get("restoreState") == "restored"
                    and not item.get("deleted")
                ),
                None,
            )
            if observed is None:
                raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "恢复结果仍无法核实", 503)
            record = verified({"stage_code": "verified", "result_code": "RESTORE_VERIFIED"})
        elif record.action == "cleanup":
            if cleanup is None or not hasattr(cleanup, "resources") or not hasattr(cleanup.resources, "list"):
                raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "尚未接入清理记录核实", 503)
            observed = next(
                (
                    item
                    for item in cleanup.resources.list("cleanup-operation")
                    if item.get("requestId") == record.request_id and item.get("workspaceId") == workspace
                    and (not payload.get("previewId") or item.get("previewId") == payload.get("previewId"))
                ),
                None,
            )
            if observed is None or observed.get("state") != "succeeded":
                raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "清理结果仍无法核实", 503)
            record = verified({"stage_code": "verified", "result_code": "CLEANUP_VERIFIED"})
        elif record.action == "check" and record.target_id == "environment":
            try:
                await check_service.check(record.request_id)
            except Exception as error:
                raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "环境检查结果仍无法核实", 503) from error
            record = verified({"stage_code": "verified", "result_code": "ENVIRONMENT_CHECKED"})
        elif devices is None:
            raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "尚未接入运行时核实，操作保持待核实", 503)
        else:
            record = await verify_lifecycle_operation(
                operations,
                devices,
                record,
                workspace_identity=workspace,
            )
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
        return ImageRead.model_validate(await images.register(body.model_dump(by_alias=True, mode="json")))

    @router.post("/image-pulls", response_model=OperationRead, status_code=202)
    async def image_pull(body: ImagePullCreate) -> OperationRead:
        if images is None or not hasattr(images, "pull"):
            raise AndroidError("ANDROID_IMAGE_PULL_UNAVAILABLE", "镜像拉取适配器尚未配置", 503)
        if operations is None:
            raise AndroidError("ANDROID_OPERATION_UNAVAILABLE", "操作记录服务尚未配置", 503)
        workspace = workspace_identity()
        digest = hashlib.sha256(json.dumps({"reference": body.reference}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        target_id = str(uuid5(NAMESPACE_URL, f"{workspace}/android-image-pull/{body.request_id}"))
        record = operations.accept(workspace, body.request_id, target_id, "pull", digest, {"reference": body.reference})
        if record.state != "queued":
            return _operation_response(record)
        record = operations.transition(record.operation_id, "queued", "running", {"stage_code": "pulling"})
        try:
            result = await images.pull(body.request_id, body.reference)
        except asyncio.CancelledError:
            operations.transition(record.operation_id, "running", "needs_verification", {"stage_code": "verify", "result_code": "IMAGE_PULL_CANCELLED", "message": "请求已取消，拉取结果未知"})
            raise
        except (TimeoutError, OSError) as error:
            record = operations.transition(record.operation_id, "running", "needs_verification", {"stage_code": "verify", "result_code": "IMAGE_PULL_RESULT_UNKNOWN", "message": str(error)[:480]})
        except Exception as error:
            operations.transition(record.operation_id, "running", "failed", {"stage_code": "failed", "result_code": getattr(error, "code", "ANDROID_IMAGE_PULL_FAILED"), "message": str(error)[:480]})
            raise
        else:
            record = operations.transition(record.operation_id, "running", "succeeded", {"stage_code": "completed", "result_code": "IMAGE_PULL_SUCCEEDED", "message": str(result.get("imageId", ""))[:480]})
        return _operation_response(record)

    @router.delete("/images/{identifier}", response_model=ImageRead)
    async def delete_image(identifier: str, body: ImageDelete) -> ImageRead:
        if images is None:
            raise RuntimeError("Android image service is not configured")
        if body.delete_content and hasattr(images, "delete_content"):
            return ImageRead.model_validate(await images.delete_content(identifier, body.request_id, body.expected_revision))
        return ImageRead.model_validate(images.delete(identifier, body.delete_content, body.request_id, body.expected_revision))

    @router.post("/images/{identifier}/verifications", response_model=ImageRead, status_code=201)
    async def verify_image(identifier: str, body: ImageVerificationCreate) -> ImageRead:
        if images is None:
            raise RuntimeError("Android image service is not configured")
        payload = body.model_dump(by_alias=True)
        verifier = getattr(images, "verify_server", None)
        if not callable(verifier):
            raise AndroidError("ANDROID_IMAGE_VERIFICATION_UNAVAILABLE", "尚未接入镜像服务端核实适配器", 503)
        result = verifier(identifier, payload)
        if inspect.isawaitable(result):
            result = await result
        return ImageRead.model_validate(result)

    @router.post("/images/{identifier}/delete-verifications", response_model=ImageRead)
    async def verify_image_delete(identifier: str, body: ImageDeleteVerification) -> ImageRead:
        if images is None or not hasattr(images, "verify_delete_content"):
            raise AndroidError("ANDROID_IMAGE_VERIFICATION_UNAVAILABLE", "尚未接入镜像删除核实服务", 503)
        return ImageRead.model_validate(await images.verify_delete_content(identifier, body.request_id))

    @router.get("/profiles/{identifier}", response_model=EnvironmentProfile)
    async def profile(identifier: str) -> EnvironmentProfile:
        if profiles is None:
            raise RuntimeError("Android profile service is not configured")
        return _profile_response(profiles.get("profile", identifier))

    @router.post("/profiles/{identifier}/archive", response_model=EnvironmentProfile)
    async def archive_profile(identifier: str, body: ProfileArchiveCommand) -> EnvironmentProfile:
        if profiles is None:
            raise RuntimeError("Android profile service is not configured")
        item = profiles.get("profile", identifier)
        if item.get("archiveRequestId") == body.request_id:
            return _profile_response(item)
        if item.get("revision") != body.expected_revision:
            raise AndroidError("ANDROID_PROFILE_CONFLICT", "设备模板已更新，请重新加载", 409)
        item["archived"] = True
        item["revision"] = int(item.get("revision", 0)) + 1
        item["archiveRequestId"] = body.request_id
        profiles.save("profile", item)
        return _profile_response(item)

    @router.get("/backups", response_model=list[BackupRead])
    async def backup_page() -> list[BackupRead]:
        if backups is None:
            return []
        workspace = workspace_identity()
        return [
            _backup_response(item)
            for item in backups.resources.list("backup")
            if item.get("workspaceId") == workspace
        ]

    @router.post("/backups", response_model=BackupRead, status_code=201)
    async def create_backup(body: BackupCreate) -> BackupRead:
        if backups is None or devices is None or body.device_id is None or body.expected_revision is None:
            raise AndroidError("ANDROID_BACKUP_REQUEST_INVALID", "备份请求缺少设备和版本", 422)
        device = devices.get(body.device_id)
        if int(device.get("generation", 1) or 1) != body.expected_revision:
            raise AndroidError("ANDROID_REVISION_CONFLICT", "设备已发生变化，请重新加载", 409)
        return _backup_response(await backups.create_with_runtime(device, None, devices.runtime, body.request_id, body.expected_revision))

    @router.post("/devices/{identifier}/backups", response_model=BackupRead, status_code=201)
    async def backup(identifier: str, body: BackupCreate) -> BackupRead:
        if backups is None or devices is None:
            raise RuntimeError("Android backup service is not configured")
        device = devices.get(identifier)
        if body.device_id is not None and body.device_id != identifier:
            raise AndroidError("ANDROID_BACKUP_REQUEST_INVALID", "路径设备与请求设备不一致", 422)
        if body.expected_revision is None:
            raise AndroidError("ANDROID_BACKUP_REQUEST_INVALID", "备份请求缺少设备版本", 422)
        if int(device.get("generation", 1) or 1) != body.expected_revision:
            raise AndroidError("ANDROID_REVISION_CONFLICT", "设备已发生变化，请重新加载", 409)
        return _backup_response(await backups.create_with_runtime(device, None, devices.runtime, body.request_id, body.expected_revision))

    @router.post("/backups/{identifier}/restore", response_model=BackupRestoreRead, status_code=202)
    async def restore_backup(identifier: str, body: BackupRestore) -> BackupRestoreRead:
        if backups is None or devices is None:
            raise AndroidError("ANDROID_BACKUP_RESTORE_UNAVAILABLE", "备份恢复服务尚未配置", 503)
        workspace = workspace_identity()
        record = next((item for item in backups.resources.list("backup") if item.get("id") == identifier and item.get("workspaceId") == workspace), None)
        if record is None:
            raise AndroidError("ANDROID_BACKUP_NOT_FOUND", "备份不存在或不可恢复", 404)
        new_device_id = str(uuid5(NAMESPACE_URL, f"{workspace}/android-restore/{body.request_id}"))
        payload = {"backupId": identifier, "newName": body.new_name, "newDeviceId": new_device_id}
        operation = None
        if operations is not None:
            digest = hashlib.sha256(json.dumps({"action": "restore", **payload}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            operation = operations.accept(workspace, body.request_id, new_device_id, "restore", digest, payload)
            if operation.state == "succeeded":
                existing = next((item for item in devices.repository.list() if item.get("deviceId") == new_device_id and item.get("restoreRequestId") == body.request_id and item.get("restoreBackupId") == identifier and item.get("restoreState") == "restored" and not item.get("deleted")), None)
                if existing is None:
                    raise AndroidError("ANDROID_RESTORE_RESULT_UNKNOWN", "恢复结果已记录但设备不可见，请核实后再试", 503)
                return BackupRestoreRead(operation_id=operation.operation_id, request_id=body.request_id, target_id=existing["deviceId"], device_id=existing["deviceId"], backup_id=identifier, state="restored")
            if operation.state in {"running", "needs_verification", "failed", "cancelled"}:
                raise AndroidError("ANDROID_RESTORE_REQUEST_REPLAYED", "恢复请求已处理，请先核实操作结果", 409)
            operation = operations.transition(operation.operation_id, "queued", "running", {"stage_code": "creating"})
        config = dict(record.get("config") or {})
        if any(key not in config for key in ("width", "height", "dpi", "cpu", "memoryMb")):
            if operation is not None:
                operations.transition(operation.operation_id, "running", "failed", {"stage_code": "failed", "result_code": "ANDROID_BACKUP_INCOMPATIBLE", "message": "备份缺少可恢复的实例配置快照"})
            raise AndroidError("ANDROID_BACKUP_INCOMPATIBLE", "备份缺少可恢复的实例配置快照", 409)
        try:
            environment = await devices.environment()
        except asyncio.CancelledError:
            if operation is not None:
                operations.transition(operation.operation_id, "running", "needs_verification", {"stage_code": "verify", "result_code": "RESTORE_RESULT_UNKNOWN", "message": "请求已取消，恢复结果未知"})
            raise
        except (TimeoutError, OSError) as error:
            if operation is not None:
                operations.transition(operation.operation_id, "running", "needs_verification", {"stage_code": "verify", "result_code": "RESTORE_RESULT_UNKNOWN", "message": str(error)[:480]})
            raise AndroidError("ANDROID_BACKUP_RESTORE_RESULT_UNKNOWN", "恢复结果未知，请核实新实例", 503) from error
        if not any(image.get("id") == record.get("imageId") for image in environment.get("images", [])):
            if operation is not None:
                operations.transition(operation.operation_id, "running", "failed", {"stage_code": "failed", "result_code": "ANDROID_BACKUP_IMAGE_MISSING", "message": "备份所需的精确镜像当前不可用"})
            raise AndroidError("ANDROID_BACKUP_IMAGE_MISSING", "备份所需的精确镜像当前不可用", 409)
        config.update(deviceId=new_device_id, name=body.new_name, imageId=record["imageId"], instanceType="persistent", start=False, restoreRequestId=body.request_id, restoreBackupId=identifier, restoreOperationId=operation.operation_id if operation else None)
        try:
            created = devices.management.create(config)
            task = devices.management.task
            if task is not None:
                await asyncio.shield(task)
            created = devices.repository.get(new_device_id)
            if created.get("deleted") or created.get("control") == "recovery_required" or created.get("androidStatus") in {"ready", "running"} or created.get("operation", {}).get("state") in {"failed", "needs_verification", "interrupted"}:
                raise AndroidError("ANDROID_BACKUP_RESTORE_CREATE_FAILED", "恢复目标实例创建未完成，未写入数据卷", 503)
            await backups.restore_data(identifier, created, devices.runtime)
            created.update(dataRetained=False, restoreState="restored", control="idle", lastError=None)
            if operation is not None:
                operation = operations.transition_with_device(operation.operation_id, "running", "succeeded", {"stage_code": "completed", "result_code": "BACKUP_RESTORED"}, created)
            else:
                devices.repository.save(created)
        except BaseException as error:
            # Read durable state: the local completion projection may never have committed.
            # A lost commit acknowledgement must not downgrade a published restoration.
            unknown = isinstance(error, (asyncio.CancelledError, TimeoutError, OSError))
            try:
                latest = operations.get(operation.operation_id) if operation is not None else None
                target = next((item for item in devices.repository.list() if item.get("deviceId") == new_device_id), None)
                committed = (
                    target is not None and not target.get("deleted")
                    and target.get("restoreState") == "restored"
                    and target.get("restoreRequestId") == body.request_id
                    and target.get("restoreBackupId") == identifier
                    and (latest is None or latest.state == "succeeded")
                )
                if committed and not isinstance(error, asyncio.CancelledError):
                    return BackupRestoreRead(operation_id=latest.operation_id if latest else None, request_id=body.request_id, target_id=new_device_id, device_id=new_device_id, backup_id=identifier, state="restored")
                if not committed and latest is not None and latest.state == "running":
                    state = "needs_verification" if unknown else "failed"
                    changes = {"stage_code": "verify" if unknown else "failed", "result_code": "RESTORE_RESULT_UNKNOWN" if unknown else getattr(error, "code", "ANDROID_BACKUP_RESTORE_FAILED"), "message": str(error)[:480]}
                    if target is not None and restore_pending(target) and target.get("control") != "managing":
                        target.update(control="recovery_required", lastError="恢复数据卷未完成，请核实新实例")
                        operations.transition_with_device(latest.operation_id, "running", state, changes, target)
                    else:
                        operations.transition(latest.operation_id, "running", state, changes)
            except Exception as persistence_error:
                # Pending intent was persisted before any IO; unavailable storage cannot release it.
                if isinstance(error, asyncio.CancelledError):
                    raise error from persistence_error
                raise AndroidError("ANDROID_BACKUP_RESTORE_RESULT_UNKNOWN", "恢复结果无法持久核实，请核实新实例", 503) from persistence_error
            if isinstance(error, asyncio.CancelledError):
                raise
            if unknown:
                raise AndroidError("ANDROID_BACKUP_RESTORE_RESULT_UNKNOWN", "恢复结果未知，请核实新实例", 503) from error
            raise
        return BackupRestoreRead(operation_id=operation.operation_id if operation is not None else None, request_id=body.request_id, target_id=new_device_id, device_id=new_device_id, backup_id=identifier, state="restored")

    @router.post("/bulk-operations", response_model=BulkRead, status_code=202)
    async def bulk_create(body: BulkCreate) -> BulkRead:
        if bulk is None:
            raise RuntimeError("Android bulk service is not configured")
        result = bulk.create(workspace_identity(), body.request_id, body.action, [item.model_dump(by_alias=True) for item in body.items], body.delete_data)
        return BulkRead.model_validate(bulk.run(result["id"], workspace_identity()))

    @router.get("/bulk-operations/{identifier}", response_model=BulkRead)
    async def bulk_get(identifier: str) -> BulkRead:
        if bulk is None:
            raise RuntimeError("Android bulk service is not configured")
        return BulkRead.model_validate(bulk.get(identifier, workspace_identity()))

    @router.post("/bulk-operations/{identifier}/actions", response_model=BulkRead)
    async def bulk_action(identifier: str, body: BulkAction) -> BulkRead:
        if bulk is None:
            raise RuntimeError("Android bulk service is not configured")
        if body.action == "verify":
            return BulkRead.model_validate(await bulk.verify(identifier, workspace_identity()))
        return BulkRead.model_validate(bulk.action(identifier, body.action, body.request_id, workspace_identity()))

    @router.get("/cleanup/resources", response_model=CleanupResourcePage)
    async def cleanup_resources() -> CleanupResourcePage:
        if cleanup is None:
            raise AndroidError("ANDROID_CLEANUP_UNAVAILABLE", "数据清理服务尚未配置", 503)
        return CleanupResourcePage(items=cleanup.inventory(workspace_identity()))

    @router.post("/cleanup/previews", response_model=CleanupPreviewRead)
    async def cleanup_preview(body: CleanupPreviewCreate) -> CleanupPreviewRead:
        if cleanup is None:
            raise RuntimeError("Android cleanup service is not configured")
        items = cleanup.preview(body.resource_ids, workspace_identity())
        import hashlib
        import json
        digest = hashlib.sha256(json.dumps(items, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        preview_id = cleanup.preview_id_for(workspace_identity(), digest) or digest
        return CleanupPreviewRead(items=items, confirmation_digest=digest, preview_id=preview_id)

    @router.post("/cleanup", response_model=CleanupRead)
    async def cleanup_execute(body: CleanupExecute) -> CleanupRead:
        if cleanup is None:
            raise RuntimeError("Android cleanup service is not configured")
        items = cleanup.execute(workspace_identity(), body.confirmation_digest, body.request_id, body.preview_id)
        operation = cleanup.last_operation or {}
        response_preview_id = operation.get("previewId") or body.preview_id or cleanup.preview_id_for(workspace_identity(), body.confirmation_digest)
        return CleanupRead(items=items, state=operation.get("state", "accepted") if cleanup.operations is not None else "accepted", operation_id=operation.get("operationId"), request_id=body.request_id, preview_id=response_preview_id)

    @router.post("/diagnostics", response_model=DiagnosticRead, status_code=202)
    async def diagnostics(body: DiagnosticsCreate) -> DiagnosticRead:
        if resources is None:
            raise RuntimeError("Android diagnostics store is not configured")
        workspace = workspace_identity()
        request_payload = body.model_dump(by_alias=True, mode="json")
        request_digest = hashlib.sha256(
            json.dumps(request_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        existing = next(
            (
                item
                for item in resources.list("diagnostic")
                if item.get("workspaceId") == workspace and item.get("requestId") == body.request_id
            ),
            None,
        )
        if existing is not None:
            if existing.get("requestDigest") != request_digest:
                raise AndroidError("ANDROID_REQUEST_CONFLICT", "请求编号已用于不同诊断导出", 409)
            return _diagnostic_response(existing)
        created_at = datetime.now(UTC)
        record = {
            "id": body.request_id,
            "requestId": body.request_id,
            "workspaceId": workspace,
            "requestDigest": request_digest,
            "state": "ready",
            "payload": await diagnostic_payload(body, workspace),
            "createdAt": created_at.isoformat(),
            "expiresAt": (created_at + timedelta(minutes=5)).isoformat(),
        }
        resources.save("diagnostic", record)
        return _diagnostic_response(record)

    return router
