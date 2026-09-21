from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import DatabaseError

from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.domain.workflows.runs import WorkflowRunError, WorkflowRunStart
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_models import (
    WorkflowRunEventRow,
    WorkflowRunRow,
)
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns


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
    before_recovery = service.events("run-1", after_sequence=0, limit=20)

    recovered = service.recover_interrupted()

    assert [run.run_id for run in recovered] == ["run-1"]
    run = service.get("run-1")
    assert run.status == "interrupted"
    assert run.cleanup_state == "completed"
    assert run.finished_at is not None
    events = service.events("run-1", after_sequence=0, limit=20)
    assert events[:-1] == before_recovery
    assert events[-1].type == "execution:interrupted"
    assert not any(event.type.startswith("execution:node") for event in events)
    assert service.recover_interrupted() == ()
    assert service.events("run-1", after_sequence=0, limit=20) == events
    assert service.start(_start("run-2")).run_id == "run-2"


def test_recovery_interrupts_a_failed_pause_without_replaying_actions(
    service: WorkflowRunService,
) -> None:
    service.start(_start())
    service.mark_running("run-1")
    service._repository.append_event(
        "run-1",
        "execution:failed_paused",
        {"error": "列表为空", "pauseId": "pause-1"},
        now=datetime(2026, 9, 15, tzinfo=UTC),
        node_id="fail",
        run_patch={"status": "failed_paused", "currentNodeId": "fail", "error": {"code": "WORKFLOW_EXECUTION_FAILED", "message": "列表为空", "nodeId": "fail"}},
    )

    recovered = service.recover_interrupted()

    assert [run.run_id for run in recovered] == ["run-1"]
    assert service.get("run-1").status == "interrupted"
    assert service.events("run-1", after_sequence=0, limit=20)[-1].type == "execution:interrupted"


def test_recovery_does_not_reinterpret_retired_studio_payload(tmp_path: Path) -> None:
    database = tmp_path / "retired-run.sqlite3"
    migrate_database(database)
    repository = SqlAlchemyWorkflowRuns(create_session_factory(database))
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO workflow_runs VALUES (?, ?, ?, ?, ?, ?)",
            (
                "retired-run",
                "retired-workflow",
                "legacy-request",
                "2026-09-13",
                1,
                '{"state":"paused"}',
            ),
        )

    assert repository.recover_interrupted(now=datetime(2026, 9, 15, tzinfo=UTC)) == ()
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT active_slot, payload FROM workflow_runs WHERE id='retired-run'"
        ).fetchone() == (1, '{"state":"paused"}')

    created = WorkflowRunService(repository).start(_start("current-run"))
    assert created.status == "starting"


def test_debug_command_receipt_survives_repository_recreation(tmp_path: Path) -> None:
    database = tmp_path / "debug-command.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    repository = SqlAlchemyWorkflowRuns(sessions)
    WorkflowRunService(repository).start(_start())
    receipt = {
        "commandId": "debug-step-1",
        "runId": "run-1",
        "action": "step",
        "success": True,
        "error": None,
    }

    repository.save_debug_command(
        "run-1",
        "debug-step-1",
        request_hash="a" * 64,
        receipt=receipt,
        http_status=200,
    )

    assert SqlAlchemyWorkflowRuns(sessions).get_debug_command("debug-step-1") == (
        "a" * 64,
        receipt,
        200,
    )


