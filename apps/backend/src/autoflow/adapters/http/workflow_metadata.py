"""Frozen WebRPA field rules, scoped to the approved Studio catalog."""

from pathlib import Path

from fastapi import APIRouter

from .errors import browser_error_responses
from .workflow_studio_schemas import StudioModuleRequiredFields

METADATA_PATH = Path(__file__).with_name("module-required-fields.json")


def workflow_metadata_router() -> APIRouter:
    router = APIRouter(
        prefix="/api/system",
        tags=["studio-metadata"],
        responses=browser_error_responses(401, 500),
    )

    @router.get("/module-required-fields", response_model=StudioModuleRequiredFields)
    def module_required_fields() -> StudioModuleRequiredFields:
        return StudioModuleRequiredFields.model_validate_json(METADATA_PATH.read_bytes())

    return router
