from __future__ import annotations

import asyncio
import sys
import textwrap
from pathlib import Path

import pytest

from autoflow.application.kernels.operations import KernelOperation
from autoflow.infrastructure.database.kernel_operations import (
    SqlAlchemyKernelOperationRepository,
)
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.events.kernel_events import KernelEventBroker
from autoflow.infrastructure.process.kernel_worker import (
    DEFAULT_TERMINATION_TIMEOUT,
    KernelInstallJob,
    KernelWorkerManager,
    KernelWorkerManagerBusy,
    KernelWorkerManagerError,
)

FAKE_WORKER = r'''
import json
import os
import signal
import sys
import time
from pathlib import Path

job = json.loads(sys.stdin.readline())
mode = os.environ.get("FAKE_WORKER_MODE", "complete")
if mode == "ignore-term":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
staging = Path(job["cacheDir"])
name = f'chromium-{job["requestedVersion"]}' + ('-pro' if job["edition"] == 'licensed' else '')
install = staging / name
executable = install / "chrome.exe"
executable.parent.mkdir(parents=True, exist_ok=True)
executable.write_bytes(b"new kernel")
print(json.dumps({"type": "progress", "state": "downloading", "progress": None}), flush=True)
if mode in {"wait", "ignore-term"}:
    time.sleep(30)
if mode == "crash":
    raise SystemExit(7)
if mode == "error-hang":
    print(json.dumps({"type": "error", "error": "failed"}), flush=True)
    time.sleep(30)
print(json.dumps({"type": "progress", "state": "verifying", "progress": None}), flush=True)
print(json.dumps({"type": "progress", "state": "extracting", "progress": None}), flush=True)
if mode == "symlink":
    (install / "escape").symlink_to(Path("/tmp"), target_is_directory=True)
relative = "../outside/chrome.exe" if mode == "escape" else f"{name}/chrome.exe"
print(json.dumps({
    "type": "completed",
    "resolvedVersion": job["requestedVersion"],
    "executableRelativePath": relative,
}), flush=True)
if mode == "complete-hang":
    time.sleep(30)
'''


