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
    StudioRecorderBatch,
    StudioRecorderControl,
    StudioRecorderReadRequest,
    StudioRecorderStarted,
    StudioRecorderStartRequest,
    StudioRecorderStatus,
    StudioRecorderStopped,
    StudioRecordingReview,
    StudioRecordingReviewWrite,
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

    @router.post("/api/recorder/start", response_model=StudioRecorderStarted)
    async def recorder_start(request: StudioRecorderStartRequest) -> dict[str, Any]:
        return await service.start_recording(request.session_id)

    @router.get("/api/recorder/events", response_model=StudioRecorderBatch)
    async def recorder_events(
        session_id: str = Query(alias="sessionId"),
        after_seq: int = Query(default=0, alias="afterSeq", ge=0),
    ) -> dict[str, Any]:
        return await service.recording_events(session_id, after_seq=after_seq)

    @router.post("/api/recorder/stop", response_model=StudioRecorderStopped)
    async def recorder_stop(request: StudioRecorderReadRequest) -> dict[str, Any]:
        return await service.stop_recording(
            request.session_id, after_seq=request.after_seq
        )

    @router.post("/api/recorder/pause", response_model=StudioRecorderControl)
    async def recorder_pause(request: StudioRecorderReadRequest) -> dict[str, Any]:
        return await service.pause_recording(
            request.session_id, after_seq=request.after_seq
        )

    @router.post("/api/recorder/resume", response_model=StudioRecorderControl)
    async def recorder_resume(request: StudioRecorderReadRequest) -> dict[str, Any]:
        return await service.resume_recording(
            request.session_id, after_seq=request.after_seq
        )

    @router.get("/api/recorder/status", response_model=StudioRecorderStatus)
    def recorder_status(
        session_id: str | None = Query(default=None, alias="sessionId"),
    ) -> dict[str, Any]:
        return service.recording_status(session_id)

    @router.get(
        "/api/recorder/reviews/{document_id}", response_model=StudioRecordingReview
    )
    def recording_review(document_id: str) -> dict[str, Any]:
        return service.read_recording_review(document_id)

    @router.put(
        "/api/recorder/reviews/{document_id}", response_model=StudioRecordingReview
    )
    def save_recording_review(
        document_id: str, request: StudioRecordingReviewWrite
    ) -> dict[str, Any]:
        return service.save_recording_review(
            document_id, request.model_dump(by_alias=True)
        )

    return router
