from __future__ import annotations

import asyncio
import copy
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioCommandLookup,
    StudioCommandReceipt,
    StudioDesktopActionState,
    StudioEventCommandRequest,
    StudioInputPromptState,
    StudioJsScriptState,
    StudioSpeechState,
)
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.domain.workflows.runs import WorkflowRunError


@dataclass(frozen=True, slots=True)
class StudioEvent:
    sequence: int
    event: str
    data: dict[str, Any]


class StudioEventJournal:
    """Service-lifetime Studio event journal with strict reconnect cursors."""

    def __init__(self) -> None:
        self._events: list[StudioEvent] = []
        self._subscribers: set[asyncio.Queue[StudioEvent]] = set()
        self._lock = asyncio.Lock()

    @property
    def sequence(self) -> int:
        return len(self._events)

    async def publish(self, event: str, data: dict[str, Any]) -> StudioEvent:
        async with self._lock:
            item = StudioEvent(len(self._events) + 1, event, copy.deepcopy(data))
            self._events.append(item)
            for queue in tuple(self._subscribers):
                queue.put_nowait(item)
            return item

    def replay(self, *, after_sequence: int) -> tuple[StudioEvent, ...]:
        return self._replay_unlocked(after_sequence)

    def _replay_unlocked(self, after_sequence: int) -> tuple[StudioEvent, ...]:
        if after_sequence < 0:
            raise WorkflowRunError("EVENT_CURSOR_INVALID", "事件游标无效", 422)
        if after_sequence > len(self._events):
            raise WorkflowRunError(
                "EVENT_CURSOR_AHEAD",
                "事件游标超过当前服务连接代次",
                409,
                {"afterSeq": after_sequence, "latestSeq": len(self._events)},
            )
        return tuple(self._events[after_sequence:])

    @asynccontextmanager
    async def subscribe(
        self, *, after_sequence: int
    ) -> AsyncIterator[asyncio.Queue[StudioEvent]]:
        queue: asyncio.Queue[StudioEvent] = asyncio.Queue()
        async with self._lock:
            replay = self._replay_unlocked(after_sequence)
            for item in replay:
                queue.put_nowait(item)
            self._subscribers.add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                self._subscribers.discard(queue)


def _frame(item: StudioEvent) -> bytes:
    import json

    data = json.dumps(item.data, ensure_ascii=False, separators=(",", ":"))
    return f"id: {item.sequence}\nevent: {item.event}\ndata: {data}\n\n".encode()


def _scope_run_event(item: StudioEvent, project_id: str | None, runs: WorkflowRunService | None) -> StudioEvent:
    if project_id is not None and (item.event.startswith("execution:") or "runId" in item.data):
        run_id = item.data.get("runId")
        if not isinstance(run_id, str) or runs is None or not runs.belongs_to_project(run_id, project_id):
            # The journal's sequence is workspace-wide. Preserve its cursor
            # without leaking another project's event, identity or payload.
            return StudioEvent(item.sequence, "studio:cursor", {})
    return item


class StudioEventCommands(Protocol):
    async def submit_event_command(
        self, command_id: str, event: str, data: Mapping[str, Any]
    ) -> tuple[dict[str, Any], int]: ...

    def event_command(self, command_id: str) -> tuple[dict[str, Any], int]: ...

    def request_run(self, request_id: str) -> str | None: ...

    def command_run(self, command_id: str) -> str | None: ...

    def input_prompt_state(self, request_id: str) -> dict[str, str]: ...

    def js_script_state(self, request_id: str) -> dict[str, str]: ...

    def tts_request_state(self, request_id: str) -> dict[str, str]: ...

    def desktop_action_state(self, request_id: str) -> dict[str, str]: ...


def workflow_events_router(
    journal: StudioEventJournal, commands: StudioEventCommands | None = None,
    runs: WorkflowRunService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/events", tags=["studio-events"])

    @router.get("/stream")
    async def stream_events(
        request: Request,
        after_sequence: int = Query(default=0, alias="afterSeq", ge=0),
        project_id: str | None = Query(default=None, alias="projectId", min_length=1, max_length=200),
    ) -> StreamingResponse:
        # Validate before creating the streaming response so an impossible cursor
        # is returned as the normal AutoFlow error envelope.
        journal.replay(after_sequence=after_sequence)

        async def generate() -> AsyncIterator[bytes]:
            async with journal.subscribe(after_sequence=after_sequence) as queue:
                while not await request.is_disconnected():
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=15)
                        yield _frame(_scope_run_event(item, project_id, runs))
                    except TimeoutError:
                        yield b": keep-alive\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    if commands is not None:
        def require_request_project(
            request: Request,
            project_id: str | None = Query(default=None, alias="projectId", min_length=1, max_length=200),
        ) -> None:
            if project_id is not None:
                owner = commands.request_run(request.path_params["request_id"])
                if owner is None or runs is None or not runs.belongs_to_project(owner, project_id):
                    raise WorkflowRunError("REQUEST_NOT_FOUND", "交互请求不存在", 404)

        @router.post("/commands", response_model=StudioCommandReceipt)
        async def submit_command(
            request: StudioEventCommandRequest,
            project_id: str | None = Query(default=None, alias="projectId", min_length=1, max_length=200),
        ) -> JSONResponse:
            if project_id is not None and request.event in {
                "input_prompt_result", "js_script_claim", "js_script_result", "tts_claim", "tts_result", "desktop_action_claim", "desktop_action_result",
            }:
                request_id = request.data.get("requestId")
                owner = commands.request_run(request_id) if isinstance(request_id, str) else None
                if owner is None or runs is None or not runs.belongs_to_project(owner, project_id):
                    raise WorkflowRunError("REQUEST_NOT_FOUND", "交互请求不存在", 404)
            payload, http_status = await commands.submit_event_command(
                request.command_id, request.event, request.data
            )
            return JSONResponse(payload, status_code=http_status)

        @router.get("/commands/{command_id}", response_model=StudioCommandLookup)
        def get_command(
            command_id: str,
            project_id: str | None = Query(default=None, alias="projectId", min_length=1, max_length=200),
        ) -> JSONResponse:
            payload, http_status = commands.event_command(command_id)
            run_id = commands.command_run(command_id) if project_id is not None else None
            if project_id is not None and isinstance(run_id, str) and (runs is None or not runs.belongs_to_project(run_id, project_id)):
                raise WorkflowRunError("COMMAND_NOT_FOUND", "命令记录不存在", 404)
            return JSONResponse(payload, status_code=http_status)

        @router.get(
            "/input-prompts/{request_id}", response_model=StudioInputPromptState, dependencies=[Depends(require_request_project)]
        )
        def get_input_prompt(request_id: str) -> dict[str, str]:
            return commands.input_prompt_state(request_id)

        @router.get(
            "/js-requests/{request_id}", response_model=StudioJsScriptState, dependencies=[Depends(require_request_project)]
        )
        def get_js_script(request_id: str) -> dict[str, str]:
            return commands.js_script_state(request_id)

        @router.get(
            "/tts-requests/{request_id}", response_model=StudioSpeechState, dependencies=[Depends(require_request_project)]
        )
        def get_tts_request(request_id: str) -> dict[str, str]:
            return commands.tts_request_state(request_id)

        @router.get(
            "/desktop-actions/{request_id}",
            response_model=StudioDesktopActionState, dependencies=[Depends(require_request_project)],
        )
        def get_desktop_action(request_id: str) -> dict[str, str]:
            return commands.desktop_action_state(request_id)

    return router