@pytest.fixture
def repository(tmp_path: Path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    yield SqlAlchemyKernelOperationRepository(factory)
    factory.dispose()


@pytest.fixture
def fake_worker(tmp_path: Path) -> Path:
    script = tmp_path / "fake_kernel_worker.py"
    script.write_text(textwrap.dedent(FAKE_WORKER), encoding="utf-8")
    return script


def _manager(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
    *,
    mode: str = "complete",
    termination_timeout: float = 3.0,
) -> KernelWorkerManager:
    return KernelWorkerManager(
        kernels_dir=tmp_path / "kernels",
        repository=repository,
        events=KernelEventBroker(),
        command=(sys.executable, str(fake_worker)),
        worker_env={"FAKE_WORKER_MODE": mode},
        platform="windows-x64",
        termination_timeout=termination_timeout,
    )


def _job(version: str = "146.0.7680.80", *, license_key: str | None = None) -> KernelInstallJob:
    return KernelInstallJob(
        edition="licensed" if license_key else "public",
        requested_version=version,
        release_channel="stable",
        license_key=license_key,
    )


@pytest.mark.asyncio
async def test_cancel_does_not_publish_install(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    manager = _manager(tmp_path, repository, fake_worker, mode="wait")
    operation = await manager.start(_job())
    await manager.wait_for_state(operation.id, "downloading")

    cancelled = await manager.cancel(operation.id)
    await manager.wait(operation.id)

    assert cancelled.state == "cancelled"
    assert manager.get(operation.id).state == "cancelled"
    assert not (tmp_path / "kernels" / "chromium-146.0.7680.80").exists()
    assert manager.active_processes() == []


@pytest.mark.asyncio
async def test_cancel_waits_then_kills_uncooperative_worker(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    manager = _manager(
        tmp_path,
        repository,
        fake_worker,
        mode="ignore-term",
        termination_timeout=0.05,
    )
    operation = await manager.start(_job())
    await manager.wait_for_state(operation.id, "downloading")
    await manager.cancel(operation.id)

    assert manager.get(operation.id).state == "cancelled"
    assert manager.active_processes() == []
    assert DEFAULT_TERMINATION_TIMEOUT == 3.0


@pytest.mark.asyncio
async def test_concurrent_start_is_rejected_and_duplicate_cancel_is_idempotent(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    manager = _manager(tmp_path, repository, fake_worker, mode="wait")
    operation = await manager.start(_job())
    with pytest.raises(KernelWorkerManagerBusy) as error:
        await manager.start(_job("147.0.7777.1"))
    assert error.value.code == "KERNEL_BUSY"
    first, second = await asyncio.gather(
        manager.cancel(operation.id), manager.cancel(operation.id)
    )
    assert first.state == second.state == "cancelled"


@pytest.mark.asyncio
async def test_two_managers_share_an_os_install_lock_and_recovery_respects_owner(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    first = _manager(tmp_path, repository, fake_worker, mode="wait")
    second = _manager(tmp_path, repository, fake_worker, mode="wait")
    operation = await first.start(_job())
    await first.wait_for_state(operation.id, "downloading")
    staging = tmp_path / "kernels" / ".staging" / operation.id

    assert second.recover_interrupted() == []
    assert repository.get(operation.id).state == "downloading"
    assert staging.exists()
    with pytest.raises(KernelWorkerManagerBusy):
        await second.start(_job("147.0.7777.1"))

    await first.shutdown()
    next_operation = await second.start(_job("147.0.7777.1"))
    await second.wait_for_state(next_operation.id, "downloading")
    await second.shutdown()


@pytest.mark.parametrize(
    ("mode", "terminal"), [("complete-hang", "completed"), ("error-hang", "failed")]
)
@pytest.mark.asyncio
async def test_shutdown_reaps_worker_that_remains_alive_after_terminal_message(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
    mode: str,
    terminal: str,
) -> None:
    manager = _manager(
        tmp_path,
        repository,
        fake_worker,
        mode=mode,
        termination_timeout=0.05,
    )
    operation = await manager.start(_job())
    await manager.wait_for_state(operation.id, terminal)
    assert len(manager.active_processes()) == 1

    await manager.shutdown()

    assert manager.active_processes() == []
    assert manager.get(operation.id).state == terminal


@pytest.mark.asyncio
async def test_complete_wins_cancel_race_without_overwriting_terminal_state(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    manager = _manager(tmp_path, repository, fake_worker)
    operation = await manager.start(_job())
    completed = await manager.wait(operation.id)
    after_cancel = await manager.cancel(operation.id)

    assert completed.state == after_cancel.state == "completed"
    assert (tmp_path / "kernels" / "chromium-146.0.7680.80" / "chrome.exe").is_file()


@pytest.mark.asyncio
async def test_existing_valid_install_is_reused_without_overwrite(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    old_executable = tmp_path / "kernels" / "chromium-146.0.7680.80" / "chrome.exe"
    old_executable.parent.mkdir(parents=True)
    old_executable.write_bytes(b"old kernel")
    manager = _manager(tmp_path, repository, fake_worker)

    completed = await manager.wait((await manager.start(_job())).id)

    assert completed.state == "completed"
    assert old_executable.read_bytes() == b"old kernel"


@pytest.mark.parametrize("mode", ["escape", "symlink"])
@pytest.mark.asyncio
async def test_untrusted_worker_result_cannot_escape_or_publish(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
    mode: str,
) -> None:
    manager = _manager(tmp_path, repository, fake_worker, mode=mode)

    failed = await manager.wait((await manager.start(_job())).id)

    assert failed.state == "failed"
    assert failed.error == "Kernel worker protocol error"
    assert not (tmp_path / "kernels" / "chromium-146.0.7680.80").exists()


@pytest.mark.asyncio
async def test_cancel_preserves_an_existing_install(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    old_executable = tmp_path / "kernels" / "chromium-146.0.7680.80" / "chrome.exe"
    old_executable.parent.mkdir(parents=True)
    old_executable.write_bytes(b"old kernel")
    manager = _manager(tmp_path, repository, fake_worker, mode="wait")
    operation = await manager.start(_job())
    await manager.wait_for_state(operation.id, "downloading")
    await manager.cancel(operation.id)

    assert old_executable.read_bytes() == b"old kernel"


@pytest.mark.asyncio
async def test_worker_crash_is_persisted_as_failed(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    manager = _manager(tmp_path, repository, fake_worker, mode="crash")
    operation = await manager.start(_job())
    failed = await manager.wait(operation.id)

    assert failed.state == "failed"
    assert failed.error == "Kernel worker exited unexpectedly"
    assert repository.get(operation.id) == failed
    assert not (tmp_path / "kernels" / ".staging" / operation.id).exists()


def test_restart_marks_persisted_active_operations_failed(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    operation = KernelOperation.new(
        operation_id="interrupted",
        edition="public",
        requested_version="146.0.7680.80",
        release_channel="stable",
        state="downloading",
    )
    repository.save(operation)
    stale_staging = tmp_path / "kernels" / ".staging" / operation.id
    stale_staging.mkdir(parents=True)
    (stale_staging / "partial").write_bytes(b"partial")
    manager = _manager(tmp_path, repository, fake_worker)

    recovered = manager.recover_interrupted()

    assert [item.state for item in recovered] == ["failed"]
    assert recovered[0].error == "应用关闭，安装中断"
    assert not stale_staging.exists()


@pytest.mark.asyncio
async def test_staging_setup_failure_persists_failed_and_releases_ownership(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    kernels = tmp_path / "kernels"
    kernels.mkdir()
    (kernels / ".staging").write_bytes(b"not a directory")
    manager = _manager(tmp_path, repository, fake_worker)

    with pytest.raises(KernelWorkerManagerError):
        await manager.start(_job())

    operations = repository.list()
    assert len(operations) == 1
    assert operations[0].state == "failed"
    assert operations[0].error == "Kernel worker could not start"
    assert manager.active_processes() == []
    (kernels / ".staging").unlink()
    completed = await manager.wait((await manager.start(_job())).id)
    assert completed.state == "completed"


def test_operation_roundtrips_through_database(
    repository: SqlAlchemyKernelOperationRepository,
) -> None:
    operation = KernelOperation.new(
        operation_id="persisted",
        edition="licensed",
        requested_version="146.0.7680.80",
        release_channel="preview",
        state="queued",
    )
    repository.save(operation)

    assert repository.get("persisted") == operation


@pytest.mark.asyncio
async def test_shutdown_leaves_no_worker_process(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    manager = _manager(tmp_path, repository, fake_worker, mode="wait")
    operation = await manager.start(_job())
    await manager.wait_for_state(operation.id, "downloading")
    await manager.shutdown()

    assert manager.active_processes() == []
    assert manager.get(operation.id).state == "cancelled"


@pytest.mark.asyncio
async def test_license_is_only_sent_in_stdin(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    manager = _manager(tmp_path, repository, fake_worker)
    job = _job(license_key="private-test-key")
    operation = await manager.start(job)
    running = manager.active_processes()[0]

    assert "private-test-key" not in " ".join(running.args)
    assert "private-test-key" not in repr(job)
    assert "private-test-key" not in repr(repository.get(operation.id))
    await manager.wait(operation.id)
