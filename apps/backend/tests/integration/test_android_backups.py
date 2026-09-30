from __future__ import annotations

import asyncio
import io
import tarfile
from pathlib import Path

import pytest

from autoflow.application.android.backups import AndroidBackupService
from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android_operations import (
    SqlAlchemyAndroidOperationRepository,
)
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)

IMAGE = "sha256:" + "a" * 64


@pytest.mark.asyncio
async def test_backup_is_persisted_and_same_request_does_not_rearchive(
    tmp_path: Path,
) -> None:
    sessions = _sessions(tmp_path)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    runtime = _Runtime(_tar(b'{"theme":"dark"}'))
    service = AndroidBackupService(resources, tmp_path, operations)
    device = _device()

    first = await service.create_with_runtime(device, None, runtime, "backup-1", 3)
    replay = await service.create_with_runtime(device, None, runtime, "backup-1", 3)

    assert replay["id"] == first["id"]
    assert runtime.backup_calls == runtime.estimate_calls == 1
    assert (
        operations.by_request(str(tmp_path.resolve()), "backup-1").state == "succeeded"
    )
    assert runtime.locked == 0
    assert (Path(first["path"]) / "data.tar").stat().st_mode & 0o777 == 0o600
    sessions.dispose()


@pytest.mark.asyncio
async def test_unknown_backup_result_is_durable_and_never_replayed(
    tmp_path: Path,
) -> None:
    sessions = _sessions(tmp_path)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    runtime = _Runtime(_tar(b"data"), backup_error=OSError("connection lost"))
    service = AndroidBackupService(resources, tmp_path, operations)

    with pytest.raises(AndroidError, match="结果未知"):
        await service.create_with_runtime(_device(), None, runtime, "backup-unknown", 1)
    assert (
        operations.by_request(str(tmp_path.resolve()), "backup-unknown").state
        == "needs_verification"
    )
    assert resources.list("backup") == []
    with pytest.raises(AndroidError, match="已处理"):
        await service.create_with_runtime(_device(), None, runtime, "backup-unknown", 1)
    assert runtime.backup_calls == 1
    assert not list((tmp_path / "android-backups" / "staging").glob("*"))
    sessions.dispose()


@pytest.mark.asyncio
async def test_cancelled_backup_marks_result_unknown_and_releases_runtime(
    tmp_path: Path,
) -> None:
    sessions = _sessions(tmp_path)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    runtime = _Runtime(_tar(b"data"), backup_error=asyncio.CancelledError())
    service = AndroidBackupService(resources, tmp_path, operations)

    with pytest.raises(asyncio.CancelledError):
        await service.create_with_runtime(_device(), None, runtime, "backup-cancelled", 1)

    operation = operations.by_request(str(tmp_path.resolve()), "backup-cancelled")
    assert operation.state == "needs_verification"
    assert operation.result_code == "BACKUP_RESULT_UNKNOWN"
    assert runtime.locked == 0
    assert not list((tmp_path / "android-backups" / "staging").glob("*"))
    sessions.dispose()


def _sessions(tmp_path: Path):
    path = tmp_path / "android-backups.sqlite3"
    migrate_database(path)
    return create_session_factory(path)


def _device() -> dict:
    return {
        "deviceId": "source-device",
        "imageId": IMAGE,
        "control": "idle",
        "ownerRunId": None,
        "generation": 3,
        "creationConfig": {
            "width": 720,
            "height": 1280,
            "dpi": 320,
            "cpu": 2,
            "memoryMb": 1536,
        },
    }


def _tar(content: bytes) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        info = tarfile.TarInfo("data/settings.json")
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    return stream.getvalue()


