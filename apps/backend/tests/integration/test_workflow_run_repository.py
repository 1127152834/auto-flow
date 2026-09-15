from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path

import pytest
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.domain.workflows.runs import WorkflowRunError, WorkflowRunStart
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
from sqlalchemy.exc import DatabaseError


def _start(run_id: str = "run-1", *, url: str = "https://example.test") -> WorkflowRunStart:
    return WorkflowRunStart(
        run_id=run_id,
        workflow_id="workflow-1",
        document_id="document-1",
        workflow_name="真实运行",
        document_snapshot={"nodes": [{"id": "open", "data": {"url": url}}]},
        layout_snapshot={"viewport": {"x": 0, "y": 0, "zoom": 1}},
        profile_id="profile-1",
        profile_snapshot={
            "browserVersion": "145.0.7632.109.2",
            "locale": "zh-CN",
            "proxy": {"server": "http://127.0.0.1:8080", "password": "不得保存"},
            "licenseKey": "不得保存",
        },
        mode="run",
    )


@pytest.fixture
def service(tmp_path: Path) -> WorkflowRunService:
    database = tmp_path / "runs.sqlite3"
    migrate_database(database)
    repository = SqlAlchemyWorkflowRuns(create_session_factory(database))
    ticks = count()
    return WorkflowRunService(
        repository,
        clock=lambda: datetime(2026, 9, 15, tzinfo=UTC)
        + timedelta(seconds=next(ticks)),
    )


def test_run_start_is_idempotent_and_active_slot_lasts_until_cleanup(
    service: WorkflowRunService,
) -> None:
    created = service.start(_start())
    repeated = service.start(_start())

    assert repeated == created
    assert created.status == "starting"
    assert created.cleanup_state == "pending"
    assert created.profile_snapshot == {
        "browserVersion": "145.0.7632.109.2",
        "locale": "zh-CN",
        "proxy": {"server": "http://127.0.0.1:8080"},
    }
    with pytest.raises(WorkflowRunError) as reused:
        service.start(_start(url="https://different.test"))
    assert reused.value.code == "RUN_ID_CONFLICT"
    with pytest.raises(WorkflowRunError) as busy:
        service.start(_start("run-2"))
    assert busy.value.code == "WORKFLOW_RUN_BUSY"

    service.mark_running("run-1")
    service.request_stop("run-1")
    with pytest.raises(WorkflowRunError) as premature:
        service.finish("run-1", status="stopped", cleanup_completed=False)
    assert premature.value.code == "RUN_CLEANUP_INCOMPLETE"
    with pytest.raises(WorkflowRunError):
        service.start(_start("run-2"))

    finished = service.finish("run-1", status="stopped", cleanup_completed=True)
    assert finished.status == "stopped"
    assert finished.cleanup_state == "completed"
    assert service.start(_start("run-2")).run_id == "run-2"


def test_recovery_interrupts_active_runs_without_replaying_actions(
    service: WorkflowRunService,
) -> None:
    service.start(_start())
    service.mark_running("run-1")

    recovered = service.recover_interrupted()

    assert [run.run_id for run in recovered] == ["run-1"]
    run = service.get("run-1")
    assert run.status == "interrupted"
    assert run.cleanup_state == "completed"
    assert run.finished_at is not None
    events = service.events("run-1", after_sequence=0, limit=20)
    assert events[-1].type == "execution:interrupted"
    assert service.start(_start("run-2")).run_id == "run-2"


def test_node_success_and_event_roll_back_in_one_transaction(tmp_path: Path) -> None:
    database = tmp_path / "atomic.sqlite3"
    migrate_database(database)
    repository = SqlAlchemyWorkflowRuns(create_session_factory(database))
    service = WorkflowRunService(
        repository, clock=lambda: datetime(2026, 9, 15, tzinfo=UTC)
    )
    service.start(_start())
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_run_event BEFORE INSERT ON workflow_run_events
            BEGIN SELECT RAISE(ABORT, 'synthetic event failure'); END
            """
        )

    with pytest.raises(DatabaseError):
        service.record_node_success(
            "run-1",
            node_id="open",
            execution_id="execution-1",
            result={"message": "完成"},
        )

    run = service.get("run-1")
    assert run.current_node_id is None
    assert run.event_count == 0
    assert service.events("run-1", after_sequence=0, limit=20) == ()


def test_node_success_associates_artifacts_in_the_same_transaction(
    tmp_path: Path,
) -> None:
    database = tmp_path / "artifacts-atomic.sqlite3"
    migrate_database(database)
    repository = SqlAlchemyWorkflowRuns(create_session_factory(database))
    service = WorkflowRunService(
        repository, clock=lambda: datetime(2026, 9, 15, tzinfo=UTC)
    )
    service.start(_start())
    artifact = repository.register_artifact(
        run_id="run-1",
        artifact_id="artifact-1",
        node_id="shot",
        execution_id="execution-1",
        relative_path="runs/run-1/artifacts/shot.png",
        size=8,
        sha256="a" * 64,
        mime_type="image/png",
        purpose="result",
    )
    assert artifact.event_sequence == 0

    event = service.record_node_success(
        "run-1",
        node_id="shot",
        execution_id="execution-1",
        result={"path": "shot.png"},
        artifact_ids=("artifact-1",),
    )

    rows = repository.list_artifacts("run-1", cursor=0, limit=20)
    assert rows[0].event_sequence == event.sequence
