from fastapi import APIRouter, BackgroundTasks, Header

from autoflow.application.project_data.excel_import import ExcelImportService

from .project_data import CanonicalId, Key
from .project_excel_schemas import (
    ExcelReplaceImpact,
    ExcelTableImportCreate,
    ExcelTableReplace,
)
from .project_schemas import OperationAccepted


def project_excel_import_router(service: ExcelImportService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}")

    @router.post(
        "/table-imports/excel", response_model=OperationAccepted, status_code=202
    )
    def create(
        projectId: CanonicalId,
        body: ExcelTableImportCreate,
        idempotency_key: Key,
        tasks: BackgroundTasks,
        window_id: int = Header(alias="x-autoflow-file-window-id"),
        proof: str = Header(alias="x-autoflow-file-window-token"),
    ):
        operation = service.submit(
            str(projectId),
            None,
            str(idempotency_key),
            body.model_dump(by_alias=True),
            window_id,
            proof,
        )
        if operation["status"] == "accepted":
            tasks.add_task(service.run, operation["operationId"])
        return {"operation": operation}

    @router.post(
        "/tables/{tableId}/imports/excel/impact", response_model=ExcelReplaceImpact
    )
    def impact(projectId: CanonicalId, tableId: CanonicalId):
        return service.preview_replace(str(projectId), str(tableId))

    @router.post(
        "/tables/{tableId}/imports/excel",
        response_model=OperationAccepted,
        status_code=202,
    )
    def replace(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: ExcelTableReplace,
        idempotency_key: Key,
        tasks: BackgroundTasks,
        window_id: int = Header(alias="x-autoflow-file-window-id"),
        proof: str = Header(alias="x-autoflow-file-window-token"),
    ):
        operation = service.submit(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
            window_id,
            proof,
        )
        if operation["status"] == "accepted":
            tasks.add_task(service.run, operation["operationId"])
        return {"operation": operation}

    return router
