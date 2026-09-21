from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from autoflow.infrastructure.database import session as database_session
from autoflow.infrastructure.database import workflow_recordings
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_models import WorkflowRecordingSessionRow
from autoflow.infrastructure.database.workflow_recordings import (
    MAX_RECORDING_BYTES,
    MAX_RECORDING_EVENTS,
    MAX_RECORDING_VALUE_BYTES,
    SqlAlchemyWorkflowRecordings,
)


def test_recording_events_are_durable_ordered_and_non_destructive(tmp_path) -> None:
    database = tmp_path / "workspace.db"
    migrate_database(database)
    first = create_session_factory(database)
    recordings = SqlAlchemyWorkflowRecordings(first)
    now = datetime.now(UTC)

    assert recordings.start("record-1", now=now) == {
        "sessionId": "record-1",
        "recording": True,
        "nextSeq": 0,
    }
    appended = recordings.append(
        "record-1",
        [
            {"type": "input", "selector": "#name", "value": "中文"},
            {"type": "click", "selector": "#submit"},
        ],
        now=now,
    )
    assert [item["sequence"] for item in appended] == [1, 2]
    assert recordings.events("record-1", after_seq=0, limit=1) == {
        "sessionId": "record-1",
        "nextSeq": 1,
        "hasMore": True,
        "data": [appended[0]],
    }
    assert recordings.events("record-1", after_seq=0, limit=10)["data"] == appended
    assert recordings.events("record-1", after_seq=2, limit=10)["data"] == []
    recordings.stop("record-1", now=now)
    first.dispose()

    second = create_session_factory(database)
    restored = SqlAlchemyWorkflowRecordings(second)
    assert restored.status("record-1") == {
        "sessionId": "record-1",
        "recording": False,
        "nextSeq": 2,
    }
    assert restored.events("record-1", after_seq=0, limit=10)["data"] == appended
    second.dispose()


