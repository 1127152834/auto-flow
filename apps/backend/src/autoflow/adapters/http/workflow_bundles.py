from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from autoflow.adapters.http.schemas import ApiModel
from autoflow.application.workflows.bundles import WorkflowBundleService


class BundleExport(ApiModel):
    name: str
    content: dict[str, Any]


class BundleImport(ApiModel):
    bundle: Any


def workflow_bundles_router(service: WorkflowBundleService) -> APIRouter:
    router = APIRouter(prefix="/api/workflow-bundle", tags=["studio-workflow-bundle"])

    @router.post("/export")
    def export_bundle(request: BundleExport) -> dict[str, Any]:
        return {
            "success": True,
            "bundle": service.export(request.name, request.content),
        }

    @router.post("/import")
    def import_bundle(request: BundleImport) -> dict[str, Any]:
        return service.import_bundle(request.bundle)

    return router
