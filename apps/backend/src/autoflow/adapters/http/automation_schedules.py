"""Automation schedule routes (remediation M2 R2-25/R2-27)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Response
from pydantic import Field, JsonValue, StrictBool, StrictInt, StrictStr

from autoflow.application.project_automations.schedules import AutomationScheduleService

from .errors import browser_error_responses
from .schemas import ApiModel


class ScheduleWrite(ApiModel):
    kind: Literal["cron", "webhook"]
    cron: StrictStr | None = None
    timezone: StrictStr = "Asia/Shanghai"
    overlap: Literal["skip", "queue", "parallel"] = "skip"
    missed: Literal["latestOnly", "ignore"] = "latestOnly"
    enabled: StrictBool
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    max_tasks: StrictInt | None = Field(default=None, ge=1, le=100)
    concurrency: StrictInt = Field(default=1, ge=1, le=100)


class ScheduleUpdate(ScheduleWrite):
    expected_revision: StrictInt = Field(ge=1)


class ScheduleView(ApiModel):
    schedule_id: str
    project_id: str
    automation_id: str
    kind: Literal["cron", "webhook"]
    cron: str | None
    timezone: str
    overlap: Literal["skip", "queue", "parallel"]
    missed: Literal["latestOnly", "ignore"]
    enabled: bool
    parameters: dict[str, JsonValue]
    max_tasks: int | None
    concurrency: int
    last_fire_at: datetime | None
    revision: int
    # Only returned once, when a webhook schedule is created.
    webhook_secret: str | None = None


class ScheduleTriggerView(ApiModel):
    trigger_id: str
    kind: Literal["cron", "webhook"]
    planned_at: str | None
    received_at: datetime
    state: Literal["pending", "started", "skipped", "queued", "failed"]
    batch_id: str | None
    reason: str | None


class WebhookCall(ApiModel):
    event_id: StrictStr = Field(min_length=1, max_length=200)


def automation_schedules_router(service: AutomationScheduleService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}/automations/{automationId}/schedules")
    responses = browser_error_responses(401, 403, 404, 409, 422)

    def payload(body: ScheduleWrite) -> dict[str, Any]:
        value = body.model_dump(by_alias=True, exclude={"expected_revision"})
        value.pop("expectedRevision", None)
        return value

    @router.get("", response_model=list[ScheduleView], responses=responses)
    def list_schedules(projectId: UUID, automationId: UUID) -> list[dict[str, Any]]:
        return service.schedules(str(projectId), str(automationId))

    @router.post("", response_model=ScheduleView, status_code=201, responses=responses)
    def create_schedule(projectId: UUID, automationId: UUID, body: ScheduleWrite) -> dict[str, Any]:
        return service.create(str(projectId), str(automationId), payload(body))

    @router.put("/{scheduleId}", response_model=ScheduleView, responses=responses)
    def update_schedule(projectId: UUID, automationId: UUID, scheduleId: UUID, body: ScheduleUpdate) -> dict[str, Any]:
        return service.update(str(projectId), str(automationId), str(scheduleId), body.expected_revision, payload(body))

    @router.delete("/{scheduleId}", status_code=204, responses=responses)
    def delete_schedule(projectId: UUID, automationId: UUID, scheduleId: UUID) -> Response:
        service.delete(str(projectId), str(automationId), str(scheduleId))
        return Response(status_code=204)

    @router.get("/{scheduleId}/triggers", response_model=list[ScheduleTriggerView], responses=responses)
    def list_triggers(projectId: UUID, automationId: UUID, scheduleId: UUID) -> list[dict[str, Any]]:
        return service.triggers(str(projectId), str(automationId), str(scheduleId))

    @router.post("/{scheduleId}/webhook", response_model=ScheduleTriggerView, status_code=202, responses=responses)
    def call_webhook(
        projectId: UUID,
        automationId: UUID,
        scheduleId: UUID,
        body: WebhookCall,
        secret: Annotated[str | None, Header(alias="X-AutoFlow-Webhook-Secret")] = None,
    ) -> dict[str, Any]:
        return service.webhook(str(projectId), str(automationId), str(scheduleId), secret, body.event_id)

    return router
