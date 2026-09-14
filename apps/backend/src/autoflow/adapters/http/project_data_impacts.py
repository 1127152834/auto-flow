from fastapi import APIRouter

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.deletions import DataDeletionService
from autoflow.domain.project_data.identity import RecordKey, encode_record_key
from autoflow.domain.projects.models import ProjectError

from .errors import browser_error_responses
from .project_data import CanonicalId
from .project_data_impact_schemas import (
    DeletionImpactReport,
    FieldImpactReport,
    FieldImpactRequest,
    MutationImpactRequest,
    RecordDeleteImpactRequest,
    StatusDeleteImpactRequest,
)


def project_data_impact_router(
    service: DataCatalogService, deletions: DataDeletionService
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}")

    @router.post(
        "/mutation-impact",
        response_model=FieldImpactReport | DeletionImpactReport,
        responses=browser_error_responses(401, 404, 409, 410, 422),
    )
    def preview(projectId: CanonicalId, body: MutationImpactRequest):
        if isinstance(body, FieldImpactRequest):
            return service.preview_field_update(
                str(projectId),
                body.target.field_ref.model_dump(by_alias=True),
                body.change.model_dump(by_alias=True),
            )
        if isinstance(body, StatusDeleteImpactRequest):
            target = body.target
            if str(target.project_id) != str(projectId):
                raise ProjectError("STATUS_NOT_FOUND", "Status was not found", 404)
            return deletions.preview_status(
                str(projectId), target.table_id, target.status_id
            )
        assert isinstance(body, RecordDeleteImpactRequest)
        ref = body.target.record_ref
        if str(ref.project_id) != str(projectId):
            raise ProjectError("RECORD_NOT_FOUND", "Record was not found", 404)
        encoded = encode_record_key(
            RecordKey(ref.record_key.type, ref.record_key.value)
        )
        return deletions.preview_record(
            str(projectId),
            ref.table_id,
            ref.dataset_generation,
            encoded,
            ref.record_key.type,
        )

    return router
