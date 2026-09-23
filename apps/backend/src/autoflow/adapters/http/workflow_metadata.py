"""Frozen WebRPA field rules, scoped to the approved Studio catalog."""

from fastapi import APIRouter

from autoflow.domain.workflows.required_fields import MODULE_REQUIRED_FIELDS

from .errors import browser_error_responses
from .workflow_studio_schemas import StudioModuleRequiredFields


def workflow_metadata_router() -> APIRouter:
    router = APIRouter(
        prefix="/api/system",
        tags=["studio-metadata"],
        responses=browser_error_responses(401, 500),
    )

    @router.get("/module-required-fields", response_model=StudioModuleRequiredFields)
    def required_fields() -> StudioModuleRequiredFields:
        return StudioModuleRequiredFields.model_validate(MODULE_REQUIRED_FIELDS)

    return router
