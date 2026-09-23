import asyncio
from pathlib import Path

import pytest

from autoflow.infrastructure.filesystem.project_workflow_artifacts import (
    ProjectScreenshotWriter,
)


@pytest.mark.asyncio
async def test_project_screenshot_returns_only_after_ack_and_keeps_filename(tmp_path):
    arrived, confirmed = asyncio.Event(), asyncio.Event()
    events = []

    async def emit(*event):
        events.append(event)
        arrived.set()
        await confirmed.wait()

    writer = ProjectScreenshotWriter(tmp_path, "run", 2, "shot", "visit", emit)
    pending = asyncio.create_task(
        writer.write_bytes(
            name="nested/capture.png", content=b"png", mime_type="image/png"
        )
    )
    await asyncio.wait_for(arrived.wait(), 3)
    assert not pending.done()
    kind, node, visit, payload = events[0]
    assert (kind, node, visit) == ("artifact", "shot", "visit")
    assert payload["purpose"] == "result"
    assert (
        payload["relativePath"] == "runs/run/generation-2/artifacts/nested/capture.png"
    )
    assert (tmp_path / payload["relativePath"]).read_bytes() == b"png"
    confirmed.set()
    assert Path(await pending) == tmp_path / payload["relativePath"]


@pytest.mark.asyncio
async def test_uncertain_ack_does_not_delete_possible_committed_screenshot(tmp_path):
    events = []

    async def emit(*event):
        events.append(event)
        raise RuntimeError("ACK connection lost after SQL commit")

    writer = ProjectScreenshotWriter(tmp_path, "run", 1, "shot", "visit", emit)
    with pytest.raises(RuntimeError, match="ACK connection lost"):
        await writer.write_bytes(
            name="capture.png", content=b"png", mime_type="image/png"
        )
    assert (tmp_path / events[0][3]["relativePath"]).read_bytes() == b"png"


@pytest.mark.asyncio
async def test_screenshot_paths_and_existing_files_keep_shared_store_rules(tmp_path):
    events = []

    async def emit(*event):
        events.append(event)

    writer = ProjectScreenshotWriter(tmp_path, "run", 1, "shot", "visit", emit)
    from autoflow.domain.workflows.runs import WorkflowRunError

    with pytest.raises(WorkflowRunError, match="产物路径无效"):
        await writer.write_bytes(
            name="../outside.png", content=b"png", mime_type="image/png"
        )
    original = await writer.write_bytes(
        name="capture.png", content=b"first", mime_type="image/png"
    )
    with pytest.raises(WorkflowRunError, match="产物文件已存在"):
        await writer.write_bytes(
            name="capture.png", content=b"second", mime_type="image/png"
        )
    assert Path(original).read_bytes() == b"first"
    assert len(events) == 1


@pytest.mark.asyncio
async def test_generation_symlink_is_rejected_before_any_external_file_is_written(
    tmp_path,
):
    from autoflow.domain.workflows.runs import WorkflowRunError

    root, outside = tmp_path / "workspace", tmp_path / "outside"
    outside.mkdir()
    run_root = root / "runs" / "run"
    run_root.mkdir(parents=True)
    (run_root / "generation-3").symlink_to(outside, target_is_directory=True)
    events = []

    async def emit(*event):
        events.append(event)

    failure = None
    try:
        writer = ProjectScreenshotWriter(root, "run", 3, "shot", "visit", emit)
        await writer.write_bytes(
            name="capture.png", content=b"png", mime_type="image/png"
        )
    except (WorkflowRunError, ValueError) as error:
        failure = error
    assert list(outside.rglob("*")) == [], (
        "rejected generation must not create external directories or files"
    )
    assert events == []
    assert isinstance(failure, WorkflowRunError)
    assert failure.code == "ARTIFACT_PATH_INVALID"


@pytest.mark.asyncio
async def test_cancel_during_blocked_file_write_waits_for_cleanup_without_unregistered_file(
    tmp_path, monkeypatch
):
    from threading import Event

    from autoflow.infrastructure.filesystem.workflow_artifacts import (
        WorkflowArtifactStore,
    )

    entered, release, finished = Event(), Event(), Event()
    original = WorkflowArtifactStore._place_file
    events = []

    def blocked_write(target, content):
        entered.set()
        try:
            assert release.wait(5), "test did not release controlled file write"
            original(target, content)
        finally:
            finished.set()

    monkeypatch.setattr(
        WorkflowArtifactStore, "_place_file", staticmethod(blocked_write)
    )

    async def emit(*event):
        events.append(event)

    writer = ProjectScreenshotWriter(tmp_path, "run", 4, "shot", "visit", emit)
    pending = asyncio.create_task(
        writer.write_bytes(name="cancelled.png", content=b"png", mime_type="image/png")
    )
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        pending.cancel()
        await asyncio.sleep(
            0
        )  # Deliver cancellation while the thread is still blocked.
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(pending, 3)
        assert await asyncio.to_thread(finished.wait, 3)
        assert events == [], (
            "cancelled write must not send a completion/registration event"
        )
        generation = tmp_path / "runs" / "run" / "generation-4"
        assert not any(path.is_file() for path in generation.rglob("*")), (
            "cancelled write left an unregistered file"
        )
    finally:
        release.set()
        if not pending.done():
            pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        await asyncio.to_thread(finished.wait, 3)
