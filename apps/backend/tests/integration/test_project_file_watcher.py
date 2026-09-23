"""Real filesystem events through the existing project worker and durable outputs."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from autoflow.domain.workflows.catalog import runnable_module_types
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)
from tests.integration.test_project_data_worker import (
    _dispatcher,
    _NoBrowserResources,
    _queued_pure_data_run,
    _wait_for_started,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["created", "modified", "deleted", "timeout", "cancel", "missing"])
async def test_project_file_watcher_event_and_cleanup(tmp_path: Path, action: str) -> None:
    assert "file_watcher_trigger" in runnable_module_types()
    watched = tmp_path / "watched"
    if action != "missing":
        watched.mkdir()
    target = watched / "目标.txt"
    if action in {"modified", "deleted"}:
        target.write_text("before", encoding="utf-8")
    factory, queued = _queued_pure_data_run(tmp_path, node_data={
        "moduleType": "file_watcher_trigger", "watchPath": str(watched),
        "watchType": action if action in {"created", "modified", "deleted"} else "any",
        "filePattern": "*.txt", "timeout": 1 if action == "timeout" else 0,
        "saveToVariable": "changed_file",
    })
    worker = ProjectWorkflowWorkerManager(tmp_path / "worker")
    resources = _NoBrowserResources()
    dispatcher = _dispatcher(factory, worker, resources)
    try:
        running = await dispatcher.dispatch(queued.run_id, expected_status_revision=queued.status_revision,
                                            execution_generation=queued.execution_generation)
        if action in {"created", "modified", "deleted", "cancel"}:
            await _wait_for_started(factory, queued.run_id)
            # Retain the empty/old baseline through the source's initial snapshot.
            await asyncio.sleep(.3)
            (watched / "ignored.log").write_text("must not trigger", encoding="utf-8")
            if action == "created":
                target.write_text("after", encoding="utf-8")
            elif action == "modified":
                previous = target.stat().st_mtime
                target.write_text("after", encoding="utf-8")
                os.utime(target, (previous + 2, previous + 2))
            elif action == "deleted":
                target.unlink()
            else:
                await dispatcher.cancel(running.run_id, expected_status_revision=running.status_revision,
                                        execution_generation=running.execution_generation)
        await asyncio.wait_for(dispatcher.wait_idle(), 10)
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            finished = repository.get_run(run_id=queued.run_id)
            events = repository.list_events(queued.run_id, after_sequence=0, limit=100)
        expected = "failed" if action in {"timeout", "missing"} else "cancelled" if action == "cancel" else "succeeded"
        assert finished is not None and finished.status == expected
        outputs = [event.payload for event in events if event.kind == "output"]
        if expected == "succeeded":
            assert len(outputs) == 1 and outputs[0]["name"] == "changed_file"
            value = outputs[0]["value"]
            assert value["eventType"] == action
            assert value["fileName"] == "目标.txt" and value["filePath"] == str(target)
            assert value["timestamp"]
        else:
            assert outputs == []
        assert not worker.busy() and not resources.requests
    finally:
        await dispatcher.shutdown()
        factory.dispose()
