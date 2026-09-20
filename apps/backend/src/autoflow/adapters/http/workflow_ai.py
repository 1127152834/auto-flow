from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import ConfigDict, Field

from autoflow.application.workflows.assistant import WorkflowAssistantService

from .schemas import ApiModel


class AssistantConfig(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    model_id: str = Field(min_length=1, pattern=r"\S")
    temperature: float = Field(default=0.7, ge=0, le=2, allow_inf_nan=False)
    max_tokens: int = Field(default=4000, ge=1, le=1_000_000)
    system_prompt: str = ""
    enable_tools: bool = True
    auto_approve: bool = False


class AssistantChatRequest(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    session_id: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"\S"
    )
    message: str = Field(min_length=1, pattern=r"\S")
    config: AssistantConfig
    workflow_context: dict[str, Any] = Field(default_factory=dict)
    images: list[str] | None = Field(default=None, max_length=8)
    fallback_model_ids: list[str] | None = Field(default=None, max_length=20)


class AssistantCreateSession(ApiModel):
    title: str | None = None


class AssistantRenameSession(ApiModel):
    title: str = Field(min_length=1, pattern=r"\S")


class AssistantTruncateSession(ApiModel):
    message_id: str = Field(min_length=1, pattern=r"\S")


class AssistantModelTest(ApiModel):
    model_id: str = Field(min_length=1, pattern=r"\S")


class AssistantExtractFile(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    filename: str = Field(min_length=1, max_length=512, pattern=r"\S")
    content_base64: str = Field(min_length=1, max_length=24 * 1024 * 1024)


class AssistantExtractedFile(ApiModel):
    success: bool
    text: str
    error: str


class AssistantTranscribe(ApiModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    audio_base64: str = Field(min_length=1, max_length=48 * 1024 * 1024)
    language: str = Field(default="zh", min_length=2, max_length=16)
    model_size: str = Field(default="base", min_length=1, max_length=16)


class AssistantTranscription(ApiModel):
    success: bool
    text: str
    error: str = ""
    language: str | None = None


class AssistantMessage(ApiModel):
    id: str
    role: str
    content: str
    timestamp: str | None = None
    tool_calls: list[dict[str, Any]] | None = Field(default=None, alias="tool_calls")
    tool_call_id: str | None = Field(default=None, alias="tool_call_id")
    images: list[str] | None = None
    attachment_names: list[str] | None = None
    reasoning_content: str | None = Field(default=None, alias="reasoning_content")
    content_ref: str | None = None
    content_artifact: dict[str, Any] | None = None
    reasoning_content_ref: str | None = None
    reasoning_artifact: dict[str, Any] | None = None


class AssistantPendingAction(ApiModel):
    command_id: str
    action: str
    payload: dict[str, Any]


class AssistantSessionResponse(ApiModel):
    id: str
    title: str
    messages: list[AssistantMessage]
    status: Literal[
        "idle", "running", "waiting_for_action", "completed", "failed", "cancelled"
    ]
    pending_action: AssistantPendingAction | None = None
    revision: int


class AssistantSessionSummary(ApiModel):
    id: str
    title: str
    message_count: int
    updated_at: str
    last_message_preview: str


class AssistantCreatedSession(ApiModel):
    session_id: str
    title: str


class AssistantChatResponse(ApiModel):
    session_id: str
    message: AssistantMessage


class AssistantSuccess(ApiModel):
    success: bool


class AssistantTruncated(AssistantSuccess):
    messages: list[AssistantMessage]


class AssistantCancelled(AssistantSuccess):
    session_id: str


class AssistantModelTestResponse(AssistantSuccess):
    message: str
    detail: str
    latency_ms: float


def workflow_ai_router(service: WorkflowAssistantService) -> APIRouter:
    router = APIRouter(prefix="/api/ai-assistant", tags=["studio-assistant"])

    @router.get("/sessions", response_model=list[AssistantSessionSummary])
    def sessions() -> list[dict[str, Any]]:
        return service.list_sessions()

    @router.post("/sessions", response_model=AssistantCreatedSession)
    def create_session(body: AssistantCreateSession) -> dict[str, str]:
        return service.create_session(body.title)

    @router.get(
        "/sessions/{session_id}",
        response_model=AssistantSessionResponse,
        response_model_exclude_none=True,
    )
    def get_session(session_id: str) -> dict[str, Any]:
        return service.get_session(session_id)

    @router.delete("/sessions/{session_id}", response_model=AssistantSuccess)
    def delete_session(session_id: str) -> dict[str, bool]:
        return service.delete_session(session_id)

    @router.patch("/sessions/{session_id}/title", response_model=AssistantSuccess)
    def rename_session(
        session_id: str, body: AssistantRenameSession
    ) -> dict[str, bool]:
        return service.rename_session(session_id, body.title)

    @router.post(
        "/sessions/{session_id}/truncate",
        response_model=AssistantTruncated,
        response_model_exclude_none=True,
    )
    def truncate_session(
        session_id: str, body: AssistantTruncateSession
    ) -> dict[str, Any]:
        return service.truncate_session(session_id, body.message_id)

    @router.post("/sessions/{session_id}/cancel", response_model=AssistantCancelled)
    async def cancel(session_id: str) -> dict[str, Any]:
        return await service.cancel(session_id)

    @router.post(
        "/chat", response_model=AssistantChatResponse, response_model_exclude_none=True
    )
    async def chat(body: AssistantChatRequest) -> dict[str, Any]:
        session_id = body.session_id or service.create_session()["session_id"]
        return await service.chat(
            session_id=session_id,
            message=body.message,
            model_id=body.config.model_id,
            enable_tools=body.config.enable_tools,
            workflow_context=body.workflow_context,
            system_prompt=body.config.system_prompt,
            temperature=body.config.temperature,
            max_tokens=body.config.max_tokens,
            images=body.images,
            fallback_model_ids=body.fallback_model_ids,
        )

    @router.post("/test-connection", response_model=AssistantModelTestResponse)
    async def test_connection(body: AssistantModelTest) -> dict[str, Any]:
        return await service.test_model(body.model_id)

    @router.get("/artifacts/{kind}/{artifact_id}", response_class=FileResponse)
    def artifact(kind: str, artifact_id: str) -> FileResponse:
        path, media_type = service.artifact_file(kind, artifact_id)
        return FileResponse(path, media_type=media_type, filename=path.name)

    @router.post("/extract-file", response_model=AssistantExtractedFile)
    async def extract_file(body: AssistantExtractFile) -> dict[str, Any]:
        return await service.extract_file(body.filename, body.content_base64)

    @router.post(
        "/transcribe",
        response_model=AssistantTranscription,
        response_model_exclude_none=True,
    )
    async def transcribe(body: AssistantTranscribe) -> dict[str, Any]:
        return await service.transcribe(
            body.audio_base64, body.language, body.model_size
        )

    return router
