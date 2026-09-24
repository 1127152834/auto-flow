from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import Field, JsonValue

from autoflow.application.project_runs.interactions import ProjectRunInteractions
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.domain.project_runs.models import ProjectRunError

from .errors import browser_error_responses
from .schemas import ApiModel
from .workflow_studio_schemas import StudioInputPromptRequest


class ProjectInteractionCommand(ApiModel):
    command_id: UUID
    execution_generation: int = Field(strict=True, ge=0)
    event: Literal["input_prompt_result", "js_script_claim", "js_script_result"]
    data: dict[str, JsonValue]


class ProjectInteractionReceipt(ApiModel):
    command_id: str
    request_id: str
    status: Literal["accepted", "applied", "unconfirmed"]


class ProjectInputPromptRequest(StudioInputPromptRequest):
    type: Literal["execution:input_prompt"]
    status: Literal["pending", "submitted"]
    run_id: str
    execution_generation: int
    node_id: str
    execution_id: str
    command_id: str | None = None
    execution_context: dict[str, JsonValue] | None = None


class ProjectJsScriptRequest(ApiModel):
    type: Literal["execution:js_script"]
    request_id: str
    status: Literal["pending", "claimed", "submitted"]
    claim_id: str | None = None
    run_id: str
    execution_generation: int
    node_id: str
    execution_id: str
    command_id: str | None = None
    execution_context: dict[str, JsonValue] | None = None
    code: str
    variables: dict[str, JsonValue]


class ProjectInteractionClosed(ApiModel):
    request_id: str
    status: Literal["cancelled"]


class ProjectInteractionIdentity(ApiModel):
    project_id: str
    task_id: str
    run_id: str
    execution_generation: int
    request_id: str
    type: Literal["execution:input_prompt", "execution:js_script"]
    status: Literal["pending", "claimed", "submitted"]


def project_pending_interactions_router(service: ProjectRunInteractions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/project-run-interactions")

    @router.get("", response_model=list[ProjectInteractionIdentity])
    def pending(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return service.pending()

    return router


def project_run_interactions_router(
    service: ProjectRunInteractions, gate: QuiesceGate
) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/projects/{projectId}/tasks/{taskId}/interactions"
    )

    @router.get("/requests/{requestId}", response_model=ProjectInputPromptRequest | ProjectJsScriptRequest | ProjectInteractionClosed)
    def request(projectId: UUID, taskId: UUID, requestId: UUID, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return service.request(str(projectId), str(taskId), str(requestId))

    @router.post(
        "/commands",
        status_code=202,
        response_model=ProjectInteractionReceipt,
        responses=browser_error_responses(401, 404, 409, 422, 503),
    )
    async def submit(projectId: UUID, taskId: UUID, body: ProjectInteractionCommand):
        with gate.mutation() as admitted:
            if not admitted:
                raise ProjectRunError(
                    "SERVICE_UNAVAILABLE", "系统正在暂停写入，请稍后重试", 503
                )
            return await service.submit(
                str(projectId),
                str(taskId),
                str(body.command_id),
                body.execution_generation,
                body.event,
                body.data,
            )

    @router.get("/commands/{commandId}", response_model=ProjectInteractionReceipt)
    def command(projectId: UUID, taskId: UUID, commandId: UUID):
        return service.command(str(projectId), str(taskId), str(commandId))

    return router
