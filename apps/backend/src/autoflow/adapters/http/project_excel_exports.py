from fastapi import APIRouter, Header
from pydantic import Field

from autoflow.application.project_data.excel_export import ProjectExcelExportService
from autoflow.infrastructure.database.project_excel_common import operation_view

from .errors import browser_error_responses
from .project_data import CanonicalId, Key
from .project_excel_schemas import ExcelExportCreate
from .project_schemas import OperationAccepted
from .schemas import ApiModel


class ReconcileOperationCreate(ApiModel):
    expected_status_revision: int = Field(ge=1, strict=True)


def project_excel_exports_router(service: ProjectExcelExportService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}")

    @router.post(
        "/tables/{tableId}/exports/xlsx",
        status_code=202,
        response_model=OperationAccepted,
        responses=browser_error_responses(401, 403, 404, 409, 410, 422, 423),
    )
    def export(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: ExcelExportCreate,
        idempotency_key: Key,
        window_id: int = Header(alias="x-autoflow-file-window-id"),
        window_token: str = Header(alias="x-autoflow-file-window-token"),
    ):
        operation = service.start(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True, exclude_none=True),
            window_id,
            window_token,
        )
        return {"operation": operation_view(operation)}

    @router.post(
        "/operations/{operationId}/reconcile",
        status_code=202,
        response_model=OperationAccepted,
    )
    def reconcile(
        projectId: CanonicalId,
        operationId: CanonicalId,
        body: ReconcileOperationCreate,
        idempotency_key: Key,
    ):
        operation = service.reconcile(
            str(projectId),
            str(operationId),
            str(idempotency_key),
            body.expected_status_revision,
        )
        return {"operation": operation_view(operation)}

    return router
