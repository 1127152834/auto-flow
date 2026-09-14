import hmac

from fastapi import APIRouter, Header, Request, Response

from autoflow.application.project_data.excel import ProjectExcelService
from autoflow.domain.projects.models import ProjectError

from .project_data import CanonicalId, Key
from .project_excel_schemas import (
    ExcelInspectionCreate,
    ExcelInspectionView,
    ProjectFileSelectionCreate,
)
from .project_schemas import OperationAccepted


class ExcelInspectionResult(OperationAccepted):
    inspection: ExcelInspectionView


def internal_project_files_router(service: ProjectExcelService) -> APIRouter:
    router = APIRouter(prefix="/internal/project-files", include_in_schema=False)

    @router.post("/selections", status_code=204)
    def register_selection(
        body: ProjectFileSelectionCreate,
        request: Request,
        x_autoflow_host_token: str = Header(alias="x-autoflow-host-token"),
        window_token: str = Header(alias="x-autoflow-file-window-token"),
    ) -> Response:
        expected = getattr(request.app.state.config, "host_token", None)
        if not expected or not hmac.compare_digest(x_autoflow_host_token, expected):
            raise ProjectError("UNAUTHORIZED", "Host authentication failed", 401)
        service.register_selection(body.model_dump(by_alias=True), window_token)
        return Response(status_code=204)

    return router


def project_excel_inspection_router(service: ProjectExcelService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}")

    @router.post(
        "/table-imports/excel/inspect",
        response_model=ExcelInspectionResult | OperationAccepted,
        responses={202: {"model": OperationAccepted}},
    )
    def inspect(
        projectId: CanonicalId,
        body: ExcelInspectionCreate,
        response: Response,
        idempotency_key: Key,
        window_id: int = Header(alias="x-autoflow-file-window-id"),
        window_token: str = Header(alias="x-autoflow-file-window-token"),
    ):
        result = service.inspect(
            str(projectId),
            str(idempotency_key),
            str(body.selection_token),
            window_id,
            window_token,
        )
        if "inspection" not in result:
            response.status_code = 202
        return result

    return router
