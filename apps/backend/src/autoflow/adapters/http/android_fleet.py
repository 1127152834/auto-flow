from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile

from autoflow.application.android.console import AndroidConsole
from autoflow.application.android.fleet import AndroidFleet
from autoflow.domain.android.ports import AndroidError

from .android_fleet_schemas import (
    AllocationCreate,
    AllocationRead,
    AppInfo,
    AppLaunch,
    BatchAction,
    BatchCreate,
    BatchRead,
    ControlCommand,
    DeviceRunRead,
    EnvironmentProfile,
    SessionAction,
    SessionCreate,
    SessionRead,
)


def project(model: Any, data: dict[str, Any]) -> Any:
    return model.model_validate(
        {
            field.alias: data[field.alias]
            for field in model.model_fields.values()
            if field.alias in data
        }
    )


def android_fleet_router(fleet: AndroidFleet, console: AndroidConsole) -> APIRouter:
    router = APIRouter(prefix="/api/v1/android", tags=["android-fleet"])

    @router.get("/profiles", response_model=list[EnvironmentProfile])
    async def profiles() -> Any:
        async with fleet.tick_lock:
            return await fleet.profiles()

    @router.put("/profiles/{identifier}", response_model=EnvironmentProfile)
    async def save_profile(identifier: UUID, body: EnvironmentProfile) -> Any:
        if identifier != body.id:
            raise AndroidError("ANDROID_PROFILE_ID", "环境编号不一致", 422)
        async with fleet.tick_lock:
            return fleet.save_profile(body.model_dump(by_alias=True, mode="json"))

    @router.get("/batches", response_model=list[BatchRead])
    async def batches() -> Any:
        return [project(BatchRead, item) for item in fleet.resources.list("batch")]

    @router.post("/batches", response_model=BatchRead, status_code=202)
    async def batch(body: BatchCreate) -> Any:
        async with fleet.tick_lock:
            return project(
                BatchRead, fleet.batch(body.model_dump(by_alias=True, mode="json"))
            )

    @router.post("/batches/{identifier}/actions", response_model=BatchRead)
    async def batch_action(identifier: UUID, body: BatchAction) -> Any:
        async with fleet.tick_lock:
            return project(BatchRead, fleet.batch_action(str(identifier), body.action))

    @router.get("/allocations", response_model=list[AllocationRead])
    async def allocations() -> Any:
        return [
            project(AllocationRead, item) for item in fleet.resources.list("allocation")
        ]

    @router.post("/allocations", response_model=AllocationRead, status_code=202)
    async def allocate(body: AllocationCreate) -> Any:
        async with fleet.tick_lock:
            return project(
                AllocationRead,
                fleet.allocate(body.model_dump(by_alias=True, mode="json")),
            )

    @router.delete("/allocations/{identifier}", response_model=AllocationRead)
    async def cancel_allocation(identifier: UUID) -> Any:
        async with fleet.tick_lock:
            return project(AllocationRead, fleet.cancel_allocation(str(identifier)))

    @router.get("/devices/{identifier}/runs", response_model=list[DeviceRunRead])
    async def history(
        identifier: UUID,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
    ) -> Any:
        # Read durable run records, including runs started from the workflow studio.
        records = fleet.runs.list(None, offset, limit, str(identifier))["items"]
        result = []
        for item in records:
            if item.get("target", {}).get("deviceId") != str(identifier):
                continue
            run = fleet.runs.get(item["runId"])
            nodes = run["document"]["nodes"]
            completed = set(run.get("completedNodeIds", []))
            current = min(
                len(nodes),
                len(completed)
                + (
                    1
                    if run.get("currentNodeId") not in completed
                    and run.get("currentNodeId")
                    else 0
                ),
            )
            result.append(
                {
                    "runId": run["runId"],
                    "workflowName": run["name"],
                    "state": run["state"],
                    "currentNodeId": run.get("currentNodeId"),
                    "currentStep": current,
                    "totalSteps": len(nodes),
                    "steps": [
                        {
                            "id": node["id"],
                            "label": node.get("label") or node["type"],
                            "status": "completed"
                            if node["id"] in completed
                            else ("failed" if run["state"] == "failed" else "running")
                            if node["id"] == run.get("currentNodeId")
                            else "pending",
                        }
                        for node in nodes
                    ],
                    "handoff": run.get("handoff"),
                    "startedAt": run["startedAt"],
                }
            )
        return result

    @router.post("/sessions", response_model=SessionRead)
    async def session(body: SessionCreate) -> Any:
        return await console.create(body.model_dump(by_alias=True, mode="json"))

    @router.get("/sessions/{identifier}", response_model=SessionRead)
    async def read_session(identifier: UUID) -> Any:
        return console.get(str(identifier))["view"]

    @router.post("/sessions/{identifier}/actions", response_model=SessionRead)
    async def action(identifier: UUID, body: SessionAction) -> Any:
        return await console.action(
            str(identifier), body.model_dump(by_alias=True, mode="json")
        )

    @router.post("/sessions/{identifier}/input", response_model=SessionRead)
    async def command(identifier: UUID, body: ControlCommand) -> Any:
        return await console.command(
            str(identifier), body.model_dump(by_alias=True, mode="json")
        )

    @router.get("/sessions/{identifier}/stream", response_class=StreamingResponse)
    async def stream(identifier: UUID) -> StreamingResponse:
        session = console.get(str(identifier))
        transport = session["stream"]
        if not transport or transport.error:
            raise AndroidError(
                "ANDROID_STREAM_LOST", "设备画面已断开，请重新打开控制台", 503
            )
        return StreamingResponse(
            transport.packets(),
            media_type="application/octet-stream",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @router.get("/sessions/{identifier}/apps", response_model=AppInfo)
    async def apps(identifier: UUID) -> Any:
        return await console.apps(str(identifier))

    @router.post("/sessions/{identifier}/apps/launch", response_model=SessionRead)
    async def launch(identifier: UUID, body: AppLaunch) -> Any:
        return await console.app_operation(
            str(identifier), body.generation, "launch", body.package_name
        )

    @router.post(
        "/sessions/{identifier}/apps/install",
        response_model=SessionRead,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["file"],
                            "properties": {
                                "file": {"type": "string", "format": "binary"}
                            },
                        }
                    },
                    "application/vnd.android.package-archive": {
                        "schema": {"type": "string", "format": "binary"}
                    },
                },
            }
        },
    )
    async def install(identifier: UUID, generation: int, request: Request) -> Any:
        session = console.get(str(identifier))
        console._check(session, generation, True)
        chunks = bytearray()
        if request.headers.get("content-type", "").startswith("multipart/form-data"):
            async with request.form(max_files=1, max_fields=0) as form:
                upload = form.get("file")
                if not isinstance(upload, UploadFile):
                    raise AndroidError("ANDROID_APK_INVALID", "请选择 APK 文件", 422)
                while data := await upload.read(1024 * 1024):
                    if len(chunks) + len(data) > 256 * 1024 * 1024:
                        raise AndroidError(
                            "ANDROID_APK_TOO_LARGE", "APK 不能超过 256 MB", 413
                        )
                    chunks.extend(data)
        else:
            async for data in request.stream():
                if len(chunks) + len(data) > 256 * 1024 * 1024:
                    raise AndroidError(
                        "ANDROID_APK_TOO_LARGE", "APK 不能超过 256 MB", 413
                    )
                chunks.extend(data)
        if not chunks.startswith(b"PK"):
            raise AndroidError("ANDROID_APK_INVALID", "请选择 APK 文件", 422)
        return await console.app_operation(
            str(identifier), generation, "install", bytes(chunks)
        )

    return router
