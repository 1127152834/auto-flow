from __future__ import annotations

import asyncio
import hashlib
import os
import threading
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
async def test_binary_artifact_cancellation_after_write_removes_unowned_file(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
) -> None:
    store, repository = artifacts

    class Cancellation:
        checks = 0

        @property
        def cancelled(self) -> bool:
            return self.checks >= 2

        def raise_if_cancelled(self) -> None:
            self.checks += 1
            if self.cancelled:
                raise RuntimeError("workflow execution stopped")

    writer = store.writer(
        run_id="run-artifacts",
        node_id="shot",
        execution_id="execution-cancelled",
        purpose="result",
        cancellation=Cancellation(),
    )

    with pytest.raises(RuntimeError, match="workflow execution stopped"):
        await writer.write_bytes(
            name="cancelled.png", content=b"image", mime_type="image/png"
        )

    assert not (
        store._root / "runs/run-artifacts/artifacts/cancelled.png"
    ).exists()
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
async def test_binary_export_writes_relative_output_and_xlsx_snapshot(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
) -> None:
    store, repository = artifacts
    writer = store.writer(
        run_id="run-artifacts",
        node_id="table-export",
        execution_id="execution-xlsx",
        purpose="result",
    )
    content = b"PK\x03\x04synthetic-xlsx"

    result_path = await writer.write_binary_output(
        output_path="reports/结果.xlsx",
        content=content,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    target = Path(result_path)
    assert target == store._root / "runs/run-artifacts/outputs/reports/结果.xlsx"
    assert target.read_bytes() == content
    rows = repository.list_artifacts("run-artifacts", cursor=0, limit=20)
    assert len(rows) == 1
    snapshot = store._root / rows[0].relative_path
    assert snapshot.suffix == ".xlsx"
    assert snapshot != target
    assert snapshot.read_bytes() == content
    assert rows[0].sha256 == hashlib.sha256(content).hexdigest()
    assert rows[0].size == len(content)
    snapshot = await writer.read_binary_output(
        output_path="reports/结果.xlsx", max_bytes=1024 * 1024
    )
    assert snapshot.content == content
    assert snapshot.identity != "missing"


@pytest.mark.asyncio
async def test_binary_export_failure_keeps_existing_target_and_registers_nothing(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, repository = artifacts
    target = store._root / "runs/run-artifacts/outputs/result.xlsx"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"existing")
    writer = store.writer(
        run_id="run-artifacts",
        node_id="table-export",
        execution_id="execution-xlsx",
        purpose="result",
    )

    def fail_replace(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(
        "autoflow.infrastructure.filesystem.workflow_artifacts.os.replace",
        fail_replace,
    )

    with pytest.raises(OSError, match="disk full"):
        await writer.write_binary_output(
            output_path="result.xlsx",
            content=b"replacement",
            mime_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

    assert target.read_bytes() == b"existing"
    assert repository.list_artifacts("run-artifacts", cursor=0, limit=20) == ()
    assert not list(target.parent.glob(".*.tmp"))


@pytest.mark.asyncio
async def test_binary_export_rejects_path_escape_and_symlink(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
    tmp_path: Path,
) -> None:
    store, repository = artifacts
    writer = store.writer(
        run_id="run-artifacts",
        node_id="table-export",
        execution_id="execution-xlsx",
        purpose="result",
    )
    output_root = store._root / "runs/run-artifacts/outputs"
    output_root.mkdir(parents=True)
    outside = tmp_path / "outside-xlsx"
    outside.mkdir()
    (output_root / "linked").symlink_to(outside, target_is_directory=True)

    for output_path in ("../escape.xlsx", "linked/escape.xlsx"):
        with pytest.raises(WorkflowRunError) as caught:
            await writer.write_binary_output(
                output_path=output_path,
                content=b"blocked",
                mime_type=(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
            )
        assert caught.value.code == "ARTIFACT_PATH_INVALID"

    assert not (outside / "escape.xlsx").exists()
    assert repository.list_artifacts("run-artifacts", cursor=0, limit=20) == ()


@pytest.mark.asyncio
async def test_binary_export_cancellation_keeps_existing_target(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
) -> None:
    store, repository = artifacts
    target = store._root / "runs/run-artifacts/outputs/result.xlsx"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"existing")

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
        node_id="table-export",
        execution_id="execution-xlsx",
        purpose="result",
        cancellation=Cancellation(),
    )

    with pytest.raises(RuntimeError, match="workflow execution stopped"):
        await writer.write_binary_output(
            output_path="result.xlsx",
            content=b"x" * (3 * 1024 * 1024),
            mime_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

    assert target.read_bytes() == b"existing"
    assert repository.list_artifacts("run-artifacts", cursor=0, limit=20) == ()
    assert not list(target.parent.glob(".*.tmp"))


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
async def test_limited_text_append_rejects_oversize_before_replacing_output(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
) -> None:
    store, repository = artifacts
    writer = store.writer(
        run_id="run-artifacts", node_id="export", execution_id="limited",
        purpose="result", max_bytes=3,
    )
    target = Path(await writer.write_text(
        output_path="limited.txt", content="abc", separator="", encoding="utf-8",
        append=False, mime_type="text/plain",
    ))
    with pytest.raises(WorkflowRunError) as error:
        await writer.write_text(
            output_path="limited.txt", content="d", separator="", encoding="utf-8",
            append=True, mime_type="text/plain",
        )
    assert error.value.code == "ARTIFACT_TOO_LARGE"
    assert target.read_text() == "abc"
    assert len(repository.list_artifacts("run-artifacts", cursor=0, limit=20)) == 1


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
async def test_text_export_registration_failure_restores_existing_target(
    tmp_path: Path,
) -> None:
    class FailedRepository:
        def register_artifact(self, **_values: object) -> WorkflowArtifact:
            raise RuntimeError("synthetic registration failure")

    root = tmp_path / "workspace"
    target = root / "runs/run-artifacts/outputs/result.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("existing", encoding="utf-8")
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

    assert target.read_text(encoding="utf-8") == "existing"
    assert not list((root / "runs/run-artifacts/artifacts").rglob("*.txt"))
    assert not list(target.parent.glob(".*.bak"))


@pytest.mark.asyncio
async def test_binary_export_registration_failure_restores_existing_target(
    tmp_path: Path,
) -> None:
    class FailedRepository:
        def register_artifact(self, **_values: object) -> WorkflowArtifact:
            raise RuntimeError("synthetic registration failure")

    root = tmp_path / "workspace"
    target = root / "runs/run-artifacts/outputs/result.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"existing")
    writer = WorkflowArtifactStore(root, FailedRepository()).writer(
        run_id="run-artifacts",
        node_id="table-export",
        execution_id="execution-xlsx",
        purpose="result",
    )

    with pytest.raises(RuntimeError, match="synthetic registration failure"):
        await writer.write_binary_output(
            output_path="result.xlsx",
            content=b"replacement",
            mime_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

    assert target.read_bytes() == b"existing"
    assert not list((root / "runs/run-artifacts/artifacts").rglob("*.xlsx"))
    assert not list(target.parent.glob(".*.bak"))


@pytest.mark.asyncio
async def test_binary_export_rejects_concurrent_change_after_read(
    artifacts: tuple[WorkflowArtifactStore, SqlAlchemyWorkflowRuns],
) -> None:
    store, repository = artifacts
    writer = store.writer(
        run_id="run-artifacts",
        node_id="table-export",
        execution_id="execution-xlsx",
        purpose="result",
    )
    target = store._root / "runs/run-artifacts/outputs/result.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"original")
    snapshot = await writer.read_binary_output(
        output_path="result.xlsx", max_bytes=1024
    )
    target.write_bytes(b"concurrent")

    with pytest.raises(WorkflowRunError) as caught:
        await writer.write_binary_output(
            output_path="result.xlsx",
            content=b"replacement",
            mime_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            expected_identity=snapshot.identity,
        )

    assert caught.value.code == "ARTIFACT_WRITE_CONFLICT"
    assert target.read_bytes() == b"concurrent"
    assert repository.list_artifacts("run-artifacts", cursor=0, limit=20) == ()


@pytest.mark.asyncio
async def test_binary_export_serializes_competing_autoflow_writers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Repository:
        def register_artifact(self, **_values: object) -> WorkflowArtifact:
            return object()  # type: ignore[return-value]

    root = tmp_path / "workspace"
    store = WorkflowArtifactStore(root, Repository())
    first_writer = store.writer(
        run_id="run-artifacts",
        node_id="first",
        execution_id="execution-first",
        purpose="result",
    )
    second_writer = store.writer(
        run_id="run-artifacts",
        node_id="second",
        execution_id="execution-second",
        purpose="result",
    )
    target = root / "runs/run-artifacts/outputs/result.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"original")
    snapshot = await first_writer.read_binary_output(
        output_path="result.xlsx", max_bytes=1024
    )
    first_publish_started = threading.Event()
    allow_first_publish = threading.Event()
    original_replace = os.replace

    def pause_first_publish(*args: object, **kwargs: object) -> None:
        source = str(args[0]) if args else ""
        destination = str(args[1]) if len(args) > 1 else ""
        if (
            destination == target.name
            and source.endswith(".tmp")
            and not first_publish_started.is_set()
        ):
            first_publish_started.set()
            assert allow_first_publish.wait(timeout=2)
        original_replace(*args, **kwargs)

    monkeypatch.setattr(
        "autoflow.infrastructure.filesystem.workflow_artifacts.os.replace",
        pause_first_publish,
    )
    first = asyncio.create_task(
        first_writer.write_binary_output(
            output_path="result.xlsx",
            content=b"first",
            mime_type="application/octet-stream",
            expected_identity=snapshot.identity,
        )
    )
    assert await asyncio.to_thread(first_publish_started.wait, 2)
    second = asyncio.create_task(
        second_writer.write_binary_output(
            output_path="result.xlsx",
            content=b"second",
            mime_type="application/octet-stream",
            expected_identity=snapshot.identity,
        )
    )
    await asyncio.sleep(0.05)
    assert not second.done()
    allow_first_publish.set()

    await first
    with pytest.raises(WorkflowRunError) as caught:
        await second

    assert caught.value.code == "ARTIFACT_WRITE_CONFLICT"
    assert target.read_bytes() == b"first"


@pytest.mark.asyncio
async def test_registration_failure_does_not_overwrite_newer_external_output(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    target = root / "runs/run-artifacts/outputs/result.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"original")

    class FailedRepository:
        def register_artifact(self, **_values: object) -> WorkflowArtifact:
            target.write_bytes(b"concurrent-after-publish")
            raise RuntimeError("synthetic registration failure")

    writer = WorkflowArtifactStore(root, FailedRepository()).writer(
        run_id="run-artifacts",
        node_id="table-export",
        execution_id="execution-xlsx",
        purpose="result",
    )

    with pytest.raises(WorkflowRunError) as caught:
        await writer.write_binary_output(
            output_path="result.xlsx",
            content=b"replacement",
            mime_type="application/octet-stream",
        )

    assert caught.value.code == "ARTIFACT_ROLLBACK_FAILED"
    assert "责任记录" in caught.value.message
    assert target.read_bytes() == b"concurrent-after-publish"
    assert len(list((root / "maintenance/workflow-output-backups").glob("*.pending"))) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("binary", [False, True])
async def test_publish_identity_comes_from_staged_file_before_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    binary: bool,
) -> None:
    class FailedRepository:
        def register_artifact(self, **_values: object) -> WorkflowArtifact:
            raise RuntimeError("synthetic registration failure")

    root = tmp_path / "workspace"
    suffix = "xlsx" if binary else "txt"
    target = root / f"runs/run-artifacts/outputs/result.{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"original")
    writer = WorkflowArtifactStore(root, FailedRepository()).writer(
        run_id="run-artifacts",
        node_id="export",
        execution_id="execution-export",
        purpose="result",
    )
    original_replace = os.replace
    injected = False

    def write_after_publication(*args: object, **kwargs: object) -> None:
        nonlocal injected
        original_replace(*args, **kwargs)
        source = str(args[0]) if args else ""
        destination = str(args[1]) if len(args) > 1 else ""
        if not injected and source.endswith(".tmp") and destination == target.name:
            injected = True
            target.write_bytes(b"concurrent-between-replace-and-stat")

    monkeypatch.setattr(
        "autoflow.infrastructure.filesystem.workflow_artifacts.os.replace",
        write_after_publication,
    )

    with pytest.raises(WorkflowRunError) as caught:
        if binary:
            await writer.write_binary_output(
                output_path=f"result.{suffix}",
                content=b"replacement",
                mime_type="application/octet-stream",
            )
        else:
            await writer.write_text(
                output_path=f"result.{suffix}",
                content="replacement",
                separator="\n",
                encoding="utf-8",
                append=False,
                mime_type="text/plain",
            )

    assert caught.value.code == "ARTIFACT_ROLLBACK_FAILED"
    assert "责任记录" in caught.value.message
    assert target.read_bytes() == b"concurrent-between-replace-and-stat"


@pytest.mark.asyncio
@pytest.mark.parametrize("binary", [False, True])
async def test_output_publish_fsync_failure_restores_existing_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    binary: bool,
) -> None:
    class Repository:
        def register_artifact(self, **_values: object) -> WorkflowArtifact:
            raise AssertionError("failed publish must not register an artifact")

    root = tmp_path / "workspace"
    suffix = "xlsx" if binary else "txt"
    target = root / f"runs/run-artifacts/outputs/result.{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"existing")
    writer = WorkflowArtifactStore(root, Repository()).writer(
        run_id="run-artifacts",
        node_id="export",
        execution_id="execution-export",
        purpose="result",
    )
    original_replace = os.replace
    original_fsync = os.fsync
    replaced = False
    failed = False

    def track_replace(*args: object, **kwargs: object) -> None:
        nonlocal replaced
        original_replace(*args, **kwargs)
        replaced = True

    def fail_first_post_replace_fsync(fd: int) -> None:
        nonlocal failed
        if replaced and not failed:
            failed = True
            raise OSError("synthetic directory fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(
        "autoflow.infrastructure.filesystem.workflow_artifacts.os.replace",
        track_replace,
    )
    monkeypatch.setattr(
        "autoflow.infrastructure.filesystem.workflow_artifacts.os.fsync",
        fail_first_post_replace_fsync,
    )

    with pytest.raises(OSError, match="synthetic directory fsync failure"):
        if binary:
            await writer.write_binary_output(
                output_path=f"result.{suffix}",
                content=b"replacement",
                mime_type="application/octet-stream",
            )
        else:
            await writer.write_text(
                output_path=f"result.{suffix}",
                content="replacement",
                separator="\n",
                encoding="utf-8",
                append=False,
                mime_type="text/plain",
            )

    assert target.read_bytes() == b"existing"
    assert not list(target.parent.glob(".*.bak"))


@pytest.mark.asyncio
async def test_backup_cleanup_failure_is_persisted_and_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Repository:
        def __init__(self) -> None:
            self.calls = 0

        def register_artifact(self, **_values: object) -> WorkflowArtifact:
            self.calls += 1
            return object()  # type: ignore[return-value]

    repository = Repository()
    root = tmp_path / "workspace"
    store = WorkflowArtifactStore(root, repository)
    target = root / "runs/run-artifacts/outputs/result.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"existing")
    writer = store.writer(
        run_id="run-artifacts",
        node_id="table-export",
        execution_id="execution-xlsx",
        purpose="result",
    )
    original_unlink = os.unlink

    def fail_backup_unlink(path: object, *args: object, **kwargs: object) -> None:
        if str(path).endswith(".cleanup"):
            raise OSError("synthetic backup cleanup failure")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(
        "autoflow.infrastructure.filesystem.workflow_artifacts.os.unlink",
        fail_backup_unlink,
    )

    with pytest.raises(WorkflowRunError) as caught:
        await writer.write_binary_output(
            output_path="result.xlsx",
            content=b"replacement",
            mime_type="application/octet-stream",
        )

    assert caught.value.code == "ARTIFACT_CLEANUP_FAILED"
    assert "责任记录" in caught.value.message
    assert repository.calls == 1
    assert target.read_bytes() == b"replacement"
    cleanup_root = root / "maintenance/workflow-output-backups"
    assert len(list(cleanup_root.glob("*.cleanup"))) == 1

    monkeypatch.undo()
    WorkflowArtifactStore(root, repository)

    assert not list(cleanup_root.glob("*.cleanup"))


@pytest.mark.asyncio
async def test_backup_cleanup_rename_failure_falls_back_to_direct_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Repository:
        def register_artifact(self, **_values: object) -> WorkflowArtifact:
            return object()  # type: ignore[return-value]

    root = tmp_path / "workspace"
    store = WorkflowArtifactStore(root, Repository())
    target = root / "runs/run-artifacts/outputs/result.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"existing")
    writer = store.writer(
        run_id="run-artifacts",
        node_id="table-export",
        execution_id="execution-xlsx",
        purpose="result",
    )
    original_replace = os.replace

    def fail_pending_transition(*args: object, **kwargs: object) -> None:
        source = str(args[0]) if args else ""
        destination = str(args[1]) if len(args) > 1 else ""
        if source.endswith(".pending") and destination.endswith(".cleanup"):
            raise OSError("synthetic cleanup transition failure")
        original_replace(*args, **kwargs)

    monkeypatch.setattr(
        "autoflow.infrastructure.filesystem.workflow_artifacts.os.replace",
        fail_pending_transition,
    )

    result = await writer.write_binary_output(
        output_path="result.xlsx",
        content=b"replacement",
        mime_type="application/octet-stream",
    )

    assert Path(result).read_bytes() == b"replacement"
    cleanup_root = root / "maintenance/workflow-output-backups"
    assert not list(cleanup_root.iterdir())


@pytest.mark.asyncio
async def test_backup_cleanup_transition_and_unlink_failure_records_retry_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Repository:
        def register_artifact(self, **_values: object) -> WorkflowArtifact:
            return object()  # type: ignore[return-value]

    root = tmp_path / "workspace"
    store = WorkflowArtifactStore(root, Repository())
    target = root / "runs/run-artifacts/outputs/result.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"existing")
    writer = store.writer(
        run_id="run-artifacts",
        node_id="table-export",
        execution_id="execution-xlsx",
        purpose="result",
    )
    original_replace = os.replace
    original_path_unlink = Path.unlink

    def fail_pending_transition(*args: object, **kwargs: object) -> None:
        source = str(args[0]) if args else ""
        destination = str(args[1]) if len(args) > 1 else ""
        if source.endswith(".pending") and destination.endswith(".cleanup"):
            raise OSError("synthetic cleanup transition failure")
        original_replace(*args, **kwargs)

    def fail_pending_unlink(
        path: Path, missing_ok: bool = False
    ) -> None:
        if path.suffix == ".pending":
            raise OSError("synthetic pending unlink failure")
        original_path_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(
        "autoflow.infrastructure.filesystem.workflow_artifacts.os.replace",
        fail_pending_transition,
    )
    monkeypatch.setattr(Path, "unlink", fail_pending_unlink)

    with pytest.raises(WorkflowRunError) as caught:
        await writer.write_binary_output(
            output_path="result.xlsx",
            content=b"replacement",
            mime_type="application/octet-stream",
        )

    assert caught.value.code == "ARTIFACT_CLEANUP_FAILED"
    cleanup_root = root / "maintenance/workflow-output-backups"
    assert len(list(cleanup_root.glob("*.pending"))) == 1
    assert len(list(cleanup_root.glob("*.cleanup-marker"))) == 1

    monkeypatch.undo()
    WorkflowArtifactStore(root, Repository())

    assert not list(cleanup_root.iterdir())


def test_pending_cleanup_scan_cannot_escape_through_imported_workspace_symlink(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    outside_root = tmp_path / "outside"
    cleanup_root = outside_root / "workflow-output-backups"
    cleanup_root.mkdir(parents=True)
    outside = cleanup_root / "forged.cleanup"
    outside.write_bytes(b"must remain")
    (root / "maintenance").symlink_to(outside_root, target_is_directory=True)

    WorkflowArtifactStore(root, object())  # type: ignore[arg-type]

    assert outside.read_bytes() == b"must remain"
