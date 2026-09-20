from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import ConfigDict, Field

from autoflow.adapters.http.schemas import ApiModel
from autoflow.application.workflows.inspection import WorkflowInspectionService

from .workflow_studio_schemas import (
    StudioBrowserPageCommand,
    StudioBrowserPages,
    StudioBrowserStatus,
    StudioPickerSessionRequest,
    StudioPickerSessionStartRequest,
    StudioPickerSessionState,
    StudioSelectorTestRequest,
    StudioSelectorTestResult,
)


class BrowserOpenRequest(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    profile_id: str = Field(min_length=1)
    url: str | None = None


class BrowserCloseRequest(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    session_id: str | None = Field(default=None, min_length=1)


class BrowserNavigateRequest(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: str = Field(min_length=1, pattern=r"\S")


def workflow_inspection_router(service: WorkflowInspectionService) -> APIRouter:
    router = APIRouter(tags=["studio-workflow-inspection"])

    @router.get("/api/browser/status", response_model=StudioBrowserStatus)
    async def browser_status() -> dict[str, Any]:
        return await service.status()

    @router.post("/api/browser/open", response_model=StudioBrowserStatus)
    async def browser_open(request: BrowserOpenRequest) -> dict[str, Any]:
        return await service.open(profile_id=request.profile_id, url=request.url)

    @router.post("/api/browser/close")
    async def browser_close(request: BrowserCloseRequest) -> dict[str, Any]:
        return await service.close(request.session_id)

    @router.post("/api/browser/navigate")
    async def browser_navigate(request: BrowserNavigateRequest) -> dict[str, Any]:
        return await service.navigate(request.url)

    @router.get("/api/browser/url")
    async def browser_url() -> dict[str, Any]:
        return await service.current_url()

    @router.get("/api/browser/pages", response_model=StudioBrowserPages)
    async def browser_pages() -> dict[str, Any]:
        return await service.pages()

    @router.post("/api/browser/pages", response_model=StudioBrowserPages)
    async def browser_page(request: StudioBrowserPageCommand) -> dict[str, Any]:
        return await service.page(request.model_dump(by_alias=True))

    @router.post(
        "/api/element-picker/start", response_model=StudioPickerSessionState
    )
    async def picker_start(
        request: StudioPickerSessionStartRequest,
    ) -> dict[str, Any]:
        if request.profile_id is None:
            from autoflow.domain.workflows.runs import WorkflowRunError

            raise WorkflowRunError(
                "INSPECTION_PROFILE_REQUIRED", "请选择 CloakBrowser Profile", 422
            )
        return await service.start_picker(
            session_id=request.session_id,
            profile_id=request.profile_id,
            url=request.url,
        )

    @router.post("/api/element-picker/stop", response_model=StudioPickerSessionState)
    async def picker_stop(request: StudioPickerSessionRequest) -> dict[str, Any]:
        return await service.stop_picker(request.session_id)

    @router.get("/api/element-picker/status", response_model=StudioPickerSessionState)
    def picker_status(
        session_id: str | None = Query(default=None, alias="sessionId"),
    ) -> dict[str, Any]:
        return service.picker_status(session_id)

    async def read_result(
        session_id: str | None, *, similar: bool
    ) -> dict[str, Any]:
        status = service.picker_status(session_id)
        if not status["active"]:
            return status
        return await service.picker_result(status["sessionId"], similar=similar)

    @router.get("/api/element-picker/result")
    async def picker_result(
        session_id: str | None = Query(default=None, alias="sessionId"),
    ) -> dict[str, Any]:
        return await read_result(session_id, similar=False)

    @router.get("/api/element-picker/selected")
    async def picker_selected(
        session_id: str | None = Query(default=None, alias="sessionId"),
    ) -> dict[str, Any]:
        return await read_result(session_id, similar=False)

    @router.get("/api/element-picker/similar")
    async def picker_similar(
        session_id: str | None = Query(default=None, alias="sessionId"),
    ) -> dict[str, Any]:
        return await read_result(session_id, similar=True)

    @router.post(
        "/api/element-picker/test-selector",
        response_model=StudioSelectorTestResult,
    )
    async def test_selector(request: StudioSelectorTestRequest) -> dict[str, Any]:
        return await service.test_selector(request.model_dump(by_alias=True))

    return router
