from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioRetentionCleanup,
    StudioRetentionLoaded,
    StudioRetentionSaved,
    StudioRetentionUpdate,
    StudioRetentionUsageResponse,
)
from autoflow.application.workflows.retention import StudioRetentionService


def studio_retention_router(service: StudioRetentionService) -> APIRouter:
    router = APIRouter(prefix="/api/retention", tags=["studio-retention"])

    @router.get("/config", response_model=StudioRetentionLoaded)
    def get_config() -> dict[str, Any]:
        return {"success": True, "config": service.load(), "usage": service.usage()}

    @router.post("/config", response_model=StudioRetentionSaved)
    def save_config(request: StudioRetentionUpdate) -> dict[str, Any]:
        updates = request.model_dump(by_alias=True, exclude_none=True)
        return {"success": True, "config": service.save(updates)}

    @router.get("/usage", response_model=StudioRetentionUsageResponse)
    def get_usage() -> dict[str, Any]:
        return {"success": True, "usage": service.usage()}

    @router.post("/cleanup", response_model=StudioRetentionCleanup)
    def cleanup() -> dict[str, Any]:
        return service.cleanup()

    return router
