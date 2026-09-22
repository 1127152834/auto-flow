from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.backups import AndroidBackupService
from autoflow.application.android.devices import AndroidDeviceService
from autoflow.application.android.diagnostics import EnvironmentCheckService
from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.android_operations import (
    SqlAlchemyAndroidOperationRepository,
)
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)

IMAGE = "sha256:" + "b" * 64


@pytest.mark.asyncio
async def test_restore_request_id_creates_one_isolated_target(tmp_path: Path) -> None:
    sessions = _sessions(tmp_path)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    repository = SqlAlchemyDeviceRepository(sessions)
    runtime = _Runtime(_tar(b"source"), IMAGE)
    devices = AndroidDeviceService(repository, runtime)
    devices.management.workspace_identity = str(tmp_path.resolve())
    backups = AndroidBackupService(resources, tmp_path, operations)
    source = {
        "deviceId": "source-device",
        "name": "source",
        "imageId": IMAGE,
        "control": "idle",
        "ownerRunId": None,
        "generation": 1,
        "creationConfig": {
            "width": 720,
            "height": 1280,
            "dpi": 320,
            "cpu": 2,
            "memoryMb": 1536,
        },
    }
    repository.save(source)
    backup = await backups.create_with_runtime(
        source, None, runtime, "backup-request", 1
    )

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(
        android_management_router(
            EnvironmentCheckService(runtime),
            operations,
            backups=backups,
            devices=devices,
        )
    )
    body = {"requestId": "restore-request", "newName": "copy"}
    with TestClient(app) as client:
        first = client.post(
            f"/api/v1/android/management/backups/{backup['id']}/restore", json=body
        )
        second = client.post(
            f"/api/v1/android/management/backups/{backup['id']}/restore", json=body
        )

    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert first.json()["deviceId"] == second.json()["deviceId"]
    assert runtime.restore_calls == 1
    assert len(repository.list()) == 2
    assert (
        operations.by_request(str(tmp_path.resolve()), "restore-request").state
        == "succeeded"
    )
    sessions.dispose()


@pytest.mark.asyncio
async def test_restore_rejects_corrupt_digest_and_does_not_write_runtime(
    tmp_path: Path,
) -> None:
    sessions = _sessions(tmp_path)
    resources = AndroidResourceRepository(sessions)
    runtime = _Runtime(_tar(b"source"), IMAGE)
    backups = AndroidBackupService(resources, tmp_path)
    source = {
        "deviceId": "source",
        "imageId": IMAGE,
        "control": "idle",
        "ownerRunId": None,
    }
    record = await backups.create_with_runtime(
        source, {"androidStatus": "stopped"}, runtime
    )
    (Path(record["path"]) / "data.tar").write_bytes(b"corrupt")
    with pytest.raises(AndroidError, match="摘要"):
        await backups.restore_data(
            record["id"], {"deviceId": "target", "imageId": IMAGE}, runtime
        )
    assert runtime.restore_calls == 0
    sessions.dispose()


def _sessions(tmp_path: Path):
    path = tmp_path / "android-restore.sqlite3"
    migrate_database(path)
    return create_session_factory(path)


def _tar(content: bytes) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        info = tarfile.TarInfo("data/settings.json")
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    return stream.getvalue()


class _Runtime:
    def __init__(self, payload: bytes, image: str):
        self.payload = payload
        self.image = image
        self.locked = 0
        self.restore_calls = 0

    def lock(self):
        self.locked += 1

    def unlock(self):
        self.locked -= 1

    async def inspect(self, _device):
        return {"androidStatus": "stopped"}

    async def backup_volume(self, _device):
        return self.payload

    async def restore_volume(self, _device, data):
        assert data == self.payload
        self.restore_calls += 1

    async def environment(self):
        return {
            "available": True,
            "platformSupported": True,
            "runtimeId": "test",
            "images": [{"id": self.image}],
        }

    def new_device(self, config):
        return {
            **config,
            "control": "idle",
            "ownerRunId": None,
            "androidStatus": "unknown",
            "generation": 0,
        }

    async def manage(self, device, _request, _stage, save):
        device["androidStatus"] = "stopped"
        save()
