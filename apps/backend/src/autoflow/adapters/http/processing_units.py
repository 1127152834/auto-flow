"""Processing unit routes (remediation M2 R2-06)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, Query

from autoflow.application.project_runs.processing_units import ProcessingUnitService

from .errors import browser_error_responses
from .processing_unit_schemas import (
    ProcessingUnitChange,
    ProcessingUnitCommandResult,
    ProcessingUnitPage,
    ProcessingUnitResolve,
    UnitState,
)

Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def processing_units_router(service: ProcessingUnitService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}/automations/{automationId}/processing-units")

    @router.get("", response_model=ProcessingUnitPage, responses=browser_error_responses(401, 404, 422))
    def list_units(
        projectId: UUID,
        automationId: UUID,
        state: UnitState | None = None,
        after: str | None = None,
        limit: int = Query(50, ge=1, le=200),
    ) -> dict[str, Any]:
        return service.list(str(projectId), str(automationId), state=state, after=after, limit=limit)

    def run(project_id: UUID, automation_id: UUID, unit_id: UUID, key: UUID, action: str, body: Any) -> dict[str, Any]:
        operation, unit = service.command(
            str(project_id), str(automation_id), str(unit_id), str(key), action,
            body.model_dump(by_alias=True),
        )
        return {"operation": operation, "unit": unit}

    responses = browser_error_responses(401, 404, 409, 422)

    @router.post("/{unitId}/reset", response_model=ProcessingUnitCommandResult, responses=responses)
    def reset(projectId: UUID, automationId: UUID, unitId: UUID, body: ProcessingUnitChange, idempotency_key: Key) -> dict[str, Any]:
        return run(projectId, automationId, unitId, idempotency_key, "reset", body)

    @router.post("/{unitId}/skip", response_model=ProcessingUnitCommandResult, responses=responses)
    def skip(projectId: UUID, automationId: UUID, unitId: UUID, body: ProcessingUnitChange, idempotency_key: Key) -> dict[str, Any]:
        return run(projectId, automationId, unitId, idempotency_key, "skip", body)

    @router.post("/{unitId}/resolve", response_model=ProcessingUnitCommandResult, responses=responses)
    def resolve(projectId: UUID, automationId: UUID, unitId: UUID, body: ProcessingUnitResolve, idempotency_key: Key) -> dict[str, Any]:
        return run(projectId, automationId, unitId, idempotency_key, "resolve", body)

    return router
