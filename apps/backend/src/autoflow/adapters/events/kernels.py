from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from autoflow.application.kernels.operations import KernelOperation
from autoflow.infrastructure.events.kernel_events import KernelEventBroker


def kernels_events_router(
    broker: KernelEventBroker,
    snapshot: Callable[[], list[KernelOperation]],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/kernels", tags=["kernels"])

    @router.get("/events")
    async def events() -> StreamingResponse:
        return StreamingResponse(
            kernel_event_stream(broker, snapshot),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router


async def kernel_event_stream(
    broker: KernelEventBroker,
    snapshot: Callable[[], list[KernelOperation]],
    *,
    heartbeat_interval: float = 15.0,
) -> AsyncIterator[str]:
    subscription = broker.subscribe()
    try:
        yield _frame("snapshot", snapshot())
        while True:
            try:
                operations = await asyncio.wait_for(
                    subscription.queue.get(), timeout=heartbeat_interval
                )
            except TimeoutError:
                yield ": heartbeat\n\n"
            else:
                yield _frame("snapshot", operations)
    finally:
        subscription.close()


def _frame(event: str, operations: list[KernelOperation]) -> str:
    payload = {
        "type": "snapshot",
        "operations": [operation.as_dict() for operation in operations],
    }
    return f"event: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"
