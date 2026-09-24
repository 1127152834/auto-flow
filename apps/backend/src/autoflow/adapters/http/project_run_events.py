import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse

from autoflow.application.project_runs.events import ProjectRunEvents
from autoflow.domain.project_runs.models import ProjectRunError

from .project_run_events_schemas import ProjectRunEventPage, ProjectRunEventView


def project_run_events_router(events: ProjectRunEvents) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}/tasks/{taskId}/events")

    @router.get("", response_model=ProjectRunEventPage)
    def read_events(
        projectId: UUID,
        taskId: UUID,
        after_sequence: Annotated[int, Query(alias="afterSequence", ge=0)] = 0,
    ):
        return events.page(str(projectId), str(taskId), after_sequence)

    @router.get("/stream")
    async def stream_events(
        request: Request,
        projectId: UUID,
        taskId: UUID,
        after_sequence: Annotated[int, Query(alias="afterSequence", ge=0)] = 0,
        last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    ):
        cursor = _resume_cursor(after_sequence, last_event_id)
        first_page = await asyncio.to_thread(
            events.page, str(projectId), str(taskId), cursor
        )

        async def stream():
            nonlocal cursor
            page = first_page
            while not await request.is_disconnected():
                for item in page["items"]:
                    cursor = item["sequence"]
                    data = ProjectRunEventView.model_validate(item).model_dump_json(by_alias=True)
                    yield f"id: {cursor}\nevent: {item['kind']}\ndata: {data}\n\n"
                if page["terminal"] and not page["hasMore"]:
                    return
                if not page["items"]:
                    await asyncio.sleep(0.25)
                page = await asyncio.to_thread(
                    events.page, str(projectId), str(taskId), cursor
                )

        return StreamingResponse(stream(), media_type="text/event-stream")

    return router


def _resume_cursor(query: int, header: str | None) -> int:
    if header is None:
        return query
    try:
        value = int(header)
    except ValueError as error:
        raise ProjectRunError(
            "VALIDATION_ERROR", "Last-Event-ID 必须是非负整数", 422
        ) from error
    if value < 0 or str(value) != header:
        raise ProjectRunError("VALIDATION_ERROR", "Last-Event-ID 必须是非负整数", 422)
    return value
