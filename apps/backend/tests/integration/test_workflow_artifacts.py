from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.domain.workflows.runs import (
    WorkflowArtifact,
    WorkflowRunError,
    WorkflowRunStart,
)
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
from autoflow.infrastructure.filesystem.workflow_artifacts import WorkflowArtifactStore


def _start() -> WorkflowRunStart:
    return WorkflowRunStart(
        run_id="run-artifacts",
        workflow_id="workflow",
        document_id="document",
        workflow_name="产物流程",
        document_snapshot={"nodes": []},
        layout_snapshot={},
        profile_id="profile",
        profile_snapshot={},
        mode="run",
    )


@pytest.fixture
def artifacts(tmp_path: Path) -> tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns]:
    database = tmp_path / "artifacts.sqlite3"
    migrate_database(database)
    repository = SqlAlchemyWorkflowRuns(create_session_factory(database))
    WorkflowRunService(
        repository, clock=lambda: datetime(2026, 9, 15, tzinfo=UTC)
    ).start(_start())
    return WorkflowArtifactStore(tmp_path / "workspace", repository), repository


@pytest.mark.asyncio
async def test_artifact_is_atomically_written_hashed_and_registered(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
) -> None:
    store, repository = artifacts
    content = b"\x89PNG\r\n\x1a\n" + b"x" * 70_000
    writer = store.writer(
        run_id="run-artifacts",
        node_id="shot",
        execution_id="execution-1",
        purpose="result",
    )

    result_path = await writer.write_bytes(
        name="screenshots/结果.png", content=content, mime_type="image/png"
    )

    target = Path(result_path)
    assert target.read_bytes() == content
    assert not list(target.parent.glob(".*.tmp"))
    rows = repository.list_artifacts("run-artifacts", cursor=0, limit=20)
    assert len(rows) == 1
    assert rows[0].relative_path == "runs/run-artifacts/artifacts/screenshots/结果.png"
    assert rows[0].size == len(content)
    assert rows[0].sha256 == hashlib.sha256(content).hexdigest()
    assert rows[0].mime_type == "image/png"
    assert rows[0].purpose == "result"
    assert rows[0].event_sequence == 0


@pytest.mark.asyncio
async def test_artifact_rejects_escape_and_explicit_overwrite(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
) -> None:
    store, _ = artifacts
    writer = store.writer(
        run_id="run-artifacts",
        node_id="shot",
        execution_id="execution-1",
        purpose="result",
    )
    with pytest.raises(WorkflowRunError) as escaped:
        await writer.write_bytes(name="../escape.png", content=b"x", mime_type="image/png")
    assert escaped.value.code == "ARTIFACT_PATH_INVALID"

    await writer.write_bytes(name="same.png", content=b"first", mime_type="image/png")
    with pytest.raises(WorkflowRunError) as duplicate:
        await writer.write_bytes(name="same.png", content=b"second", mime_type="image/png")
    assert duplicate.value.code == "ARTIFACT_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_registration_failure_removes_unowned_file(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
    tmp_path: Path,
) -> None:
    _, repository = artifacts

    class FailedRepository:
        def register_artifact(
            self,
            *,
            run_id: str,
            artifact_id: str,
            node_id: str,
            execution_id: str | None,
            relative_path: str,
            size: int,
            sha256: str,
            mime_type: str,
            purpose: str,
        ) -> WorkflowArtifact:
            raise RuntimeError("synthetic registration failure")

    store = WorkflowArtifactStore(tmp_path / "failed-workspace", FailedRepository())
    writer = store.writer(
        run_id="run-artifacts",
        node_id="shot",
        execution_id="execution-1",
        purpose="result",
    )
    with pytest.raises(RuntimeError, match="synthetic registration failure"):
        await writer.write_bytes(name="orphan.png", content=b"bytes", mime_type="image/png")

    assert not (tmp_path / "failed-workspace" / "runs" / "run-artifacts").exists()
    assert repository.list_artifacts("run-artifacts", cursor=0, limit=20) == ()


@pytest.mark.asyncio
async def test_disk_failure_does_not_register_artifact(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
    tmp_path: Path,
) -> None:
    _, repository = artifacts
    invalid_root = tmp_path / "not-a-directory"
    invalid_root.write_bytes(b"occupied")
    writer = WorkflowArtifactStore(invalid_root, repository).writer(
        run_id="run-artifacts",
        node_id="shot",
        execution_id="execution-2",
        purpose="result",
    )

    with pytest.raises(OSError):
        await writer.write_bytes(name="failed.png", content=b"png", mime_type="image/png")

    assert repository.list_artifacts("run-artifacts", cursor=0, limit=20) == ()