class _Runtime:
    def __init__(self, payload: bytes, backup_error: BaseException | None = None):
        self.payload = payload
        self.backup_error = backup_error
        self.backup_calls = 0
        self.estimate_calls = 0
        self.locked = 0

    def lock(self):
        self.locked += 1

    def unlock(self):
        self.locked -= 1

    async def inspect(self, _device):
        return {"androidStatus": "stopped"}

    async def estimate_backup_bytes(self, _device):
        self.estimate_calls += 1
        return len(self.payload)

    async def backup_volume(self, _device):
        self.backup_calls += 1
        if self.backup_error:
            raise self.backup_error
        return self.payload


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["write", "read", "file_sync", "rename", "directory_sync", "record"])
async def test_failed_publication_is_not_available_after_repository_reconstruction(tmp_path, monkeypatch, failure):
    import os
    import stat

    sessions = _sessions(tmp_path)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    runtime = _Runtime(_tar(b"proof"))
    service = AndroidBackupService(resources, tmp_path, operations)
    original_write, original_open = Path.write_bytes, Path.open
    original_sync, original_replace = os.fsync, os.replace

    def write(path, data):
        if failure == "write" and path.name == "data.tar":
            raise OSError(28, "injected disk full")
        return original_write(path, data)

    def open_file(path, mode="r", *args, **kwargs):
        if failure == "read" and path.name == "data.tar" and "r" in mode:
            raise PermissionError("injected archive read denied")
        return original_open(path, mode, *args, **kwargs)

    def sync(fd):
        if failure == "file_sync" and stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("injected file fsync failure")
        if failure == "directory_sync" and list(service.storage.final.glob("*")):
            raise OSError("injected parent fsync failure")
        return original_sync(fd)

    def replace(source, target):
        if failure == "rename":
            raise PermissionError("injected rename denied")
        return original_replace(source, target)

    def before_flush(session, _context, _instances):
        from autoflow.infrastructure.database.android_models import AndroidResourceRow
        if failure == "record" and any(isinstance(row, AndroidResourceRow) for row in session.new):
            raise OSError("injected database write failure")

    monkeypatch.setattr(Path, "write_bytes", write)
    monkeypatch.setattr(Path, "open", open_file)
    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "replace", replace)
    from sqlalchemy import event
    event.listen(sessions, "before_flush", before_flush)
    with pytest.raises(AndroidError) as error:
        await service.create_with_runtime(_device(), None, runtime, "publication-fault", 3)
    assert error.value.code != "ANDROID_OPERATION_STATE_CONFLICT"
    assert runtime.locked == 0
    assert not list(service.storage.staging.glob("*"))
    assert not list(service.storage.final.glob("*"))
    fresh_resources = AndroidResourceRepository(sessions)
    fresh_operations = SqlAlchemyAndroidOperationRepository(sessions)
    fresh_service = AndroidBackupService(fresh_resources, tmp_path, fresh_operations)
    assert fresh_resources.list("backup") == []
    assert fresh_operations.by_request(str(tmp_path.resolve()), "publication-fault").state in {"failed", "needs_verification"}
    with pytest.raises(AndroidError, match="已处理"):
        await fresh_service.create_with_runtime(_device(), None, runtime, "publication-fault", 3)
    assert runtime.backup_calls == 1
    sessions.dispose()


@pytest.mark.asyncio
async def test_committed_backup_survives_lost_database_acknowledgement(tmp_path, monkeypatch):
    sessions = _sessions(tmp_path)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    service = AndroidBackupService(resources, tmp_path, operations)
    runtime = _Runtime(_tar(b"committed"))
    original = operations.complete_backup

    def lost_ack(*args):
        original(*args)
        raise OSError("database commit acknowledgement lost")

    monkeypatch.setattr(operations, "complete_backup", lost_ack)
    record = await service.create_with_runtime(_device(), None, runtime, "committed-backup", 3)
    assert record["state"] == "available"
    assert (Path(record["path"]) / "data.tar").read_bytes() == runtime.payload
    assert resources.get("backup", record["id"]) == record
    assert operations.by_request(str(tmp_path.resolve()), "committed-backup").state == "succeeded"
    replay = await service.create_with_runtime(_device(), None, runtime, "committed-backup", 3)
    assert replay == record and runtime.backup_calls == 1
    sessions.dispose()


def test_backup_record_and_success_roll_back_together(tmp_path):
    from sqlalchemy import event

    from autoflow.infrastructure.database.android_models import AndroidResourceRow

    sessions = _sessions(tmp_path)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    workspace = str(tmp_path.resolve())
    operation = operations.accept(workspace, "atomic", "device", "backup", "digest", {})
    operations.transition(operation.operation_id, "queued", "running", {})
    record = {"id": "backup", "workspaceId": workspace, "deviceId": "device", "requestId": "atomic", "requestDigest": "digest", "state": "available"}

    def before_flush(session, _context, _instances):
        if any(isinstance(row, AndroidResourceRow) for row in session.new):
            raise OSError("injected transaction rollback")

    event.listen(sessions, "before_flush", before_flush)
    with pytest.raises(OSError, match="transaction rollback"):
        operations.complete_backup(operation.operation_id, record)
    assert operations.get(operation.operation_id).state == "running"
    assert AndroidResourceRepository(sessions).list("backup") == []
    sessions.dispose()


