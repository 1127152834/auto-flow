import asyncio
import logging
import mimetypes
import shutil
from datetime import datetime
from pathlib import Path, PurePath
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, Response
from pydantic import Field

from autoflow.application.android.ai_tests import AiTestService
from autoflow.domain.android.ai_test import TERMINAL_STATES
from autoflow.domain.android.ports import AndroidError

from .schemas import ApiModel

DeviceKind = Literal["managed", "external"]
logger = logging.getLogger(__name__)


class AiToolStatusRead(ApiModel):
    state: Literal["missing_prerequisite", "not_installed", "installing", "ready", "failed"]
    version: str | None = None
    message: str | None = None


class AiToolInstall(ApiModel):
    request_id: str = Field(min_length=1)


class ExternalDeviceRead(ApiModel):
    serial: str
    state: str
    model: str | None = None
    product: str | None = None


class AiTestRunCreate(ApiModel):
    # Value ranges are validated by the service so failures carry AI_TEST_* codes.
    request_id: str
    device_kind: DeviceKind
    device_id: str | None = None
    serial: str | None = None
    instruction: str
    mode: str
    model_id: str
    max_steps: int
    timeout_seconds: int


class AiTestStepRead(ApiModel):
    index: int | None = None
    summary: str | None = None
    screenshot: str | None = None


class AiTestRunRead(ApiModel):
    id: str
    request_id: str
    device_kind: DeviceKind
    device_id: str | None = None
    serial: str | None = None
    state: Literal["queued", "running", "succeeded", "failed", "cancelled", "needs_verification"]
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    instruction: str
    mode: str
    model_id: str
    model_key: str | None = None
    max_steps: int
    timeout_seconds: int
    tool_version: str | None = None
    steps: list[AiTestStepRead] = Field(default_factory=list)
    succeeded: bool | None = None
    trace_id: str | None = None
    artifacts: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class AiTestRunPageRead(ApiModel):
    items: list[AiTestRunRead]
    next_cursor: str | None = None


class AiTestHelperInstall(ApiModel):
    device_kind: DeviceKind
    device_id: str | None = None
    serial: str | None = None


class AiTestHelperRead(ApiModel):
    installed: bool


def _read(run: dict[str, Any]) -> AiTestRunRead:
    fields = {f.alias: run[f.alias] for f in AiTestRunRead.model_fields.values() if f.alias in run}
    fields["artifacts"] = [PurePath(str(name)).name for name in run.get("artifacts") or []]
    fields["steps"] = [
        {k: step.get(k) for k in ("index", "summary", "screenshot")} for step in run.get("steps") or []
    ]
    return AiTestRunRead.model_validate(fields)


def _artifact_missing() -> AndroidError:
    return AndroidError("AI_TEST_ARTIFACT_NOT_FOUND", "测试产物不存在", 404)


_DELETABLE_STATES = TERMINAL_STATES | {"needs_verification"}


def _remove_dir(path: Path) -> None:
    def log(_func: Any, failed: str, exc_info: Any) -> None:
        logger.warning("AI test artifacts cleanup failed for %s: %s", failed, exc_info[1])

    if path.exists():
        shutil.rmtree(path, onerror=log)  # the record is already deleted; report leftovers instead of hiding them


def _resolve_artifact(artifacts_root: Path, run_id: str, name: str) -> Path:
    root = artifacts_root.resolve()
    run_dir = (root / run_id).resolve()
    if run_dir.parent != root:  # run_id must be a plain directory name directly under the root
        raise _artifact_missing()
    target = (run_dir / name).resolve()
    if not (target.is_relative_to(run_dir) and target.is_file()):
        raise _artifact_missing()
    return target


def android_ai_tests_router(service: AiTestService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/android/ai-tests", tags=["android-ai-tests"])

    @router.get("/tool", response_model=AiToolStatusRead)
    async def tool() -> Any:
        return await service.tool_status()

    @router.post("/tool/install", response_model=AiToolStatusRead)
    async def install_tool(body: AiToolInstall) -> Any:
        return await service.install_tool(body.request_id)

    @router.get("/external-devices", response_model=list[ExternalDeviceRead])
    async def external_devices() -> Any:
        return await service.external_devices()

    @router.post("/helper", response_model=AiTestHelperRead)
    async def install_helper(body: AiTestHelperInstall) -> Any:
        return {"installed": await service.install_helper(body.device_kind, body.device_id, body.serial)}

    @router.post("/runs", response_model=AiTestRunRead, status_code=202)
    async def start(body: AiTestRunCreate) -> Any:
        return _read(await service.start(body.model_dump(by_alias=True)))

    @router.get("/runs", response_model=AiTestRunPageRead)
    async def runs(
        device_kind: Annotated[DeviceKind, Query(alias="deviceKind")],
        device_id: Annotated[str | None, Query(alias="deviceId")] = None,
        serial: str | None = None,
        cursor: str | None = None,
    ) -> Any:
        if not (device_id if device_kind == "managed" else serial):
            raise AndroidError("AI_TEST_DEVICE_INVALID", "请选择要查看的设备", 422)
        try:
            items, next_cursor = await asyncio.to_thread(
                service.repository.list, device_kind, device_id, serial, cursor
            )
        except AndroidError as exc:
            if exc.code == "ANDROID_INVALID_CURSOR":
                raise AndroidError("AI_TEST_CURSOR_INVALID", "分页游标无效", 422) from None
            raise
        return {"items": [_read(item) for item in items], "nextCursor": next_cursor}

    @router.get("/runs/{run_id}", response_model=AiTestRunRead)
    async def get_run(run_id: str) -> Any:
        return _read(await asyncio.to_thread(service.repository.get, run_id))

    @router.post("/runs/{run_id}/cancel", response_model=AiTestRunRead)
    async def cancel(run_id: str) -> Any:
        return _read(await service.cancel(run_id))

    @router.get(
        "/runs/{run_id}/screen", response_class=Response,
        responses={200: {"content": {"image/png": {}}, "description": "当前设备画面（只读）"}},
    )
    async def screen(run_id: str) -> Response:
        return Response(await service.screen(run_id), media_type="image/png", headers={"Cache-Control": "no-store"})

    @router.delete("/runs/{run_id}", status_code=204)
    async def delete_run(run_id: str) -> Response:
        run = await asyncio.to_thread(service.repository.get, run_id)
        if run["state"] not in _DELETABLE_STATES:
            raise AndroidError("AI_TEST_STATE_CONFLICT", "测试仍在进行，无法删除", 409)
        await asyncio.to_thread(service.repository.delete, run_id)
        await asyncio.to_thread(_remove_dir, service.artifacts_root / run["id"])
        return Response(status_code=204)

    @router.get("/runs/{run_id}/artifacts/{name:path}")
    async def artifact(run_id: str, name: str) -> FileResponse:
        await asyncio.to_thread(service.repository.get, run_id)  # only runs with a record are served
        target = await asyncio.to_thread(_resolve_artifact, service.artifacts_root, run_id, name)
        return FileResponse(target, media_type=mimetypes.guess_type(target.name)[0] or "application/octet-stream")

    return router