def test_recording_command_migration_preserves_existing_sessions(tmp_path) -> None:
    database = tmp_path / "recording-command-upgrade.db"
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    command.upgrade(config, "0018_scheduled_tasks")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO workflow_recording_sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("kept", "stopped", None, 0, 0, "2026-09-21", "2026-09-21"),
        )
    migrate_database(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("0019_recording_commands",)
        assert connection.execute(
            "SELECT id, status FROM workflow_recording_sessions"
        ).fetchone() == ("kept", "stopped")
        assert "workflow_recording_commands" in {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }


def test_recording_session_and_review_revisions_reject_conflicts(tmp_path) -> None:
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    recordings = SqlAlchemyWorkflowRecordings(factory)
    now = datetime.now(UTC)
    recordings.start("record-1", now=now)
    recordings.stop("record-1", now=now)

    with pytest.raises(ValueError, match="录制会话已结束"):
        recordings.start("record-1", now=now)

    saved = recordings.save_review(
        "document-1",
        expected_revision=0,
        auto_wait=True,
        events=[{"sequence": 1, "type": "navigate", "url": "https://example.test"}],
        now=now,
    )
    assert saved == {
        "documentId": "document-1",
        "revision": 1,
        "autoWait": True,
        "events": [
            {"sequence": 1, "type": "navigate", "url": "https://example.test"}
        ],
    }
    assert recordings.read_review("document-1") == saved
    with pytest.raises(ValueError, match="审查已修改"):
        recordings.save_review(
            "document-1",
            expected_revision=0,
            auto_wait=False,
            events=[],
            now=now,
        )
    factory.dispose()


def test_recording_recovery_marks_orphan_active_session_interrupted(tmp_path) -> None:
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    recordings = SqlAlchemyWorkflowRecordings(factory)
    now = datetime.now(UTC)
    recordings.start("orphan", now=now)
    recordings.begin_command(
        "pending-command",
        session_id="orphan",
        action="pause",
        request_hash="b" * 64,
        now=now,
    )

    assert recordings.recover_active(now=now) == 1
    assert recordings.status("orphan")["recording"] is False
    assert recordings.start("next", now=now)["recording"] is True
    interrupted = recordings.command("pending-command")
    assert interrupted is not None
    assert interrupted["status"] == "failed"
    assert interrupted["payload"]["code"] == "RECORDING_COMMAND_INTERRUPTED"
    factory.dispose()


def test_recording_command_claim_and_result_survive_restart(tmp_path) -> None:
    database = tmp_path / "workspace.db"
    migrate_database(database)
    first = create_session_factory(database)
    recordings = SqlAlchemyWorkflowRecordings(first)
    now = datetime.now(UTC)
    assert recordings.begin_command(
        "command-1",
        session_id="record-1",
        action="start",
        request_hash="a" * 64,
        now=now,
    ) is None
    pending = recordings.command("command-1")
    assert pending is not None and pending["status"] == "pending"
    recordings.finish_command(
        "command-1",
        status="completed",
        payload={"success": True, "commandId": "command-1"},
        http_status=200,
        now=now,
    )
    first.dispose()

    second = create_session_factory(database)
    restored = SqlAlchemyWorkflowRecordings(second)
    command = restored.command("command-1")
    assert command is not None
    assert command["payload"] == {"success": True, "commandId": "command-1"}
    assert restored.begin_command(
        "command-1",
        session_id="record-1",
        action="start",
        request_hash="a" * 64,
        now=now,
    ) == command
    second.dispose()


def test_recording_worker_exit_marks_session_interrupted(tmp_path) -> None:
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    recordings = SqlAlchemyWorkflowRecordings(factory)
    now = datetime.now(UTC)
    recordings.start("crashed", now=now)
    recordings.append("crashed", [{"type": "click", "selector": "#kept"}], now=now)

    recordings.interrupt("crashed", now=now)

    with factory() as session:
        row = session.get(WorkflowRecordingSessionRow, "crashed")
        assert row is not None
        assert row.status == "interrupted"
        assert row.active_slot is None
    assert recordings.events("crashed", after_seq=0)["data"][0]["selector"] == "#kept"
    assert recordings.start("next", now=now)["recording"] is True
    factory.dispose()


def test_recording_capacity_rejects_the_whole_unconfirmed_batch(tmp_path) -> None:
    assert MAX_RECORDING_EVENTS == 10_000
    assert MAX_RECORDING_BYTES == 64 * 1024 * 1024
    assert MAX_RECORDING_VALUE_BYTES == 1024 * 1024
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    recordings = SqlAlchemyWorkflowRecordings(factory)
    now = datetime.now(UTC)
    recordings.start("limited", now=now)

    with pytest.raises(ValueError, match="单值超过 1 MiB"):
        recordings.append(
            "limited",
            [{"type": "input", "value": "字" * (MAX_RECORDING_VALUE_BYTES + 1)}],
            now=now,
        )
    assert recordings.events("limited", after_seq=0)["data"] == []
    factory.dispose()


def test_recording_never_persists_a_captured_password_value(tmp_path) -> None:
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    recordings = SqlAlchemyWorkflowRecordings(factory)
    now = datetime.now(UTC)
    recordings.start("password", now=now)

    saved = recordings.append(
        "password",
        [
            {
                "type": "input",
                "selector": "#password",
                "value": "raw-secret",
                "sensitive": True,
            }
        ],
        now=now,
    )
    assert saved == [
        {
            "sequence": 1,
            "type": "input",
            "selector": "#password",
            "value": "",
            "sensitive": True,
            "needsValue": True,
        }
    ]
    with pytest.raises(ValueError, match="不支持的录制事件"):
        recordings.append("password", [{"type": "unknown"}], now=now)
    factory.dispose()


def test_recording_review_enforces_the_same_count_limit(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(workflow_recordings, "MAX_RECORDING_EVENTS", 1)
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    recordings = SqlAlchemyWorkflowRecordings(factory)

    with pytest.raises(ValueError, match="10000 条上限"):
        recordings.save_review(
            "too-many",
            expected_revision=0,
            auto_wait=True,
            events=[
                {"sequence": 1, "type": "click"},
                {"sequence": 2, "type": "click"},
            ],
            now=datetime.now(UTC),
        )
    assert recordings.read_review("too-many") is None
    factory.dispose()
