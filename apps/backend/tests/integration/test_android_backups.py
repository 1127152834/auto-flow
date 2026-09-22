from __future__ import annotations

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
    assert runtime.backup_calls == 1
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
        self.locked = 0

    def lock(self):
        self.locked += 1

    def unlock(self):
        self.locked -= 1

    async def inspect(self, _device):
        return {"androidStatus": "stopped"}

    async def backup_volume(self, _device):
        self.backup_calls += 1
        if self.backup_error:
            raise self.backup_error
        return self.payload
