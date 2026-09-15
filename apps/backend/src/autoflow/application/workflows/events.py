from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from autoflow.application.workflows.runs import WorkflowRunRepository
from autoflow.domain.workflows.runs import WorkflowRunEvent


class WorkflowEventPublisher(Protocol):
    async def publish(self, event: WorkflowRunEvent) -> None: ...


class WorkflowEventService:
    def __init__(
        self,
        repository: WorkflowRunRepository,
        publisher: WorkflowEventPublisher,
    ) -> None:
        self._repository = repository
        self._publisher = publisher

    async def append(
        self,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        node_id: str | None = None,
        execution_id: str | None = None,
        now: datetime | None = None,
    ) -> WorkflowRunEvent:
        event = self._repository.append_event(
            run_id,
            event_type,
            payload,
            now=now or datetime.now(UTC),
            node_id=node_id,
            execution_id=execution_id,
        )
        await self._publisher.publish(event)
        return event

    def list(
        self, run_id: str, *, after_sequence: int = 0, limit: int = 200
    ) -> tuple[WorkflowRunEvent, ...]:
        return self._repository.list_events(run_id, after_sequence, limit)
