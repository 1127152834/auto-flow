from pathlib import Path

from fastapi import APIRouter

from autoflow.adapters.http.workflow_studio_schemas import StudioModuleRequiredFields

METADATA_PATH = Path(__file__).with_name("module-required-fields.json")


def workflow_metadata_router() -> APIRouter:
    router = APIRouter(prefix="/api/system", tags=["workflow-metadata"])

    @router.get("/module-required-fields", response_model=StudioModuleRequiredFields)
    def module_required_fields() -> StudioModuleRequiredFields:
        return StudioModuleRequiredFields.model_validate_json(METADATA_PATH.read_bytes())

    return router
