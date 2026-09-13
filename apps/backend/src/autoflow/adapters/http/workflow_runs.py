from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.domain.workflows.run_validation import prepare_run

from .errors import browser_error_responses
from .workflow_run_schemas import (
    RunArtifacts,
    RunEvents,
    RunList,
    RunRead,
    RunStart,
    RunSummary,
)


def workflow_runs_router(service: WorkflowRunService) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/workflows/runs", tags=["workflow-runs"],
        responses=browser_error_responses(401, 404, 409, 422, 500, 503),
    )

    @router.post("", response_model=RunRead, status_code=201)
    async def start(body: RunStart) -> RunRead:
        return RunRead.model_validate(await service.start(
            body.run_id, body.document.model_dump(by_alias=True),
            body.layout.model_dump(by_alias=True), body.profile_id,
        ))

    @router.post("/validate", response_model=list[dict[str, str]])
    async def validate(body: RunStart) -> list[dict[str, str]]:
        prepared = prepare_run(body.document.model_dump(by_alias=True), body.layout.model_dump(by_alias=True))
        return [{"code": issue.code, "message": issue.message} for issue in prepared.warnings]

    @router.get("", response_model=RunList)
    def list_runs(
        workflow_id: str | None = Query(None, alias="workflowId"),
        offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    ) -> RunList:
        result = service.list(workflow_id, offset, limit)
        return RunList(
            items=[RunSummary.model_validate({name: item.get(field.alias or name, field.get_default(call_default_factory=True)) for name, field in RunSummary.model_fields.items()}) for item in result["items"]],
            active_run_id=result["activeRunId"], next_offset=result["nextOffset"],
        )

    @router.get("/{run_id}", response_model=RunRead)
    def get(run_id: str) -> RunRead:
        return RunRead.model_validate(service.get(run_id))

    @router.post("/{run_id}/stop", response_model=RunRead)
    async def stop(run_id: str) -> RunRead:
        return RunRead.model_validate(await service.stop(run_id))

    @router.get("/{run_id}/events", response_model=RunEvents)
    def events(
        run_id: str, after_seq: int = Query(0, alias="afterSeq", ge=0),
        limit: int = Query(200, ge=1, le=1000),
    ) -> RunEvents:
        return RunEvents.model_validate(service.events(run_id, after_seq, limit))

    @router.get("/{run_id}/artifacts", response_model=RunArtifacts)
    def artifacts(run_id: str, after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                  node_id: str | None = Query(None, alias="nodeId"), execution_id: str | None = Query(None, alias="executionId")) -> RunArtifacts:
        return RunArtifacts.model_validate(service.artifacts(run_id, after, limit, node_id, execution_id))

    @router.get("/{run_id}/artifacts/{artifact_id}", response_class=FileResponse)
    def artifact(run_id: str, artifact_id: str) -> FileResponse:
        path, item = service.artifact(run_id, artifact_id)
        return FileResponse(path, media_type=item["mimeType"], filename=item["name"], headers={"Cache-Control": "no-store"})

    return router
