from fastapi import APIRouter

from autoflow.application.project_data.status_batches import RecordStatusBatchService

from .errors import browser_error_responses
from .project_data import CanonicalId, Key
from .project_data_status_batch_schemas import (
    RecordStatusBatchCancel,
    RecordStatusBatchPreview,
    RecordStatusBatchRequest,
)
from .project_schemas import OperationAccepted
from .projects import _op


def record_status_batches_router(service: RecordStatusBatchService) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/projects/{projectId}/tables/{tableId}/record-status-batches"
    )

    @router.post(
        "/preview",
        response_model=RecordStatusBatchPreview,
        responses=browser_error_responses(401, 404, 410, 412, 422, 423),
    )
    def preview(
        projectId: CanonicalId, tableId: CanonicalId, body: RecordStatusBatchRequest
    ):
        return service.preview(
            str(projectId), str(tableId), body.model_dump(by_alias=True)
        )

    @router.post(
        "",
        status_code=202,
        response_model=OperationAccepted,
        responses=browser_error_responses(401, 404, 409, 410, 412, 422, 423),
    )
    def start(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: RecordStatusBatchRequest,
        idempotency_key: Key,
    ):
        operation, _ = service.start(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )
        return {"operation": _op(operation)}

    @router.post(
        "/{operationId}/cancel",
        status_code=202,
        response_model=OperationAccepted,
        responses=browser_error_responses(401, 404, 409, 422),
    )
    def cancel(
        projectId: CanonicalId,
        tableId: CanonicalId,
        operationId: CanonicalId,
        body: RecordStatusBatchCancel,
        idempotency_key: Key,
    ):
        operation, _ = service.cancel(
            str(projectId),
            str(tableId),
            str(operationId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )
        return {"operation": _op(operation)}

    return router
