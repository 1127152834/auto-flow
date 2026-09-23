from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response

from autoflow.application.projects.lifecycle import ProjectLifecycleService
from autoflow.application.projects.overview import ProjectOverviewService
from autoflow.application.projects.service import AVAILABILITY, ProjectService
from autoflow.domain.projects.models import project_to_dict

from .errors import browser_error_responses
from .project_schemas import (
    ArchiveProjectRequest,
    DeleteProjectRequest,
    OperationAccepted,
    ProjectCreate,
    ProjectLifecycleImpact,
    ProjectOpenResult,
    ProjectOperationPage,
    ProjectOperationView,
    ProjectOverview,
    ProjectPage,
    ProjectPatch,
    ProjectSummary,
    ProjectView,
    RestoreProjectRequest,
)

Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def projects_router(
    service: ProjectService, overview_service: ProjectOverviewService
) -> APIRouter:
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
    def overview(projectId: UUID, timezone: str | None = None):
        return {
            **overview_service.get(str(projectId), timezone=timezone),
            "availability": AVAILABILITY,
        }

    @router.get(
        "/projects/{projectId}/operations",
        response_model=ProjectOperationPage,
        response_model_exclude_unset=True,
        responses=browser_error_responses(401, 404, 422),
    )
    def operations(
        projectId: UUID,
        page: int = Query(1, ge=1, le=2_147_483_647),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
        kind: Literal[
            "createProject",
            "updateProject",
            "createAutomation",
            "updateAutomation",
            "startBatch",
            "stopBatch",
            "forceStopBatch",
            "followUpBatch",
            "workflowInteraction",
            "createTable",
            "updateTable",
            "mutateField",
            "saveTableSchema",
            "mutateStatus",
            "createRecord",
            "createRecords",
            "updateRecord",
            "setRecordStatus",
            "deleteRecord",
            "setRecordStatuses",
            "cancelRecordStatuses",
            "inspectExcel",
            "importExcel",
            "exportXlsx",
            "reconcileOperation",
            "archiveProject",
            "restoreProject",
            "deleteProject",
            "deleteAutomation",
        ]
        | None = None,
        status: Literal["accepted", "running", "reconciling", "succeeded", "failed"]
        | None = None,
        resource_type: Literal[
            "project", "table", "field", "status", "record", "automation", "batch"
        ]
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
        response_model_exclude_unset=True,
        responses=browser_error_responses(401, 404, 422),
    )
    def operation(projectId: UUID, operationId: UUID):
        return _op(
            service.operation(operation_id=str(operationId), project_id=str(projectId))
        )

    @router.get(
        "/projects/{projectId}/operations/by-idempotency-key/{key}",
        response_model=ProjectOperationView,
        response_model_exclude_unset=True,
        responses=browser_error_responses(401, 404, 422),
    )
    def operation_by_key(projectId: UUID, key: UUID):
        return _op(service.operation(key=str(key), project_id=str(projectId)))

    @router.get(
        "/workspace/operations/by-idempotency-key/{key}",
        response_model=ProjectOperationView,
        response_model_exclude_unset=True,
        responses=browser_error_responses(401, 404, 422),
    )
    def workspace_operation(key: UUID):
        return _op(service.workspace_operation(str(key)))

    return router


def project_lifecycle_router(lifecycle: ProjectLifecycleService) -> APIRouter:
    """Archive, restore and permanent delete of one project.

    Declared async so the coordinator wake-up stays on the event loop; the
    commands themselves are short local transactions.
    """
    router = APIRouter(prefix="/api/v1/projects/{projectId}")

    @router.get(
        "/lifecycle-impact",
        response_model=ProjectLifecycleImpact,
        responses=browser_error_responses(401, 404, 409, 422),
    )
    def lifecycle_impact(
        projectId: UUID,
        action: Literal["archive", "delete"] = Query(...),
    ):
        return lifecycle.impact(str(projectId), action)

    @router.post(
        "/archive",
        response_model=OperationAccepted,
        status_code=202,
        responses={
            200: {"model": OperationAccepted},
            **browser_error_responses(401, 404, 409, 412, 422, 423),
        },
    )
    async def archive_project(
        projectId: UUID,
        body: ArchiveProjectRequest,
        response: Response,
        idempotency_key: Key,
    ):
        operation = lifecycle.archive(
            str(projectId), str(idempotency_key), body.payload()
        )
        if _terminal(operation):
            response.status_code = 200
        return {"operation": _op(operation)}

    @router.post(
        "/restore",
        response_model=OperationAccepted,
        status_code=202,
        responses={
            200: {"model": OperationAccepted},
            **browser_error_responses(401, 404, 409, 412, 422),
        },
    )
    async def restore_project(
        projectId: UUID,
        body: RestoreProjectRequest,
        response: Response,
        idempotency_key: Key,
    ):
        operation = lifecycle.restore(
            str(projectId), str(idempotency_key), body.payload()
        )
        if _terminal(operation):
            response.status_code = 200
        return {"operation": _op(operation)}

    @router.delete(
        "",
        response_model=OperationAccepted,
        status_code=202,
        responses={
            200: {"model": OperationAccepted},
            **browser_error_responses(401, 404, 409, 412, 422, 423),
        },
    )
    async def delete_project(
        projectId: UUID,
        body: DeleteProjectRequest,
        response: Response,
        idempotency_key: Key,
    ):
        operation = lifecycle.delete(
            str(projectId), str(idempotency_key), body.payload()
        )
        if _terminal(operation):
            response.status_code = 200
        return {"operation": _op(operation)}

    return router


def _terminal(operation) -> bool:
    return operation.status in {"succeeded", "failed"}


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
