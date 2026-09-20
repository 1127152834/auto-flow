from __future__ import annotations

import asyncio
import sys
import textwrap
from dataclasses import replace
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
from autoflow.infrastructure.filesystem.locking import ExclusiveFileLock
from autoflow.infrastructure.process.kernel_worker import (
    DEFAULT_TERMINATION_TIMEOUT,
    KernelInstallJob,
    KernelWorkerManager,
    KernelWorkerManagerBusy,
    KernelWorkerManagerError,
)

FAKE_WORKER = r"""
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
if job["command"] == "catalog":
    if mode in {"wait", "ignore-term"}:
        time.sleep(30)
    print(json.dumps({"type": "catalog", "releases": [{"version": "151.0.7922.108", "releaseChannel": "stable"}]}), flush=True)
    raise SystemExit(0)
if job["command"] == "license":
    if mode in {"wait", "ignore-term"}:
        time.sleep(30)
    print(json.dumps({"type": "license", "status": {"configured": True, "valid": True, "plan": "pro", "expires": None, "seats": {"active": 1, "limit": 2}}}), flush=True)
    raise SystemExit(0)
resolved_version = os.environ.get("FAKE_RESOLVED_VERSION", job["requestedVersion"])
name = f'chromium-{resolved_version}' + ('-pro' if job["edition"] == 'licensed' else '')
install = staging / name
platform = os.environ.get("FAKE_WORKER_PLATFORM", "windows-x64")
executable = (
    install / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
    if platform.startswith("darwin-")
    else install / "chrome.exe"
)
executable.parent.mkdir(parents=True, exist_ok=True)
executable.write_bytes(b"new kernel")
print(json.dumps({"type": "progress", "state": "downloading", "progress": None}), flush=True)
if mode in {"wait", "ignore-term"}:
    time.sleep(30)
if mode == "wait-first" and job["requestedVersion"].endswith(".80"):
    time.sleep(30)
if mode == "wait-first":
    time.sleep(0.2)
if mode == "crash":
    raise SystemExit(7)
if mode == "error-hang":
    print(json.dumps({"type": "error", "error": "failed"}), flush=True)
    time.sleep(30)
print(json.dumps({"type": "progress", "state": "verifying", "progress": None}), flush=True)
print(json.dumps({"type": "progress", "state": "extracting", "progress": None}), flush=True)
if mode == "symlink":
    (install / "escape").symlink_to(Path("/tmp"), target_is_directory=True)
relative = (
    "../outside/chrome.exe"
    if mode == "escape"
    else executable.relative_to(staging).as_posix()
)
print(json.dumps({
    "type": "completed",
    "resolvedVersion": resolved_version,
    "executableRelativePath": relative,
}), flush=True)
if mode == "complete-hang":
    time.sleep(30)
"""


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
    rpc_timeout: float = 20.0,
    platform: str = "windows-x64",
    resolved_version: str | None = None,
) -> KernelWorkerManager:
    worker_env = {"FAKE_WORKER_MODE": mode, "FAKE_WORKER_PLATFORM": platform}
    if resolved_version is not None:
        worker_env["FAKE_RESOLVED_VERSION"] = resolved_version
    return KernelWorkerManager(
        kernels_dir=tmp_path / "kernels",
        repository=repository,
        events=KernelEventBroker(),
        command=(sys.executable, str(fake_worker)),
        worker_env=worker_env,
        platform=platform,
        termination_timeout=termination_timeout,
        rpc_timeout=rpc_timeout,
    )


