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


@pytest.mark.asyncio
async def test_text_export_writes_relative_output_and_immutable_artifact_snapshot(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
) -> None:
    store, repository = artifacts
    writer = store.writer(
        run_id="run-artifacts",
        node_id="export",
        execution_id="execution-export-1",
        purpose="result",
    )

    result_path = await writer.write_text(
        output_path="reports/结果.txt",
        content="第一条\n第二条",
        separator="\n",
        encoding="utf-8",
        append=False,
        mime_type="text/plain",
    )

    target = Path(result_path)
    assert target == store._root / "runs/run-artifacts/outputs/reports/结果.txt"
    assert target.read_text(encoding="utf-8") == "第一条\n第二条"
    rows = repository.list_artifacts("run-artifacts", cursor=0, limit=20)
    assert len(rows) == 1
    snapshot = store._root / rows[0].relative_path
    assert snapshot != target
    assert snapshot.read_bytes() == target.read_bytes()
    assert rows[0].sha256 == hashlib.sha256(target.read_bytes()).hexdigest()
    assert rows[0].execution_id == "execution-export-1"

    target.write_text("外部修改", encoding="utf-8")
    assert snapshot.read_text(encoding="utf-8") == "第一条\n第二条"


@pytest.mark.asyncio
async def test_text_export_preserves_overwrite_append_and_utf8_sig_semantics(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
) -> None:
    store, repository = artifacts
    target = Path(store._root) / "runs/run-artifacts/outputs/export.txt"
    target.parent.mkdir(parents=True)
    target.write_text("旧内容", encoding="utf-8-sig")

    first = store.writer(
        run_id="run-artifacts",
        node_id="export",
        execution_id="execution-export-1",
        purpose="result",
    )
    await first.write_text(
        output_path="export.txt",
        content="新内容",
        separator="\n",
        encoding="utf-8-sig",
        append=False,
        mime_type="text/plain",
    )
    first_bytes = target.read_bytes()
    assert first_bytes.startswith(b"\xef\xbb\xbf")
    assert first_bytes.count(b"\xef\xbb\xbf") == 1

    second = store.writer(
        run_id="run-artifacts",
        node_id="export",
        execution_id="execution-export-2",
        purpose="result",
    )
    await second.write_text(
        output_path="export.txt",
        content="追加",
        separator="\r\n",
        encoding="utf-8-sig",
        append=True,
        mime_type="text/plain",
    )
    final_bytes = target.read_bytes()
    assert final_bytes.count(b"\xef\xbb\xbf") == 1
    assert final_bytes.decode("utf-8-sig") == "新内容\r\n追加"

    rows = repository.list_artifacts("run-artifacts", cursor=0, limit=20)
    assert len(rows) == 2
    assert (store._root / rows[0].relative_path).read_bytes() == first_bytes
    assert (store._root / rows[1].relative_path).read_bytes() == final_bytes


@pytest.mark.asyncio
async def test_text_export_empty_utf8_sig_content_still_writes_one_bom(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
) -> None:
    store, _ = artifacts
    writer = store.writer(
        run_id="run-artifacts",
        node_id="export",
        execution_id="execution-empty-export",
        purpose="result",
    )

    result_path = await writer.write_text(
        output_path="empty.txt",
        content="",
        separator="\n",
        encoding="utf-8-sig",
        append=False,
        mime_type="text/plain",
    )

    assert Path(result_path).read_bytes() == b"\xef\xbb\xbf"


