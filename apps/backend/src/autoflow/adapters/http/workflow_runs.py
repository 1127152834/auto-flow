from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, StreamingResponse

from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.domain.workflows.debug import prepare_debug
from autoflow.domain.workflows.run_validation import prepare_run, validate_runtime

from .errors import browser_error_responses
from .workflow_run_schemas import (
    DebugCommand,
    DebugCommandRead,
    DebugOptions,
    DebugVariables,
    HandoffCommand,
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
            target=body.target.model_dump(by_alias=True, mode="json") if body.target else None,
            mode=body.mode, debug=(body.debug or DebugOptions()).model_dump(by_alias=True) if body.mode == "debug" else None,
        ))

    @router.post("/validate", response_model=list[dict[str, str]])
    async def validate(body: RunStart) -> list[dict[str, str]]:
        prepared = prepare_debug(body.document.model_dump(by_alias=True), body.layout.model_dump(by_alias=True), (body.debug or DebugOptions()).model_dump(by_alias=True)) if body.mode == "debug" else prepare_run(body.document.model_dump(by_alias=True), body.layout.model_dump(by_alias=True))
        validate_runtime(prepared.document, body.target is not None and body.target.kind == "android")
        return [{"code": issue.code, "message": issue.message} for issue in prepared.warnings]

    @router.get("", response_model=RunList)
    def list_runs(
        workflow_id: str | None = Query(None, alias="workflowId"),
        offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    ) -> RunList:
        result = service.list(workflow_id, offset, limit)
        return RunList(
            items=[RunSummary.model_validate({(field.alias or name): item[field.alias or name] for name, field in RunSummary.model_fields.items() if (field.alias or name) in item}) for item in result["items"]],
            active_run_id=result["activeRunId"], next_offset=result["nextOffset"],
        )

    @router.get("/{run_id}", response_model=RunRead)
    def get(run_id: str) -> RunRead:
        return RunRead.model_validate(service.get(run_id))

    @router.post("/{run_id}/stop", response_model=RunRead)
    async def stop(run_id: str) -> RunRead:
        return RunRead.model_validate(await service.stop(run_id))

    @router.post("/{run_id}/handoffs/{handoff_id}/open", response_model=RunRead, status_code=202)
    async def open_native(run_id: str, handoff_id: str, body: HandoffCommand) -> RunRead:
        return RunRead.model_validate(await service.handoff_control(run_id, handoff_id, str(body.request_id), "open"))

    @router.post("/{run_id}/handoffs/{handoff_id}/continue", response_model=RunRead, status_code=202)
    async def continue_native(run_id: str, handoff_id: str, body: HandoffCommand) -> RunRead:
        return RunRead.model_validate(await service.handoff_control(run_id, handoff_id, str(body.request_id), "continue"))
    @router.post('/{run_id}/debug/commands', response_model=DebugCommandRead, status_code=202)
    async def debug_command(run_id: str, body: DebugCommand) -> DebugCommandRead:
        return DebugCommandRead.model_validate(await service.send_debug(run_id, body.model_dump(by_alias=True)))

    @router.get('/{run_id}/debug/commands/{command_id}', response_model=DebugCommandRead)
    def command_status(run_id: str, command_id: str) -> DebugCommandRead:
        return DebugCommandRead.model_validate(service.debug_command(run_id, command_id))

    @router.get('/{run_id}/debug/variables', response_model=DebugVariables)
    def variables(run_id: str, checkpoint_id: str | None = Query(None, alias='checkpointId'),
                  offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), after: int = Query(0, ge=0)) -> DebugVariables:
        return DebugVariables.model_validate(service.variables(run_id, checkpoint_id, offset, limit, after))

    @router.get('/{run_id}/logs', response_model=RunEvents)
    def logs(run_id: str, after_seq: int = Query(0, alias='afterSeq', ge=0), limit: int = Query(200, ge=1, le=1000),
             through_seq: int | None = Query(None, alias='throughSeq', ge=0), level: str = '', q: str = '', tail: bool = False,
             node_id: str = Query('', alias='nodeId'), execution_id: str = Query('', alias='executionId')) -> RunEvents:
        return RunEvents.model_validate(service.filtered_events(run_id, after_seq, limit, through_seq, {'level': level, 'q': q, 'nodeId': node_id, 'executionId': execution_id}, tail))

    @router.get('/{run_id}/export')
    def export(run_id: str, kind: Literal['logs', 'results', 'diagnostics'] = 'logs',
               through_seq: int | None = Query(None, alias='throughSeq', ge=0), level: str = '', q: str = '',
               node_id: str = Query('', alias='nodeId'), execution_id: str = Query('', alias='executionId')) -> StreamingResponse:
        extension, mime = ('zip', 'application/zip') if kind == 'results' else ('jsonl', 'application/x-ndjson') if kind == 'logs' else ('json', 'application/json')
        chunks = service.export(run_id, kind, through_seq, {'level': level, 'q': q, 'nodeId': node_id, 'executionId': execution_id})
        return StreamingResponse(chunks, media_type=mime, headers={'Content-Disposition': f'attachment; filename="{kind}.{extension}"', 'Cache-Control': 'no-store'})

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