def _job(
    version: str = "146.0.7680.80", *, license_key: str | None = None
) -> KernelInstallJob:
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
async def test_catalog_and_license_rpc_are_supervised_and_clean_their_cache(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    manager = _manager(tmp_path, repository, fake_worker)

    releases = await manager.licensed_catalog()
    status = await manager.validate_license("private-test-key")

    assert releases == [{"version": "151.0.7922.108", "releaseChannel": "stable"}]
    assert status.valid is True
    assert status.seats is not None and status.seats.active == 1
    assert manager.active_processes() == []
    assert list((tmp_path / "kernels" / ".rpc").iterdir()) == []


@pytest.mark.asyncio
async def test_rpc_timeout_and_caller_cancellation_reap_workers_and_cache(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    manager = _manager(
        tmp_path,
        repository,
        fake_worker,
        mode="wait",
        rpc_timeout=0.05,
        termination_timeout=0.05,
    )

    with pytest.raises(Exception, match="timed out"):
        await manager.licensed_catalog()
    task = asyncio.create_task(manager.licensed_catalog())
    while not manager.active_processes():
        await asyncio.sleep(0.005)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert manager.active_processes() == []
    assert list((tmp_path / "kernels" / ".rpc").iterdir()) == []


@pytest.mark.asyncio
async def test_shutdown_cancels_one_shot_rpc_and_preserves_install_staging_namespace(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    staging = tmp_path / "kernels" / ".staging" / "unrelated"
    staging.mkdir(parents=True)
    manager = _manager(
        tmp_path, repository, fake_worker, mode="wait", termination_timeout=0.05
    )
    task = asyncio.create_task(manager.licensed_catalog())
    while not manager.active_processes():
        await asyncio.sleep(0.005)

    await manager.shutdown()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert manager.active_processes() == []
    assert list((tmp_path / "kernels" / ".rpc").iterdir()) == []
    assert staging.is_dir()


def test_rpc_startup_cleanup_removes_only_unowned_cache(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    root = tmp_path / "kernels" / ".rpc"
    stale = root / "stale"
    active = root / "active"
    stale.mkdir(parents=True)
    active.mkdir()
    ownership = ExclusiveFileLock(active / ".owner.lock")
    assert ownership.acquire()
    try:
        _manager(tmp_path, repository, fake_worker)
        assert not stale.exists()
        assert active.exists()
    finally:
        ownership.release()

    _manager(tmp_path, repository, fake_worker)
    assert not active.exists()


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
async def test_different_targets_run_concurrently_and_duplicate_cancel_is_idempotent(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    manager = _manager(tmp_path, repository, fake_worker, mode="wait")
    operation = await manager.start(_job())
    other = await manager.start(_job("147.0.7777.1"))
    await manager.wait_for_state(operation.id, "downloading")
    await manager.wait_for_state(other.id, "downloading")
    assert len(manager.active_processes()) == 2
    first, second = await asyncio.gather(
        manager.cancel(operation.id), manager.cancel(operation.id)
    )
    assert first.state == second.state == "cancelled"
    assert manager.get(other.id).state == "downloading"
    await manager.cancel(other.id)


@pytest.mark.asyncio
async def test_cancel_one_download_does_not_stop_another_target(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    manager = _manager(tmp_path, repository, fake_worker, mode="wait-first")
    first = await manager.start(_job())
    second = await manager.start(_job("147.0.7777.1"))
    await manager.wait_for_state(first.id, "downloading")
    await manager.wait_for_state(second.id, "downloading")

    cancelled = await manager.cancel(first.id)
    completed = await manager.wait(second.id)

    assert cancelled.state == "cancelled"
    assert completed.state == "completed"
    assert (tmp_path / "kernels" / "chromium-147.0.7777.1" / "chrome.exe").is_file()


@pytest.mark.asyncio
async def test_same_install_target_is_rejected_across_channels_and_managers(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    first = _manager(tmp_path, repository, fake_worker, mode="wait")
    second = _manager(tmp_path, repository, fake_worker, mode="wait")
    operation = await first.start(_job("151.0.7922.108", license_key="key"))
    await first.wait_for_state(operation.id, "downloading")

    with pytest.raises(KernelWorkerManagerBusy) as error:
        await second.start(
            KernelInstallJob(
                edition="licensed",
                requested_version="151.0.7922.108",
                release_channel="preview",
                license_key="key",
            )
        )

    assert error.value.code == "KERNEL_BUSY"
    await first.shutdown()


@pytest.mark.asyncio
async def test_two_managers_run_different_targets_and_recovery_respects_each_owner(
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
    next_operation = await second.start(_job("147.0.7777.1"))
    await second.wait_for_state(next_operation.id, "downloading")
    assert first.recover_interrupted() == []
    assert repository.get(next_operation.id).state == "downloading"

    await asyncio.gather(first.shutdown(), second.shutdown())


@pytest.mark.asyncio
async def test_different_requests_resolving_to_same_target_are_reused_safely(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
) -> None:
    resolved = "152.0.8000.1"
    manager = _manager(tmp_path, repository, fake_worker, resolved_version=resolved)

    first, second = await asyncio.gather(
        manager.start(_job("151.0.7922.108", license_key="key")),
        manager.start(_job("151.0.7922.109", license_key="key")),
    )
    completed = await asyncio.gather(manager.wait(first.id), manager.wait(second.id))

    assert [item.resolved_version for item in completed] == [resolved, resolved]
    assert (
        tmp_path / "kernels" / f"chromium-{resolved}-pro" / "chrome.exe"
    ).read_bytes() == b"new kernel"
    assert not (tmp_path / "kernels" / "chromium-151.0.7922.108-pro").exists()
    assert not (tmp_path / "kernels" / "chromium-151.0.7922.109-pro").exists()


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


def test_recovery_rereads_operation_before_cleaning_stale_snapshot(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = KernelOperation.new(
        operation_id="finished-while-recovering",
        edition="public",
        requested_version="146.0.7680.80",
        release_channel="stable",
        state="downloading",
    )
    staging = tmp_path / "kernels" / ".staging" / candidate.id
    staging.mkdir(parents=True)
    (staging / "partial").write_bytes(b"still owned result")
    repository.save(replace(candidate, state="completed"))
    monkeypatch.setattr(repository, "list_active", lambda: [candidate])

    recovered = _manager(tmp_path, repository, fake_worker).recover_interrupted()

    assert recovered == []
    assert repository.get(candidate.id).state == "completed"
    assert staging.is_dir()


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


@pytest.mark.asyncio
async def test_cancelling_start_while_spawn_is_pending_reaps_created_process(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_spawn = asyncio.create_subprocess_exec
    entered = asyncio.Event()
    continue_spawn = asyncio.Event()
    spawned: list[asyncio.subprocess.Process] = []

    async def delayed_spawn(
        *args: object, **kwargs: object
    ) -> asyncio.subprocess.Process:
        entered.set()
        await continue_spawn.wait()
        process = await real_spawn(*args, **kwargs)
        spawned.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed_spawn)
    manager = _manager(
        tmp_path, repository, fake_worker, mode="wait", termination_timeout=0.05
    )
    start = asyncio.create_task(manager.start(_job()))
    await entered.wait()

    start.cancel()
    continue_spawn.set()
    with pytest.raises(asyncio.CancelledError):
        await start

    assert spawned[0].returncode is not None
    await _assert_cancelled_start_recovered(
        tmp_path, repository, fake_worker, monkeypatch, real_spawn
    )


@pytest.mark.asyncio
async def test_repeated_cancellation_during_stdin_drain_finishes_compensation(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_spawn = asyncio.create_subprocess_exec
    drain_entered = asyncio.Event()
    never = asyncio.Event()
    spawned: list[asyncio.subprocess.Process] = []

    async def blocked_drain_spawn(
        *args: object, **kwargs: object
    ) -> asyncio.subprocess.Process:
        process = await real_spawn(*args, **kwargs)
        assert process.stdin is not None

        async def blocked_drain() -> None:
            drain_entered.set()
            await never.wait()

        monkeypatch.setattr(process.stdin, "drain", blocked_drain)
        spawned.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", blocked_drain_spawn)
    manager = _manager(
        tmp_path,
        repository,
        fake_worker,
        mode="ignore-term",
        termination_timeout=0.05,
    )
    start = asyncio.create_task(manager.start(_job()))
    await drain_entered.wait()

    start.cancel()
    await asyncio.sleep(0.01)
    start.cancel()
    with pytest.raises(asyncio.CancelledError):
        await start

    assert spawned[0].returncode is not None
    await _assert_cancelled_start_recovered(
        tmp_path, repository, fake_worker, monkeypatch, real_spawn
    )


async def _assert_cancelled_start_recovered(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
    monkeypatch: pytest.MonkeyPatch,
    real_spawn: object,
) -> None:
    operations = repository.list()
    assert len(operations) == 1
    assert operations[0].state == "failed"
    assert operations[0].error == "Kernel worker start was cancelled"
    assert not (tmp_path / "kernels" / ".staging" / operations[0].id).exists()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", real_spawn)
    second = _manager(tmp_path, repository, fake_worker)
    completed = await second.wait((await second.start(_job("147.0.7777.1"))).id)
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
async def test_shutdown_reaps_multiple_uncooperative_workers_in_parallel_and_closes_gate(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
    monkeypatch,
) -> None:
    manager = _manager(
        tmp_path,
        repository,
        fake_worker,
        mode="ignore-term",
        termination_timeout=0.05,
    )
    operations = [
        await manager.start(_job(version))
        for version in ("146.0.7680.80", "147.0.7777.1", "148.0.7800.2")
    ]
    await asyncio.gather(
        *(manager.wait_for_state(item.id, "downloading") for item in operations)
    )

    stop_process = manager._stop_process
    all_stopping = asyncio.Event()
    stopping = 0

    async def stop_together(process):
        nonlocal stopping
        stopping += 1
        if stopping == len(operations):
            all_stopping.set()
        await all_stopping.wait()
        await stop_process(process)

    monkeypatch.setattr(manager, "_stop_process", stop_together)
    await asyncio.wait_for(manager.shutdown(), timeout=5)
    assert stopping == len(operations)
    assert manager.active_processes() == []
    assert [manager.get(item.id).state for item in operations] == ["cancelled"] * 3
    assert all(
        not (tmp_path / "kernels" / ".staging" / item.id).exists()
        for item in operations
    )
    with pytest.raises(KernelWorkerManagerError, match="shutting down"):
        await manager.start(_job("149.0.7900.3"))


@pytest.mark.parametrize(
    ("platform", "relative_executable"),
    [
        ("windows-x64", Path("chrome.exe")),
        (
            "darwin-x64",
            Path("Chromium.app/Contents/MacOS/Chromium"),
        ),
        (
            "darwin-arm64",
            Path("Chromium.app/Contents/MacOS/Chromium"),
        ),
    ],
)
@pytest.mark.asyncio
async def test_worker_publishes_the_platform_specific_executable_path(
    tmp_path: Path,
    repository: SqlAlchemyKernelOperationRepository,
    fake_worker: Path,
    platform: str,
    relative_executable: Path,
) -> None:
    manager = _manager(tmp_path, repository, fake_worker, platform=platform)

    operation = await manager.wait((await manager.start(_job())).id)

    assert operation.state == "completed"
    assert (
        tmp_path / "kernels" / "chromium-146.0.7680.80" / relative_executable
    ).is_file()


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
