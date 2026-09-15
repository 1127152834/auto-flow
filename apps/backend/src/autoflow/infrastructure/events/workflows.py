from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from autoflow.domain.workflows.runs import WorkflowRunEvent


class WorkflowEventBroker:
    def __init__(self) -> None:
        self._subscribers: dict[
            str, set[asyncio.Queue[WorkflowRunEvent]]
        ] = defaultdict(set)

    @asynccontextmanager
    async def subscribe(
        self, run_id: str
    ) -> AsyncIterator[asyncio.Queue[WorkflowRunEvent]]:
        queue: asyncio.Queue[WorkflowRunEvent] = asyncio.Queue()
        self._subscribers[run_id].add(queue)
        try:
            yield queue
        finally:
            subscribers = self._subscribers.get(run_id)
            if subscribers is not None:
                subscribers.discard(queue)
                if not subscribers:
                    self._subscribers.pop(run_id, None)

    async def publish(self, event: WorkflowRunEvent) -> None:
        for queue in tuple(self._subscribers.get(event.run_id, ())):
            queue.put_nowait(event)
