"""Authenticated aggregate schema preview and commit transport."""

from fastapi import APIRouter

from autoflow.application.project_data.schema import DataSchemaService

from .errors import browser_error_responses
from .project_data import CanonicalId, Key
from .project_data_schema_schemas import (
    DataSchemaCandidate,
    DataSchemaCommit,
    DataSchemaImpact,
    DataSchemaResult,
)


def project_data_schema_router(service: DataSchemaService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}/tables/{tableId}/schema")

    @router.post(
        "/preview",
        response_model=DataSchemaImpact,
        responses=browser_error_responses(401, 404, 409, 410, 412, 422, 423),
    )
    def preview(
        projectId: CanonicalId, tableId: CanonicalId, body: DataSchemaCandidate
    ):
        return service.preview(
            str(projectId),
            str(tableId),
            body.model_dump(by_alias=True, exclude_unset=True),
        )

    @router.post(
        "",
        response_model=DataSchemaResult,
        responses=browser_error_responses(401, 404, 409, 410, 412, 422, 423),
    )
    def commit(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: DataSchemaCommit,
        idempotency_key: Key,
    ):
        result, _, _ = service.commit(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True, exclude_unset=True),
        )
        return result

    return router
