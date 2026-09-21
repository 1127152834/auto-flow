from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import ConfigDict, Field

from autoflow.adapters.http.schemas import ApiModel
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.domain.workflows.runs import WorkflowRun

from .workflow_studio_schemas import StudioRunResultPage, StudioRunResultValue


class WorkflowRunCommands(Protocol):
    async def start(
        self, workflow_id: str, request: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...

    async def stop(self, workflow_id: str, run_id: str) -> Mapping[str, Any]: ...

    async def submit_event_command(
        self, command_id: str, event: str, data: Mapping[str, Any]
    ) -> tuple[dict[str, Any], int]: ...

    def event_command(self, command_id: str) -> tuple[dict[str, Any], int]: ...

    def input_prompt_state(self, request_id: str) -> dict[str, str]: ...

    def js_script_state(self, request_id: str) -> dict[str, str]: ...

    def tts_request_state(self, request_id: str) -> dict[str, str]: ...

    def desktop_action_state(self, request_id: str) -> dict[str, str]: ...

    async def trigger_webhook(
        self,
        webhook_id: str,
        *,
        method: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        body: Any,
    ) -> tuple[Any, int]: ...


class WorkflowExecuteRequest(ApiModel):
    model_config = ConfigDict(extra="allow")

    run_id: str = Field(alias="runId", min_length=1, max_length=128)
    document_id: str = Field(alias="documentId", min_length=1)
    profile_id: str = Field(alias="profileId", min_length=1)
    headless: bool = False
    document: dict[str, Any] | None = None


class WorkflowStopRequest(ApiModel):
    run_id: str = Field(alias="runId", min_length=1, max_length=128)


def run_summary(run: WorkflowRun) -> dict[str, Any]:
    return {
        "runId": run.run_id,
        "workflowId": run.workflow_id,
        "documentId": run.document_id,
        "workflowName": run.workflow_name,
        "status": run.status,
        "startedAt": run.started_at.isoformat(),
        "finishedAt": run.finished_at.isoformat() if run.finished_at else None,
        "logCount": run.log_count,
    }


def run_detail(run: WorkflowRun) -> dict[str, Any]:
    return {
        **run_summary(run),
        "documentSnapshot": run.document_snapshot,
        "layoutSnapshot": run.layout_snapshot,
        "profileSnapshot": run.profile_snapshot,
        "customModuleSnapshots": run.custom_module_snapshots,
    }


def workflow_run_command_router(commands: WorkflowRunCommands) -> APIRouter:
    router = APIRouter(prefix="/api/workflows", tags=["studio-workflow-runs"])

    @router.post("/{workflow_id}/execute", status_code=status.HTTP_202_ACCEPTED)
    async def execute_workflow(
        workflow_id: str, request: WorkflowExecuteRequest
    ) -> Mapping[str, Any]:
        return await commands.start(
            workflow_id, request.model_dump(by_alias=True, exclude_none=True)
        )

    @router.post("/{workflow_id}/stop", status_code=status.HTTP_202_ACCEPTED)
    async def stop_workflow(
        workflow_id: str, request: WorkflowStopRequest
    ) -> Mapping[str, Any]:
        return await commands.stop(workflow_id, request.run_id)

    return router


def workflow_trigger_router(commands: WorkflowRunCommands) -> APIRouter:
    router = APIRouter(prefix="/api/triggers", tags=["studio-workflow-triggers"])

    @router.get("/webhook/{webhook_id}")
    @router.post("/webhook/{webhook_id}")
    @router.put("/webhook/{webhook_id}")
    @router.delete("/webhook/{webhook_id}")
    async def trigger_webhook(webhook_id: str, request: Request) -> Response:
        body: Any = dict(request.query_params)
        if request.method in {"POST", "PUT"}:
            chunks: list[bytes] = []
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 1024 * 1024:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Webhook请求体超过1 MiB限制"},
                    )
                chunks.append(chunk)
            raw = b"".join(chunks)
            try:
                body = json.loads(raw) if raw else {}
            except (json.JSONDecodeError, UnicodeDecodeError):
                body = {}
        response_body, response_status = await commands.trigger_webhook(
            webhook_id,
            method=request.method,
            headers=dict(request.headers),
            query=dict(request.query_params),
            body=body,
        )
        return JSONResponse(content=response_body, status_code=response_status)

    return router


def _result_page(
    service: WorkflowRunService,
    run_id: str,
    *,
    cursor: int,
    limit: int,
    through_sequence: int | None,
) -> dict[str, Any]:
    run = service.get(run_id)
    rows = service.results(run_id)
    maximum = rows[-1]["sequence"] if rows else 0
    through = maximum if through_sequence is None else through_sequence
    if through < 0 or through > maximum:
        from autoflow.domain.workflows.runs import WorkflowRunError

        raise WorkflowRunError("RUN_RESULT_CURSOR_INVALID", "结果截止位置无效", 422)
    snapshot = [row for row in rows if row["sequence"] <= through]
    page = snapshot[cursor : cursor + limit]
    output: list[dict[str, Any]] = []
    for row in page:
        values = dict(row["values"])
        large_values: dict[str, str] = {}
        for key, value in tuple(values.items()):
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if len(encoded.encode()) > 4096:
                values.pop(key)
                large_values[key] = encoded[:180]
        output.append({**row, "values": values, "largeValues": large_values})
    return {
        "runId": run_id,
        "workflowId": run.workflow_id,
        "items": output,
        "total": len(snapshot),
        "throughSequence": through,
        "nextCursor": cursor + len(page) if cursor + len(page) < len(snapshot) else None,
    }