@pytest.mark.asyncio
async def test_text_export_allows_explicit_absolute_target_and_rejects_relative_escape(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
    tmp_path: Path,
) -> None:
    store, repository = artifacts
    writer = store.writer(
        run_id="run-artifacts",
        node_id="export",
        execution_id="execution-export",
        purpose="result",
    )

    absolute = tmp_path / "custom" / "result.txt"
    result_path = await writer.write_text(
        output_path=str(absolute),
        content="自定义输出",
        separator=",",
        encoding="utf-8",
        append=False,
        mime_type="text/plain",
    )
    assert Path(result_path) == absolute.resolve()
    assert absolute.read_text(encoding="utf-8") == "自定义输出"

    with pytest.raises(WorkflowRunError) as escaped:
        await writer.write_text(
            output_path="../escape.txt",
            content="x",
            separator="\n",
            encoding="utf-8",
            append=False,
            mime_type="text/plain",
        )
    assert escaped.value.code == "ARTIFACT_PATH_INVALID"
    assert len(repository.list_artifacts("run-artifacts", cursor=0, limit=20)) == 1


@pytest.mark.asyncio
async def test_text_export_failure_keeps_existing_target_and_registers_nothing(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
) -> None:
    store, repository = artifacts
    target = store._root / "runs/run-artifacts/outputs/result.txt"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"existing")
    writer = store.writer(
        run_id="run-artifacts",
        node_id="export",
        execution_id="execution-export",
        purpose="result",
    )

    with pytest.raises(LookupError):
        await writer.write_text(
            output_path="result.txt",
            content="new",
            separator="\n",
            encoding="not-a-codec",
            append=False,
            mime_type="text/plain",
        )

    assert target.read_bytes() == b"existing"
    assert repository.list_artifacts("run-artifacts", cursor=0, limit=20) == ()
    assert not list(target.parent.glob(".*.tmp"))


@pytest.mark.asyncio
async def test_text_export_rejects_symlink_escape(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
    tmp_path: Path,
) -> None:
    store, _ = artifacts
    writer = store.writer(
        run_id="run-artifacts",
        node_id="export",
        execution_id="execution-export",
        purpose="result",
    )
    output_root = store._root / "runs/run-artifacts/outputs"
    output_root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (output_root / "linked").symlink_to(outside, target_is_directory=True)
    final_target = output_root / "final.txt"
    outside_file = outside / "outside.txt"
    outside_file.write_bytes(b"outside")
    final_target.symlink_to(outside_file)

    for output_path in ("linked/created/escape.txt", "final.txt"):
        with pytest.raises(WorkflowRunError) as caught:
            await writer.write_text(
                output_path=output_path,
                content="blocked",
                separator="\n",
                encoding="utf-8",
                append=False,
                mime_type="text/plain",
            )
        assert caught.value.code == "ARTIFACT_PATH_INVALID"
    assert outside_file.read_bytes() == b"outside"
    assert not (outside / "created").exists()


