from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.workflows.runs import WorkflowRunStart
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
from autoflow.infrastructure.filesystem.paths import AppPaths


def _start(run_id: str) -> WorkflowRunStart:
    return WorkflowRunStart(
        run_id=run_id,
        workflow_id="workflow-recovery",
        document_id="document-recovery",
        workflow_name="异常恢复",
        document_snapshot={"nodes": []},
        layout_snapshot={},
        profile_id="profile-recovery",
        profile_snapshot={"browserVersion": "145.0.7632.109.2"},
        mode="run",
    )


def test_sidecar_startup_interrupts_orphaned_run_without_starting_worker(
    tmp_path: Path, monkeypatch
) -> None:
    paths = AppPaths.from_data_dir(tmp_path)
    migrate_database(paths.database)
    sessions = create_session_factory(paths.database)
    before_restart = WorkflowRunService(
        SqlAlchemyWorkflowRuns(sessions),
        clock=lambda: datetime(2026, 9, 16, tzinfo=UTC),
    )
    before_restart.start(_start("run-orphaned"))
    before_restart.mark_running("run-orphaned")
    sessions.dispose()
    worker_start = AsyncMock(side_effect=AssertionError("恢复不得重放 worker"))
    monkeypatch.setattr(
        "autoflow.bootstrap.workflows.WorkflowWorkerManager.start", worker_start
    )

    app = create_app(Settings(data_dir=str(tmp_path), instance_id="recovery-test"))
    with TestClient(app):
        runs = app.state.workflow_services.runs
        recovered = runs.get("run-orphaned")
        events = runs.events("run-orphaned", after_sequence=0, limit=20)

        assert recovered.status == "interrupted"
        assert recovered.cleanup_state == "completed"
        assert events[-1].type == "execution:interrupted"
        assert not any(event.type.startswith("execution:node") for event in events)
        assert worker_start.await_count == 0
        assert app.state.workflow_services.workers.busy() is False

        replacement = runs.start(_start("run-after-recovery"))
        assert replacement.status == "starting"
        runs.finish(
            replacement.run_id,
            status="stopped",
            cleanup_completed=True,
        )