@pytest.mark.asyncio
async def test_cancel_before_catalogue_commit_cleans_unpublished_backup(tmp_path):
    from sqlalchemy import event

    from autoflow.infrastructure.database.android_models import AndroidResourceRow

    sessions = _sessions(tmp_path)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    resources = AndroidResourceRepository(sessions)
    service = AndroidBackupService(resources, tmp_path, operations)

    def before_flush(session, _context, _instances):
        if any(isinstance(row, AndroidResourceRow) for row in session.new):
            raise asyncio.CancelledError()

    event.listen(sessions, "before_flush", before_flush)
    with pytest.raises(asyncio.CancelledError):
        await service.create_with_runtime(_device(), None, _Runtime(_tar(b"cancel")), "cancel-commit", 3)
    assert resources.list("backup") == []
    assert not list(service.storage.final.glob("*"))
    assert operations.by_request(str(tmp_path.resolve()), "cancel-commit").state == "needs_verification"
    sessions.dispose()


@pytest.mark.asyncio
async def test_unverifiable_commit_preserves_archive_and_blocks_replay(tmp_path, monkeypatch):
    sessions = _sessions(tmp_path)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    resources = AndroidResourceRepository(sessions)
    service = AndroidBackupService(resources, tmp_path, operations)
    runtime = _Runtime(_tar(b"unknown"))
    original_list = resources.list
    attempted = False

    def commit(*_args):
        nonlocal attempted
        attempted = True
        raise OSError("commit status unknown")

    def read(kind):
        if attempted:
            raise OSError("catalogue unavailable")
        return original_list(kind)

    monkeypatch.setattr(operations, "complete_backup", commit)
    monkeypatch.setattr(resources, "list", read)
    with pytest.raises(AndroidError) as error:
        await service.create_with_runtime(_device(), None, runtime, "unverifiable", 3)
    assert error.value.code == "ANDROID_BACKUP_RESULT_UNKNOWN"
    assert len(list(service.storage.final.glob("*/data.tar"))) == 1
    assert operations.by_request(str(tmp_path.resolve()), "unverifiable").state == "needs_verification"
    fresh = AndroidBackupService(AndroidResourceRepository(sessions), tmp_path, SqlAlchemyAndroidOperationRepository(sessions))
    with pytest.raises(AndroidError, match="已处理"):
        await fresh.create_with_runtime(_device(), None, runtime, "unverifiable", 3)
    assert runtime.backup_calls == 1
    sessions.dispose()


@pytest.mark.asyncio
async def test_preflight_rejection_is_durable_and_failed_request_does_not_reestimate(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from autoflow.providers.android import backup_storage

    sessions = _sessions(tmp_path)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    service = AndroidBackupService(resources, tmp_path, operations)
    runtime = _Runtime(_tar(b"preserved"))
    monkeypatch.setattr(backup_storage.shutil, "disk_usage", lambda _path: SimpleNamespace(free=0))
    with pytest.raises(AndroidError) as rejected:
        await service.create_with_runtime(_device(), None, runtime, "no-disk", 1)
    assert rejected.value.code == "ANDROID_DISK_SPACE_INSUFFICIENT"
    fresh_operations = SqlAlchemyAndroidOperationRepository(sessions)
    record = fresh_operations.by_request(str(tmp_path.resolve()), "no-disk")
    assert record.state == "failed" and record.result_code == rejected.value.code
    fresh_service = AndroidBackupService(AndroidResourceRepository(sessions), tmp_path, fresh_operations)
    with pytest.raises(AndroidError) as replay:
        await fresh_service.create_with_runtime(_device(), None, runtime, "no-disk", 1)
    assert replay.value.code == "ANDROID_BACKUP_REQUEST_REPLAYED"
    assert runtime.estimate_calls == 1 and runtime.backup_calls == 0
    assert resources.list("backup") == []
    assert not service.storage.staging.exists()
    sessions.dispose()


@pytest.mark.asyncio
async def test_cancelled_backup_estimation_records_no_write_and_releases_for_new_request(tmp_path):
    sessions = _sessions(tmp_path)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    service = AndroidBackupService(resources, tmp_path, operations)
    runtime = _Runtime(_tar(b"preserved"))
    entered = asyncio.Event()
    original_estimate = runtime.estimate_backup_bytes

    async def suspended_estimate(_device):
        entered.set()
        await asyncio.Event().wait()

    runtime.estimate_backup_bytes = suspended_estimate
    task = asyncio.create_task(service.create_with_runtime(_device(), None, runtime, "cancel-estimate", 1))
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    record = operations.by_request(str(tmp_path.resolve()), "cancel-estimate")
    assert record.state == "failed" and record.result_code == "BACKUP_PREFLIGHT_CANCELLED"
    assert runtime.backup_calls == 0 and runtime.locked == 0
    assert not service.storage.staging.exists()
    runtime.estimate_backup_bytes = original_estimate
    backup = await service.create_with_runtime(_device(), None, runtime, "new-estimate", 1)
    assert backup["state"] == "available" and runtime.backup_calls == 1
    sessions.dispose()
