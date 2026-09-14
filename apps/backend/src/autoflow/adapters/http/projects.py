from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response

from autoflow.application.projects.service import AVAILABILITY, ProjectService
from autoflow.domain.projects.models import project_to_dict

from .errors import browser_error_responses
from .project_schemas import (
    ProjectCreate,
    ProjectOpenResult,
    ProjectOperationPage,
    ProjectOperationView,
    ProjectOverview,
    ProjectPage,
    ProjectPatch,
    ProjectSummary,
    ProjectView,
)

Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def projects_router(service: ProjectService) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get(
        "/projects",
        response_model=ProjectPage,
        responses=browser_error_responses(401, 422),
    )
    def list_projects(
        q: str | None = None,
        lifecycle_state: Literal["active", "archived"] | None = Query(
            None, alias="lifecycleState"
        ),
        page: int = Query(1, ge=1, le=2_147_483_647),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
        sort: str = "-lastOpenedAt",
    ):
        items, total = service.list(
            q=q,
            lifecycle_state=lifecycle_state,
            page=page,
            page_size=page_size,
            sort=sort,
        )
        return {
            "items": [
                {**project_to_dict(item), "availability": AVAILABILITY}
                for item in items
            ],
            "page": page,
            "pageSize": page_size,
            "total": total,
            "sort": sort,
        }

    @router.post(
        "/projects",
        response_model=ProjectView,
        status_code=201,
        responses={
            200: {"model": ProjectView},
            **browser_error_responses(401, 409, 422),
        },
    )
    def create_project(body: ProjectCreate, response: Response, idempotency_key: Key):
        project, _operation, replayed = service.create(
            str(idempotency_key), body.payload()
        )
        if replayed:
            response.status_code = 200
        return project_to_dict(project)

    @router.get(
        "/projects/{projectId}",
        response_model=ProjectSummary,
        responses=browser_error_responses(401, 404, 422),
    )
    def get_project(projectId: UUID):
        return {
            **project_to_dict(service.get(str(projectId))),
            "availability": AVAILABILITY,
        }

    @router.patch(
        "/projects/{projectId}",
        response_model=ProjectView,
        responses=browser_error_responses(401, 404, 409, 422, 423),
    )
    def patch_project(projectId: UUID, body: ProjectPatch, idempotency_key: Key):
        return project_to_dict(
            service.update(str(projectId), str(idempotency_key), body.payload())[0]
        )

    @router.post(
        "/projects/{projectId}/open",
        response_model=ProjectOpenResult,
        responses=browser_error_responses(401, 404, 409, 422),
    )
    def open_project(projectId: UUID):
        project = service.open(str(projectId))
        return {
            "project": project_to_dict(project),
            "lastOpenedAt": project.last_opened_at,
        }

    @router.get(
        "/projects/{projectId}/overview",
        response_model=ProjectOverview,
        responses=browser_error_responses(401, 404, 422),
    )
    def overview(projectId: UUID):
        return {
            "project": project_to_dict(service.get(str(projectId))),
            "counts": {},
            "availability": AVAILABILITY,
            "activity": [],
            "recent": [],
        }

    @router.get(
        "/projects/{projectId}/operations",
        response_model=ProjectOperationPage,
        responses=browser_error_responses(401, 404, 422),
    )
    def operations(
        projectId: UUID,
        page: int = Query(1, ge=1, le=2_147_483_647),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
        kind: Literal[
            "createProject",
            "updateProject",
            "createTable",
            "updateTable",
            "mutateField",
            "saveTableSchema",
            "mutateStatus",
            "createRecord",
            "updateRecord",
            "setRecordStatus",
            "deleteRecord",
            "setRecordStatuses",
            "cancelRecordStatuses",
            "inspectExcel",
            "importExcel",
            "exportXlsx",
            "reconcileOperation",
        ]
        | None = None,
        status: Literal["accepted", "running", "reconciling", "succeeded", "failed"]
        | None = None,
        resource_type: Literal["project", "table", "field", "status", "record"]
        | None = Query(None, alias="resourceType"),
    ):
        items, total = service.operations(
            str(projectId),
            page=page,
            page_size=page_size,
            kind=kind,
            status=status,
            resource_type=resource_type,
        )
        return {
            "items": [_op(item) for item in items],
            "page": page,
            "pageSize": page_size,
            "total": total,
            "sort": "-createdAt",
        }

    @router.get(
        "/projects/{projectId}/operations/{operationId}",
        response_model=ProjectOperationView,
        responses=browser_error_responses(401, 404, 422),
    )
    def operation(projectId: UUID, operationId: UUID):
        return _op(
            service.operation(operation_id=str(operationId), project_id=str(projectId))
        )

    @router.get(
        "/projects/{projectId}/operations/by-idempotency-key/{key}",
        response_model=ProjectOperationView,
        responses=browser_error_responses(401, 404, 422),
    )
    def operation_by_key(projectId: UUID, key: UUID):
        return _op(service.operation(key=str(key), project_id=str(projectId)))

    @router.get(
        "/workspace/operations/by-idempotency-key/{key}",
        response_model=ProjectOperationView,
        responses=browser_error_responses(401, 404, 422),
    )
    def workspace_operation(key: UUID):
        return _op(service.workspace_operation(str(key)))

    return router


def _op(value):
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
