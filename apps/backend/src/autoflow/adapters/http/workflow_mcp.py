from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response

from autoflow.application.workflows.mcp import WorkflowMcpService

from .workflow_studio_schemas import (
    StudioMcpCommandLookup,
    StudioMcpConfigResponse,
    StudioMcpReloaded,
    StudioMcpReloadRequest,
    StudioMcpSaved,
    StudioMcpSaveRequest,
    StudioMcpStatus,
)


def workflow_mcp_router(service: WorkflowMcpService) -> APIRouter:
    router = APIRouter(prefix="/api/ai-assistant/mcp", tags=["studio-mcp"])

    @router.get(
        "/config",
        response_model=StudioMcpConfigResponse,
        response_model_exclude_unset=True,
    )
    def config() -> dict[str, Any]:
        return service.config()

    @router.put("/config", response_model=StudioMcpSaved)
    def save(body: StudioMcpSaveRequest, response: Response) -> dict[str, Any]:
        payload, status = service.save(
            config=body.config.model_dump(by_alias=True, exclude_unset=True),
            command_id=body.command_id,
            expected_revision=body.expected_revision,
        )
        response.status_code = status
        return payload

    @router.post("/reload", response_model=StudioMcpReloaded)
    async def reload(
        body: StudioMcpReloadRequest, response: Response
    ) -> dict[str, Any]:
        payload, status = await service.reload(
            command_id=body.command_id,
            expected_revision=body.expected_revision,
        )
        response.status_code = status
        return payload

    @router.get("/status", response_model=StudioMcpStatus)
    def status() -> dict[str, Any]:
        return service.status()

    @router.get("/commands/{command_id}", response_model=StudioMcpCommandLookup)
    def command(command_id: str) -> dict[str, Any]:
        return service.command(command_id)

    return router
