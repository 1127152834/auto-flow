from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from autoflow.application.workflows.events import WorkflowEventService
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.domain.workflows.runs import WorkflowRunStart
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
from autoflow.infrastructure.events.workflows import WorkflowEventBroker


def _start() -> WorkflowRunStart:
    return WorkflowRunStart(
        run_id="run-events",
        workflow_id="workflow",
        document_id="document",
        workflow_name="事件流程",
        document_snapshot={"nodes": []},
        layout_snapshot={},
        profile_id="profile",
        profile_snapshot={"locale": "zh-CN"},
        mode="run",
    )


@pytest.mark.asyncio
async def test_events_commit_before_broadcast_and_reconnect_by_sequence(
    tmp_path: Path,
) -> None:
    database = tmp_path / "events.sqlite3"
    migrate_database(database)
    repository = SqlAlchemyWorkflowRuns(create_session_factory(database))
    run_service = WorkflowRunService(
        repository, clock=lambda: datetime(2026, 9, 15, tzinfo=UTC)
    )
    run_service.start(_start())
    broker = WorkflowEventBroker()
    service = WorkflowEventService(repository, broker)

    first = await service.append(
        "run-events", "execution:started", {"workflowId": "workflow"}
    )
    assert first.sequence == 1
    async with broker.subscribe("run-events") as live:
        second = await service.append(
            "run-events", "execution:log", {"level": "info", "message": "中文日志"}
        )
        observed = await asyncio.wait_for(live.get(), timeout=1)
    assert observed == second
    assert observed.sequence == 2
    persisted = repository.get("run-events")
    assert persisted is not None
    assert persisted.event_count == 2
    assert persisted.log_count == 1

    replay = service.list("run-events", after_sequence=1, limit=100)
    assert replay == (second,)
    assert service.list("run-events", after_sequence=2, limit=100) == ()


@pytest.mark.asyncio
async def test_broadcast_failure_does_not_rollback_committed_event(tmp_path: Path) -> None:
    database = tmp_path / "broadcast.sqlite3"
    migrate_database(database)
    repository = SqlAlchemyWorkflowRuns(create_session_factory(database))
    WorkflowRunService(
        repository, clock=lambda: datetime(2026, 9, 15, tzinfo=UTC)
    ).start(_start())

    class FailedPublisher:
        async def publish(self, _event: object) -> None:
            persisted = repository.get("run-events")
            assert persisted is not None
            assert persisted.event_count == 1
            raise RuntimeError("synthetic broadcast failure")

    service = WorkflowEventService(repository, FailedPublisher())

    with pytest.raises(RuntimeError, match="synthetic broadcast failure"):
        await service.append("run-events", "execution:started", {})

    assert [event.sequence for event in repository.list_events("run-events", 0, 20)] == [1]
