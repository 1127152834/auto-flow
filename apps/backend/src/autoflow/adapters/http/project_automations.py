from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response

from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.domain.project_automations.models import automation_to_dict

from .errors import browser_error_responses
from .project_automation_schemas import (
    AutomationCreate,
    AutomationDeleteRequest,
    AutomationPage,
    AutomationUpdate,
    AutomationValidationView,
    AutomationView,
)
from .project_schemas import AutomationImpactView, OperationAccepted

Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def project_automations_router(service: ProjectAutomationService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}/automations")

    @router.get(
        "",
        response_model=AutomationPage,
        response_model_exclude_unset=True,
        responses=browser_error_responses(401, 404, 422),
    )
    def list_automations(
        projectId: UUID,
        q: str | None = None,
        page: int = Query(1, ge=1, le=2_147_483_647),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
        sort: str = "-updatedAt",
    ):
        items, total = service.list(
            str(projectId), q=q, page=page, page_size=page_size, sort=sort
        )
        return {
            "items": [_view(item) for item in items],
            "page": page,
            "pageSize": page_size,
            "total": total,
            "sort": sort,
        }

    @router.post(
        "",
        response_model=AutomationView,
        response_model_exclude_unset=True,
        status_code=201,
        responses={
            200: {"model": AutomationView},
            **browser_error_responses(401, 404, 409, 422, 423),
        },
    )
    def create_automation(
        projectId: UUID, body: AutomationCreate, response: Response, idempotency_key: Key
    ):
        value, _operation, replayed = service.create(
            str(projectId), str(idempotency_key), body.payload()
        )
        if replayed:
            response.status_code = 200
        return _view(value)

    @router.get(
        "/{automationId}",
        response_model=AutomationView,
        response_model_exclude_unset=True,
        responses=browser_error_responses(401, 404, 422),
    )
    def get_automation(projectId: UUID, automationId: UUID):
        return _view(service.get(str(projectId), str(automationId)))

    @router.put(
        "/{automationId}",
        response_model=AutomationView,
        response_model_exclude_unset=True,
        responses=browser_error_responses(401, 404, 409, 422, 423),
    )
    def update_automation(
        projectId: UUID,
        automationId: UUID,
        body: AutomationUpdate,
        idempotency_key: Key,
    ):
        return _view(
            service.update(
                str(projectId), str(automationId), str(idempotency_key), body.payload()
            )[0]
        )

    @router.get(
        "/{automationId}/impact",
        response_model=AutomationImpactView,
        responses=browser_error_responses(401, 404, 422),
    )
    def automation_impact(
        projectId: UUID,
        automationId: UUID,
        action: Literal["delete", "unlinkWorkflow"] = Query("delete"),
    ):
        return service.impact(str(projectId), str(automationId), action)

    @router.delete(
        "/{automationId}",
        response_model=OperationAccepted,
        status_code=202,
        responses={
            200: {"model": OperationAccepted},
            **browser_error_responses(401, 404, 409, 412, 422, 423),
        },
    )
    def delete_automation(
        projectId: UUID,
        automationId: UUID,
        body: AutomationDeleteRequest,
        response: Response,
        idempotency_key: Key,
    ):
        operation = service.delete(
            str(projectId), str(automationId), str(idempotency_key), body.payload()
        )
        if operation.status in {"succeeded", "failed"}:
            response.status_code = 200
        return {"operation": _op_view(operation)}

    @router.get(
        "/{automationId}/validation",
        response_model=AutomationValidationView,
        responses=browser_error_responses(401, 404, 422, 503),
    )
    def validate_automation(projectId: UUID, automationId: UUID):
        value = service.validation(str(projectId), str(automationId))
        return {
            "status": value.status,
            "valid": value.valid,
            "runnable": value.runnable,
            "issues": [issue.__dict__ for issue in value.issues],
            "capabilityRequirements": value.capability_requirements,
            "checkedAt": value.checked_at,
        }

    return router


def _view(value):
    return automation_to_dict(value)


def _op_view(value):
    return {
        "operationId": value.operation_id,
        "projectId": value.project_id,
        "idempotencyKey": value.idempotency_key,
        "kind": value.kind,
        "status": value.status,
        "statusRevision": value.status_revision,
        "resource": value.resource,
        "result": value.result,
        "error": value.error,
        "createdAt": value.created_at,
        "updatedAt": value.updated_at,
        "completedAt": value.completed_at,
    }