@pytest.mark.asyncio
async def test_text_export_parent_swap_cannot_escape_verified_directory(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, repository = artifacts
    output_parent = store._root / "runs/run-artifacts/outputs/verified"
    output_parent.mkdir(parents=True)
    outside = tmp_path / "outside-swap"
    outside.mkdir()
    original_open = store._open_output_parent

    def swap_after_open(run_id: str, output_path: str) -> tuple[Path, int | None]:
        target, directory_fd = original_open(run_id, output_path)
        detached = target.parent.with_name("verified-detached")
        target.parent.rename(detached)
        target.parent.symlink_to(outside, target_is_directory=True)
        return target, directory_fd

    monkeypatch.setattr(store, "_open_output_parent", swap_after_open)
    writer = store.writer(
        run_id="run-artifacts",
        node_id="export",
        execution_id="execution-swap",
        purpose="result",
    )

    with pytest.raises(WorkflowRunError) as caught:
        await writer.write_text(
            output_path="verified/result.txt",
            content="blocked",
            separator="\n",
            encoding="utf-8",
            append=False,
            mime_type="text/plain",
        )

    assert caught.value.code == "ARTIFACT_WRITE_CONFLICT"
    assert not (outside / "result.txt").exists()
    assert repository.list_artifacts("run-artifacts", cursor=0, limit=20) == ()


@pytest.mark.asyncio
async def test_text_export_refuses_unverified_windows_path_operations(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, repository = artifacts
    writer = store.writer(
        run_id="run-artifacts",
        node_id="export",
        execution_id="execution-windows",
        purpose="result",
    )
    monkeypatch.setattr(
        "autoflow.infrastructure.filesystem.workflow_artifacts.os.name", "nt"
    )

    with pytest.raises(WorkflowRunError) as caught:
        await writer.write_text(
            output_path="result.txt",
            content="blocked",
            separator="\n",
            encoding="utf-8",
            append=False,
            mime_type="text/plain",
        )

    assert caught.value.code == "ARTIFACT_PLATFORM_UNSUPPORTED"
    assert repository.list_artifacts("run-artifacts", cursor=0, limit=20) == ()


@pytest.mark.asyncio
async def test_text_export_cancellation_during_append_keeps_original_file(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
) -> None:
    store, repository = artifacts
    target = store._root / "runs/run-artifacts/outputs/large.txt"
    target.parent.mkdir(parents=True)
    original = b"x" * (3 * 1024 * 1024)
    target.write_bytes(original)

    class Cancellation:
        checks = 0

        @property
        def cancelled(self) -> bool:
            return self.checks >= 3

        def raise_if_cancelled(self) -> None:
            self.checks += 1
            if self.cancelled:
                raise RuntimeError("workflow execution stopped")

    writer = store.writer(
        run_id="run-artifacts",
        node_id="export",
        execution_id="execution-export",
        purpose="result",
        cancellation=Cancellation(),
    )

    with pytest.raises(RuntimeError, match="workflow execution stopped"):
        await writer.write_text(
            output_path="large.txt",
            content="new",
            separator="\n",
            encoding="utf-8",
            append=True,
            mime_type="text/plain",
        )

    assert target.read_bytes() == original
    assert repository.list_artifacts("run-artifacts", cursor=0, limit=20) == ()
    assert not list(target.parent.glob(".*.tmp"))


@pytest.mark.asyncio
async def test_text_export_cancellation_during_snapshot_publishes_nothing(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
) -> None:
    store, repository = artifacts

    class Cancellation:
        checks = 0

        @property
        def cancelled(self) -> bool:
            return self.checks >= 35

        def raise_if_cancelled(self) -> None:
            self.checks += 1
            if self.cancelled:
                raise RuntimeError("workflow execution stopped")

    writer = store.writer(
        run_id="run-artifacts",
        node_id="export",
        execution_id="execution-snapshot-cancel",
        purpose="result",
        cancellation=Cancellation(),
    )

    with pytest.raises(RuntimeError, match="workflow execution stopped"):
        await writer.write_text(
            output_path="snapshot-cancel.txt",
            content="x" * (2 * 1024 * 1024),
            separator="\n",
            encoding="utf-8",
            append=False,
            mime_type="text/plain",
        )

    run_root = store._root / "runs/run-artifacts"
    assert not (run_root / "outputs/snapshot-cancel.txt").exists()
    assert repository.list_artifacts("run-artifacts", cursor=0, limit=20) == ()
    assert not list(run_root.rglob(".*.tmp"))


@pytest.mark.asyncio
async def test_text_export_registration_failure_reports_failure_after_target_commit(
    tmp_path: Path,
) -> None:
    class FailedRepository:
        def register_artifact(self, **_values: object) -> WorkflowArtifact:
            raise RuntimeError("synthetic registration failure")

    root = tmp_path / "workspace"
    writer = WorkflowArtifactStore(root, FailedRepository()).writer(
        run_id="run-artifacts",
        node_id="export",
        execution_id="execution-export",
        purpose="result",
    )

    with pytest.raises(RuntimeError, match="synthetic registration failure"):
        await writer.write_text(
            output_path="result.txt",
            content="committed",
            separator="\n",
            encoding="utf-8",
            append=False,
            mime_type="text/plain",
        )

    target = root / "runs/run-artifacts/outputs/result.txt"
    assert target.read_text(encoding="utf-8") == "committed"
    assert not list((root / "runs/run-artifacts/artifacts").rglob("*.txt"))
