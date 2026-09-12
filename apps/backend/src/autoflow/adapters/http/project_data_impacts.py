from fastapi import APIRouter

from autoflow.application.project_data.catalog import DataCatalogService

from .errors import browser_error_responses
from .project_data import CanonicalId
from .project_data_impact_schemas import FieldImpactReport, FieldImpactRequest


def project_data_impact_router(service: DataCatalogService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}")

    @router.post(
        "/mutation-impact",
        response_model=FieldImpactReport,
        responses=browser_error_responses(401, 404, 409, 410, 422),
    )
    def preview(projectId: CanonicalId, body: FieldImpactRequest):
        return service.preview_field_update(
            str(projectId),
            body.target.field_ref.model_dump(by_alias=True),
            body.change.model_dump(by_alias=True),
        )

    return router