def test_variable_tracking_pages_large_values_and_clears_finished_run(
    tmp_path: Path,
) -> None:
    database = tmp_path / "variable-tracking.sqlite3"
    migrate_database(database)
    repository = SqlAlchemyWorkflowRuns(create_session_factory(database))
    clock = datetime(2026, 9, 15, tzinfo=UTC)
    service = WorkflowRunService(repository, clock=lambda: clock)
    service.start(_start())
    large = "起" + "中" * 70_000 + "末尾可检索"
    for index in range(501):
        repository.append_event(
            "run-1",
            "execution:variable_changed",
            {
                "variable_name": "large" if index == 0 else "count",
                "old_value": None,
                "new_value": large if index == 0 else index,
                "node_name": "设置变量",
                "operation": "create" if index == 0 else "update",
                "value_type": "string" if index == 0 else "number",
            },
            now=clock,
            node_id="set",
            execution_id=f"execution-{index}",
        )

    first, total, next_cursor, through = service.variable_tracking(
        "run-1", limit=500
    )
    assert len(first) == 500
    assert total == 501
    assert next_cursor == 500
    assert through == 501
    second, _, final_cursor, _ = service.variable_tracking(
        "run-1", cursor=next_cursor, limit=500, through_sequence=through
    )
    assert len(second) == 1
    assert final_cursor is None
    filtered, filtered_total, _, _ = service.variable_tracking(
        "run-1", query="末尾可检索"
    )
    assert filtered_total == 1
    assert filtered[0]["new_value"] == large
    assert service.variable_tracking_value(
        "run-1", sequence=1, side="new_value"
    ) == large

    service.finish("run-1", status="completed", cleanup_completed=True)
    service.clear_variable_tracking("run-1")
    cleared, cleared_total, _, cleared_through = service.variable_tracking(
        "run-1", through_sequence=through
    )
    assert cleared == []
    assert cleared_total == 0
    assert cleared_through == through


def test_ten_thousand_persisted_logs_page_and_stream_at_a_fixed_cutoff(tmp_path: Path) -> None:
    database = tmp_path / "large-log-history.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    repository = SqlAlchemyWorkflowRuns(sessions)
    service = WorkflowRunService(repository, clock=lambda: datetime(2026, 9, 15, tzinfo=UTC))
    service.start(_start())
    with sessions() as session:
        for offset in range(0, 10_000, 1_000):
            session.execute(insert(WorkflowRunEventRow), [{
                "run_id": "run-1", "seq": index + 1,
                "payload": {
                    "type": "execution:log", "occurredAt": "2026-09-15T00:00:00+00:00",
                    "payload": {"id": f"log-{index + 1}", "level": "info", "message": f"调度-{index + 1:05d}"},
                    "nodeId": "body", "executionId": f"execution-{index + 1}",
                },
            } for index in range(offset, offset + 1_000)])
        run = session.get(WorkflowRunRow, "run-1")
        assert run is not None
        run.payload = {**run.payload, "eventCount": 10_000, "logCount": 10_000}
        session.commit()

    latest, total, next_cursor = service.logs("run-1", cursor=0, limit=100, query=None, levels=(), node_id=None)
    earliest, _, final_cursor = service.logs("run-1", cursor=9_900, limit=100, query=None, levels=(), node_id=None)
    cutoff = service.event_cutoff("run-1")
    repository.append_event(
        "run-1", "execution:log", {"id": "late", "level": "info", "message": "截止后日志"},
        now=datetime(2026, 9, 15, tzinfo=UTC), node_id="body", execution_id="execution-late",
    )
    streamed = list(service.iter_logs(
        "run-1", query=None, levels=(), node_id=None, through_sequence=cutoff,
    ))

    assert total == 10_000 and next_cursor == 100 and final_cursor is None
    assert [row["sequence"] for row in latest] == list(range(9_901, 10_001))
    assert [row["sequence"] for row in earliest] == list(range(1, 101))
    assert cutoff == 10_000 and service.event_cutoff("run-1") == 10_001
    assert len(streamed) == 10_000
    assert streamed[0]["id"] == "log-1" and streamed[-1]["id"] == "log-10000"
    with pytest.raises(WorkflowRunError) as invalid_filter:
        service.iter_logs("run-1", query=None, levels=("verbose",), node_id=None)
    assert invalid_filter.value.code == "RUN_LOG_FILTER_INVALID"


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