def _artifact_payload(value: Any) -> dict[str, Any]:
    return {
        "artifactId": value.artifact_id,
        "ordinal": value.ordinal,
        "nodeId": value.node_id,
        "executionId": value.execution_id,
        "size": value.size,
        "sha256": value.sha256,
        "mimeType": value.mime_type,
        "purpose": value.purpose,
        "eventSequence": value.event_sequence,
    }


def workflow_runs_router(
    service: WorkflowRunService, artifact_root: Path | None = None
) -> APIRouter:
    router = APIRouter(prefix="/api/workflow-runs", tags=["studio-workflow-runs"])

    @router.get("/{run_id}/results", response_model=StudioRunResultPage)
    def get_results(
        run_id: str,
        cursor: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
        through_sequence: int | None = Query(default=None, alias="throughSequence", ge=0),
    ) -> dict[str, Any]:
        return _result_page(
            service,
            run_id,
            cursor=cursor,
            limit=limit,
            through_sequence=through_sequence,
        )

    @router.get("/{run_id}/results/{sequence:int}/value", response_model=StudioRunResultValue)
    def get_result_value(run_id: str, sequence: int, key: str = Query()) -> dict[str, Any]:
        from autoflow.domain.workflows.runs import WorkflowRunError

        row = next((item for item in service.results(run_id) if item["sequence"] == sequence), None)
        if row is None or key not in row["values"]:
            raise WorkflowRunError("RUN_RESULT_NOT_FOUND", "运行结果值不存在", 404)
        return {"runId": run_id, "sequence": sequence, "key": key, "value": row["values"][key]}

    @router.get("/{run_id}/results/export", response_class=Response)
    def export_results(
        run_id: str,
        through_sequence: int = Query(alias="throughSequence", ge=0),
    ) -> Response:
        page = _result_page(
            service,
            run_id,
            cursor=0,
            limit=500,
            through_sequence=through_sequence,
        )
        rows = [
            row
            for row in service.results(run_id)
            if row["sequence"] <= page["throughSequence"]
        ]
        content = "".join(
            json.dumps({"runId": run_id, **row}, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        )
        return Response(
            content.encode(),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="results-{run_id}.jsonl"'},
        )

    @router.get("/{run_id}/artifacts")
    def list_artifacts(
        run_id: str,
        cursor: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        items, next_cursor = service.artifacts(run_id, cursor=cursor, limit=limit)
        return {
            "runId": run_id,
            "items": [_artifact_payload(item) for item in items],
            "nextCursor": next_cursor,
        }

    @router.get("/{run_id}/artifacts/{artifact_id}", response_class=FileResponse)
    def get_artifact(run_id: str, artifact_id: str) -> FileResponse:
        from autoflow.domain.workflows.runs import WorkflowRunError

        if artifact_root is None:
            raise WorkflowRunError("ARTIFACT_STORAGE_UNAVAILABLE", "运行产物存储不可用", 503)
        artifact = service.artifact(run_id, artifact_id)
        root = artifact_root.resolve()
        path = (root / artifact.relative_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise WorkflowRunError("ARTIFACT_FILE_MISSING", "运行产物文件缺失", 404)
        return FileResponse(path, media_type=artifact.mime_type, filename=path.name)

    @router.get("")
    def list_runs(
        document_id: str | None = Query(default=None, alias="documentId"),
        cursor: int = Query(default=0, ge=0),
        limit: int = Query(default=20, ge=1, le=200),
    ) -> dict[str, Any]:
        items, total, next_cursor = service.list_runs(
            document_id=document_id, cursor=cursor, limit=limit
        )
        return {
            "items": [run_summary(run) for run in items],
            "total": total,
            "nextCursor": next_cursor,
        }

    @router.get("/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        return run_detail(service.get(run_id))

    @router.get("/{run_id}/logs")
    def get_logs(
        run_id: str,
        cursor: int = Query(default=0, ge=0),
        limit: int = Query(default=200, ge=1, le=500),
        query: str | None = None,
        levels: str | None = None,
        node_id: str | None = Query(default=None, alias="nodeId"),
    ) -> dict[str, Any]:
        items, total, next_cursor = service.logs(
            run_id,
            cursor=cursor,
            limit=limit,
            query=query,
            levels=tuple(levels.split(",")) if levels else (),
            node_id=node_id,
        )
        run = service.get(run_id)
        return {
            "runId": run_id,
            "workflowId": run.workflow_id,
            "items": items,
            "total": total,
            "nextCursor": next_cursor,
        }

    return router
