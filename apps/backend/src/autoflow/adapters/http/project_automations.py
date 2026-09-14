from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response

from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.domain.project_automations.models import automation_to_dict

from .errors import browser_error_responses
from .project_automation_schemas import (
    AutomationPage,
    AutomationUpdate,
    AutomationValidationView,
    AutomationView,
    AutomationWrite,
)

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
        projectId: UUID, body: AutomationWrite, response: Response, idempotency_key: Key
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
