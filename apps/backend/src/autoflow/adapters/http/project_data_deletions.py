from fastapi import APIRouter

from autoflow.application.project_data.deletions import DataDeletionService

from .errors import browser_error_responses
from .project_data import CanonicalId, Key
from .project_data_deletion_schemas import RecordDelete, StatusDelete
from .project_schemas import OperationAccepted


def project_data_deletion_router(service: DataDeletionService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}/tables/{tableId}")

    @router.delete(
        "/statuses/{statusId}",
        response_model=OperationAccepted,
        status_code=202,
        responses=browser_error_responses(401, 404, 409, 410, 412, 422, 423),
    )
    def delete_status(
        projectId: CanonicalId,
        tableId: CanonicalId,
        statusId: CanonicalId,
        body: StatusDelete,
        idempotency_key: Key,
    ):
        _, operation, _ = service.delete_status(
            str(projectId),
            str(tableId),
            str(statusId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )
        return {"operation": operation}

    @router.delete(
        "/records/{recordKey}",
        response_model=OperationAccepted,
        status_code=202,
        responses=browser_error_responses(401, 404, 409, 410, 412, 422, 423),
    )
    def delete_record(
        projectId: CanonicalId,
        tableId: CanonicalId,
        recordKey: str,
        body: RecordDelete,
        idempotency_key: Key,
    ):
        _, operation, _ = service.delete_record(
            str(projectId),
            str(tableId),
            recordKey,
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )
        return {"operation": operation}

    return router
