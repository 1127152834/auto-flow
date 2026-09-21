from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Header, Query, Request, status
from pydantic import ConfigDict, Field

from autoflow.adapters.http.schemas import ApiModel
from autoflow.application.workflows.schedules import WorkflowScheduleService


class ScheduledTaskWrite(ApiModel):
    model_config = ConfigDict(extra="allow")

    name: str
    workflow_id: str
    trigger: dict[str, Any]
    enabled: bool = True


class ScheduledTaskUpdate(ApiModel):
    model_config = ConfigDict(extra="allow")


class ScheduledTaskToggle(ApiModel):
    enabled: bool


class ScheduledTaskExecute(ApiModel):
    command_id: str = Field(alias="commandId", min_length=1, max_length=128)


def workflow_schedules_router(service: WorkflowScheduleService) -> APIRouter:
    router = APIRouter(prefix="/api/scheduled-tasks", tags=["studio-scheduled-tasks"])

    @router.get("/list")
    def list_tasks() -> list[dict[str, Any]]:
        return service.list()

    @router.get("/logs/all")
    def all_logs(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict[str, Any]]:
        return service.logs(None, limit)

    @router.delete("/logs/all")
    def clear_all_logs() -> dict[str, bool]:
        service.clear_logs(None)
        return {"success": True}

    @router.get("/statistics/summary")
    def statistics() -> dict[str, Any]:
        return service.statistics()

    @router.get("/commands/{command_id}")
    def command(command_id: str) -> dict[str, Any]:
        return service.command(command_id)

    @router.get("/hotkeys/registrations")
    def hotkey_registrations() -> list[dict[str, str]]:
        return service.hotkeys()

    @router.post("/hotkeys/{task_id}/trigger", status_code=status.HTTP_202_ACCEPTED)
    async def trigger_hotkey(
        task_id: str,
        key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        return await service.trigger_hotkey(task_id, command_id=key or uuid4().hex)

    async def trigger_webhook(
        path: str,
        request: Request,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        del request  # The workflow reads its own configured inputs; request data is not persisted.
        return await service.trigger_webhook(path, command_id=idempotency_key or uuid4().hex)

    @router.get("/webhook/{path:path}", status_code=status.HTTP_202_ACCEPTED)
    async def webhook_get(
        path: str,
        request: Request,
        key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        return await trigger_webhook(path, request, key)

    @router.post("/webhook/{path:path}", status_code=status.HTTP_202_ACCEPTED)
    async def webhook_post(
        path: str,
        request: Request,
        key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        return await trigger_webhook(path, request, key)

    @router.put("/webhook/{path:path}", status_code=status.HTTP_202_ACCEPTED)
    async def webhook_put(
        path: str,
        request: Request,
        key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        return await trigger_webhook(path, request, key)

    @router.patch("/webhook/{path:path}", status_code=status.HTTP_202_ACCEPTED)
    async def webhook_patch(
        path: str,
        request: Request,
        key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        return await trigger_webhook(path, request, key)

    @router.delete("/webhook/{path:path}", status_code=status.HTTP_202_ACCEPTED)
    async def webhook_delete(
        path: str,
        request: Request,
        key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        return await trigger_webhook(path, request, key)

    @router.get("/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        return service.get(task_id)

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_task(request: ScheduledTaskWrite) -> dict[str, Any]:
        return service.create(request.model_dump(exclude_none=True))

    @router.put("/{task_id}")
    def update_task(task_id: str, request: ScheduledTaskUpdate) -> dict[str, Any]:
        return service.update(task_id, request.model_dump(exclude_none=True))

    @router.post("/{task_id}/toggle")
    def toggle_task(task_id: str, request: ScheduledTaskToggle) -> dict[str, Any]:
        return service.toggle(task_id, request.enabled)

    @router.post("/{task_id}/execute", status_code=status.HTTP_202_ACCEPTED)
    async def execute_task(task_id: str, request: ScheduledTaskExecute) -> dict[str, Any]:
        return await service.execute(task_id, command_id=request.command_id)

    @router.post("/{task_id}/stop", status_code=status.HTTP_202_ACCEPTED)
    async def stop_task(task_id: str) -> dict[str, Any]:
        return await service.stop(task_id)

    @router.get("/{task_id}/logs")
    def task_logs(task_id: str, limit: int = Query(default=100, ge=1, le=1000)) -> list[dict[str, Any]]:
        service.get(task_id)
        return service.logs(task_id, limit)

    @router.delete("/{task_id}/logs")
    def clear_task_logs(task_id: str) -> dict[str, bool]:
        service.get(task_id)
        service.clear_logs(task_id)
        return {"success": True}

    @router.delete("/{task_id}")
    def delete_task(task_id: str) -> dict[str, bool]:
        service.delete(task_id)
        return {"success": True}

    return router
