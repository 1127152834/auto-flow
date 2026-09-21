from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.infrastructure.database.workflow_models import (
    WorkflowRecordingSessionRow,
    WorkflowRunArtifactRow,
    WorkflowRunRow,
)


def _client(tmp_path: Path) -> TestClient:
    app = create_app(
        Settings(
            data_dir=str(tmp_path),
            instance_id="studio-retention",
            instance_token="renderer",
        )
    )
    return TestClient(app, headers={"x-autoflow-token": "renderer"})


def _run(run_id: str, started_at: datetime, *, active: bool = False) -> WorkflowRunRow:
    return WorkflowRunRow(
        id=run_id,
        workflow_id="workflow",
        request_hash=run_id,
        started_at=started_at.isoformat(),
        active_slot=2 if active else None,
        payload={"status": "running" if active else "succeeded"},
    )


def _artifact(
    run_id: str, artifact_id: str, relative_path: str, size: int
) -> WorkflowRunArtifactRow:
    return WorkflowRunArtifactRow(
        run_id=run_id,
        id=artifact_id,
        ordinal=1,
        node_id="node",
        execution_id=None,
        payload={
            "relativePath": relative_path,
            "size": size,
            "sha256": "0" * 64,
            "mimeType": "text/plain",
        },
        purpose="result",
        event_seq=1,
    )


def test_retention_config_persists_partial_updates(tmp_path: Path) -> None:
    client = _client(tmp_path)
    with client:
        loaded = client.get("/api/retention/config")
        assert loaded.status_code == 200
        assert loaded.json()["config"] == {
            "enabled": False,
            "recordings_max_days": 30,
            "recordings_max_total_mb": 0,
            "data_max_days": 30,
            "data_max_total_mb": 0,
            "cleanup_interval_hours": 24,
        }
        saved = client.post("/api/retention/config", json={"data_max_days": 9})
        assert saved.status_code == 200
        assert saved.json()["config"] == {
            **loaded.json()["config"],
            "data_max_days": 9,
        }

    with _client(tmp_path) as reopened:
        assert (
            reopened.get("/api/retention/config").json()["config"]["data_max_days"]
            == 9
        )
        before = reopened.get("/api/retention/config").json()["config"]
        assert reopened.post(
            "/api/retention/config", json={"cleanup_interval_hours": 0}
        ).status_code == 422
        assert reopened.get("/api/retention/config").json()["config"] == before


def test_cleanup_only_removes_registered_inactive_expired_data(tmp_path: Path) -> None:
    client = _client(tmp_path)
    app = client.app
    now = datetime.now(UTC)
    old = now - timedelta(days=10)
    workspace = app.state.paths.workspace
    old_file = workspace / "runs/run-old/artifacts/old.txt"
    active_file = workspace / "runs/run-active/artifacts/active.txt"
    unregistered = workspace / "runs/unregistered.txt"
    for path, content in (
        (old_file, b"old"),
        (active_file, b"active"),
        (unregistered, b"keep"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    with app.state.session_factory() as database:
        database.add_all(
            [
                WorkflowRecordingSessionRow(
                    id="recording-old",
                    status="stopped",
                    active_slot=None,
                    last_sequence=1,
                    byte_count=100,
                    created_at=old,
                    updated_at=old,
                ),
                WorkflowRecordingSessionRow(
                    id="recording-active",
                    status="recording",
                    active_slot=1,
                    last_sequence=1,
                    byte_count=100,
                    created_at=old,
                    updated_at=old,
                ),
                _run("run-old", old),
                _run("run-active", old, active=True),
            ]
        )
        database.commit()
        database.add_all(
            [
                _artifact(
                    "run-old",
                    "artifact-old",
                    "runs/run-old/artifacts/old.txt",
                    len(b"old"),
                ),
                _artifact(
                    "run-active",
                    "artifact-active",
                    "runs/run-active/artifacts/active.txt",
                    len(b"active"),
                ),
            ]
        )
        database.commit()

    with client:
        saved = client.post(
            "/api/retention/config",
            json={"recordings_max_days": 1, "data_max_days": 1},
        )
        assert saved.status_code == 200
        result = client.post("/api/retention/cleanup")
        assert result.status_code == 200
        assert result.json()["recordings"]["removed"] == 1
        assert result.json()["data"]["removed"] == 1
        usage = client.get("/api/retention/usage").json()["usage"]
        assert usage["recordings"]["count"] == 1
        assert usage["data"]["count"] == 1

    assert not old_file.exists()
    assert active_file.read_bytes() == b"active"
    assert unregistered.read_bytes() == b"keep"
    with app.state.session_factory() as database:
        assert database.get(WorkflowRecordingSessionRow, "recording-old") is None
        assert database.get(WorkflowRecordingSessionRow, "recording-active") is not None
        assert database.get(WorkflowRunArtifactRow, ("run-old", "artifact-old")) is None
        assert (
            database.get(WorkflowRunArtifactRow, ("run-active", "artifact-active"))
            is not None
        )


def test_size_limit_removes_oldest_registered_entries(tmp_path: Path) -> None:
    client = _client(tmp_path)
    app = client.app
    now = datetime.now(UTC)
    with app.state.session_factory() as database:
        database.add_all(
            [
                WorkflowRecordingSessionRow(
                    id="first",
                    status="stopped",
                    active_slot=None,
                    last_sequence=1,
                    byte_count=700_000,
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
                WorkflowRecordingSessionRow(
                    id="second",
                    status="stopped",
                    active_slot=None,
                    last_sequence=1,
                    byte_count=700_000,
                    created_at=now - timedelta(hours=1),
                    updated_at=now - timedelta(hours=1),
                ),
            ]
        )
        database.commit()

    with client:
        client.post(
            "/api/retention/config",
            json={"recordings_max_days": 0, "recordings_max_total_mb": 1},
        )
        result = client.post("/api/retention/cleanup").json()
        assert result["recordings"]["removed"] == 1

    with app.state.session_factory() as database:
        ids = database.scalars(select(WorkflowRecordingSessionRow.id)).all()
        assert ids == ["second"]


def test_cleanup_rejects_registered_path_outside_workspace_without_deleting_row(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    app = client.app
    old = datetime.now(UTC) - timedelta(days=10)
    outside = app.state.paths.workspace.parent / "outside.txt"
    outside.write_bytes(b"keep")
    with app.state.session_factory() as database:
        database.add(_run("run-invalid", old))
        database.commit()
        database.add(
            _artifact("run-invalid", "artifact-invalid", "../outside.txt", 4)
        )
        database.commit()

    with client:
        client.post("/api/retention/config", json={"data_max_days": 1})
        response = client.post("/api/retention/cleanup")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "RETENTION_ARTIFACT_PATH_INVALID"

    assert outside.read_bytes() == b"keep"
    with app.state.session_factory() as database:
        assert (
            database.get(
                WorkflowRunArtifactRow, ("run-invalid", "artifact-invalid")
            )
            is not None
        )


def test_corrupt_retention_config_is_reported_instead_of_using_cleanup_defaults(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    config = client.app.state.paths.workspace / "studio-retention.json"
    config.write_text('{"enabled":"yes"}', encoding="utf-8")
    with client:
        response = client.get("/api/retention/config")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "RETENTION_CONFIG_INVALID"
