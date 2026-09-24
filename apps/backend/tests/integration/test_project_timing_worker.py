"""Project runs use the migrated timer/probability pair and real worker cancellation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from time import monotonic
from uuid import uuid4

import pytest

from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflows import (
    SqlAlchemyWorkflowDocuments,
    SqlAlchemyWorkflowRepository,
)
from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)
from tests.integration.test_project_data_worker import (
    _dispatcher,
    _NoBrowserResources,
    _studio_payload,
)
from tests.integration.test_project_run_start import setup, start_payload


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["path1", "path2", "past", "bad_delay", "bad_probability", "stop"])
async def test_project_timer_probability_routing_and_cleanup(tmp_path: Path, scenario: str) -> None:
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    timer = {"scheduleType": "delay", "delaySeconds": 30 if scenario == "stop" else 0 if scenario == "bad_delay" else 1}
    if scenario == "past":
        timer = {"scheduleType": "datetime", "targetDate": "2000-01-01", "targetTime": "00:00"}
    document = _studio_payload(automation.workflow_id)
    document.update(schemaVersion=3, nodes=[
        {"id": "timer", "type": "scheduled_task", "position": {"x": 0, "y": 0}, "data": {"moduleType": "scheduled_task", "config": timer}},
        {"id": "choose", "type": "probability_trigger", "position": {"x": 180, "y": 0}, "data": {"moduleType": "probability_trigger", "config": {"probability": 0 if scenario == "path2" else 101 if scenario == "bad_probability" else 100}}},
        *[{"id": path, "type": "print_log", "position": {"x": 360, "y": index * 100}, "data": {"moduleType": "print_log", "config": {"logMessage": path}}} for index, path in enumerate(("path1", "path2"))],
    ], edges=[
        {"id": "begin", "source": "timer", "target": "choose"},
        *[{"id": path, "source": "choose", "target": path, "sourceHandle": path} for path in ("path1", "path2")],
    ], variables=[])
    worker = ProjectWorkflowWorkerManager(tmp_path / "worker")
    resources = _NoBrowserResources()
    dispatcher = _dispatcher(factory, worker, resources)
    try:
        WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).update(
            automation.workflow_id, document, expected_revision=1, client_request_id=str(uuid4()),
        )
        runtime = WorkflowRuntimeService(factory, SqlAlchemyWorkflowRepository(factory))
        coordinator._core = runtime
        batch, _, _ = coordinator.start(project.project_id, automation.automation_id, str(uuid4()), start_payload(automation))
        task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
        run = runtime.query_run(run_id=task.run_id)
        assert run is not None
        started = monotonic()
        running = await dispatcher.dispatch(run.run_id, expected_status_revision=run.status_revision, execution_generation=run.execution_generation)
        if scenario == "stop":
            for _ in range(200):
                with factory() as session:
                    events = SqlAlchemyWorkflowRuntimeRepository(session).list_events(run.run_id, after_sequence=0, limit=100)
                if any(event.kind == "nodeAttempt" and event.node_id == "timer" for event in events):
                    break
                await asyncio.sleep(0.05)
            else:
                pytest.fail("timer did not begin")
            stopped = monotonic()
            await dispatcher.cancel(run.run_id, expected_status_revision=running.status_revision, execution_generation=running.execution_generation)
        await dispatcher.wait_idle()
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            finished = repository.get_run(run_id=run.run_id)
            events = repository.list_events(run.run_id, after_sequence=0, limit=100)
        expected = "cancelled" if scenario == "stop" else "failed" if scenario.startswith("bad_") else "succeeded"
        assert finished is not None and finished.status == expected, (finished, events)
        node_ids = [event.node_id for event in events if event.kind == "nodeAttempt" and event.payload.get("status") == "succeeded"]
        if expected == "succeeded":
            selected = "path2" if scenario == "path2" else "path1"
            assert node_ids == ["timer", "choose", selected]
            assert any(event.kind == "log" and event.payload.get("isUserLog") and event.payload.get("message") == selected for event in events)
            assert not any(event.node_id == ("path1" if selected == "path2" else "path2") for event in events)
            if scenario != "past":
                assert monotonic() - started >= 1
        else:
            assert node_ids == (["timer"] if scenario == "bad_probability" else [])
            assert not any(event.node_id in {"path1", "path2"} for event in events)
        if scenario == "stop":
            assert monotonic() - stopped < 3
        assert not resources.requests and not worker.busy()
    finally:
        await dispatcher.shutdown()
        factory.dispose()
