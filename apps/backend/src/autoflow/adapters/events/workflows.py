import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.domain.workflows.runs import ACTIVE_RUN_STATES


def workflow_events_router(service: WorkflowRunService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/workflows/runs", tags=["workflow-runs"])

    @router.get("/{run_id}/stream", response_class=StreamingResponse)
    async def stream(run_id: str, after_seq: int = Query(0, alias="afterSeq", ge=0)) -> StreamingResponse:
        service.get(run_id)
        return StreamingResponse(
            workflow_event_stream(service, run_id, after_seq), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router


async def workflow_event_stream(
    service: WorkflowRunService, run_id: str, after_seq: int = 0, *, heartbeat_interval: float = 15,
) -> AsyncIterator[str]:
    with service.subscribe(run_id) as signal:
        while True:
            signal.clear()
            page = service.events(run_id, after_seq, 200)
            for event in page["items"]:
                after_seq = event["seq"]
                yield f"id: {after_seq}\nevent: run_event\ndata: {json.dumps(event, ensure_ascii=False, separators=(',', ':'))}\n\n"
            if page["hasMore"]:
                continue
            current = service.get(run_id)
            if current["state"] not in ACTIVE_RUN_STATES and after_seq >= current["latestSeq"]:
                return
            try:
                await asyncio.wait_for(signal.wait(), timeout=heartbeat_interval)
            except TimeoutError:
                yield ": heartbeat\n\n"
