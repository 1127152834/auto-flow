from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Response, status
from pydantic import ConfigDict, Field

from autoflow.adapters.http.errors import error_response
from autoflow.adapters.http.schemas import ApiModel
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.domain.workflows.errors import WorkflowDocumentError


class WorkflowWrite(ApiModel):
    model_config = ConfigDict(
        alias_generator=None,
        populate_by_name=True,
        extra="allow",
    )

    client_request_id: str = Field(alias="clientRequestId", min_length=1, max_length=128)


class WorkflowUpdate(WorkflowWrite):
    expected_revision: int = Field(alias="expectedRevision", ge=1)


def _payload(value: WorkflowWrite) -> dict[str, Any]:
    return value.model_dump(
        by_alias=True,
        exclude={"client_request_id", "expected_revision"},
    )


def workflows_router(service: WorkflowDocumentService) -> APIRouter:
    router = APIRouter(prefix="/api/workflows", tags=["studio-workflows"])

    @router.get("")
    def list_workflows(projectId: str | None = Query(default=None, min_length=1, max_length=200)) -> list[dict[str, Any]]:
        summaries = service.list_summaries(cursor=0, limit=200, project_id=projectId)
        return [service.get(item.id).to_payload() for item in summaries.items]

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_workflow(request: WorkflowWrite) -> dict[str, Any]:
        saved = service.create(
            _payload(request), client_request_id=request.client_request_id
        )
        return saved.to_payload()

    # Frozen Studio owns these static paths. Later milestones replace the explicit
    # pending response; keeping them here prevents dynamic ID route shadowing.
    @router.get("/data-latest/full")
    def latest_data() -> Response:
        return error_response(
            501,
            "WORKFLOW_CAPABILITY_PENDING",
            "该工作流数据能力将在对应迁入批次提供",
        )

    @router.get("/global-variables")
    def global_variables() -> Response:
        return error_response(
            501,
            "WORKFLOW_CAPABILITY_PENDING",
            "该工作流变量能力将在对应迁入批次提供",
        )

    @router.get("/{workflow_id}")
    def get_workflow(workflow_id: str, projectId: str | None = Query(default=None, min_length=1, max_length=200)) -> dict[str, Any]:
        saved = service.get(workflow_id)
        if projectId is not None and saved.project_id != projectId:
            raise WorkflowDocumentError("WORKFLOW_NOT_FOUND", "工作流不存在", 404)
        return saved.to_payload()

    @router.put("/{workflow_id}")
    def update_workflow(
        workflow_id: str, request: WorkflowUpdate
    ) -> dict[str, Any]:
        current = service.get(workflow_id)
        project_id = request.model_dump(by_alias=True).get("projectId")
        if project_id is not None and current.project_id != project_id:
            raise WorkflowDocumentError("WORKFLOW_NOT_FOUND", "工作流不存在", 404)
        saved = service.update(
            workflow_id,
            _payload(request),
            expected_revision=request.expected_revision,
            client_request_id=request.client_request_id,
        )
        return saved.to_payload()

    @router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_workflow(
        workflow_id: str,
        expected_revision: int = Query(alias="expectedRevision", ge=1),
    ) -> Response:
        service.delete(workflow_id, expected_revision=expected_revision)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
