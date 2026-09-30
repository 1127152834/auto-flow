from __future__ import annotations

import asyncio
import io
import tarfile
from concurrent.futures import CancelledError
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.backups import AndroidBackupService
from autoflow.application.android.devices import AndroidDeviceService
from autoflow.application.android.diagnostics import EnvironmentCheckService
from autoflow.domain.android.ports import AndroidDiskPreflightCancelled, AndroidError
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.android_operations import (
    SqlAlchemyAndroidOperationRepository,
)
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.providers.android.mac_runtime import MacAndroidRuntime

IMAGE = "sha256:" + "b" * 64


@pytest.mark.asyncio
async def test_restore_streams_validated_archive_without_loading_bytes(tmp_path: Path) -> None:
    class StreamRuntime(_Runtime):
        async def restore_volume(self, _device, _data):
            raise AssertionError("restore should use the file stream")

        async def restore_volume_from_path(self, _device, path):
            assert path.read_bytes() == self.payload
            self.restore_calls += 1

    sessions = _sessions(tmp_path)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    repository = SqlAlchemyDeviceRepository(sessions)
    runtime = StreamRuntime(_tar(b"source"), IMAGE)
    devices = AndroidDeviceService(repository, runtime)
    devices.management.workspace_identity = str(tmp_path.resolve())
    backups = AndroidBackupService(resources, tmp_path, operations)
    source = {"deviceId": "source", "imageId": IMAGE, "control": "idle", "ownerRunId": None, "generation": 1,
              "creationConfig": {"width": 720, "height": 1280, "dpi": 320, "cpu": 1, "memoryMb": 1536}}
    repository.save(source)
    backup = await backups.create_with_runtime(source, None, runtime, "backup-stream", 1)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), operations, backups=backups, devices=devices))

    with TestClient(app) as client:
        response = client.post(f"/api/v1/android/management/backups/{backup['id']}/restore", json={"requestId": "restore-stream", "newName": "stream copy"})

    assert response.status_code == 202, response.text
    assert runtime.restore_calls == 1
    assert runtime.disk_checks == [False]
    sessions.dispose()


@pytest.mark.asyncio
async def test_restore_does_not_inherit_source_disk_confirmation_and_preserves_known_rejection(tmp_path: Path) -> None:
    sessions = _sessions(tmp_path)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    repository = SqlAlchemyDeviceRepository(sessions)
    runtime = _Runtime(_tar(b"source"), IMAGE)
    devices = AndroidDeviceService(repository, runtime)
    devices.management.workspace_identity = str(tmp_path.resolve())
    backups = AndroidBackupService(resources, tmp_path, operations)
    source = {"deviceId": "source", "imageId": IMAGE, "control": "idle", "ownerRunId": None, "generation": 1,
              "creationConfig": {"width": 720, "height": 1280, "dpi": 320, "cpu": 1, "memoryMb": 1536, "allowUnknownDiskEstimate": True}}
    repository.save(source)
    backup = await backups.create_with_runtime(source, None, runtime, "backup-source", 1)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), operations, backups=backups, devices=devices))
    runtime.disk_error = AndroidError("ANDROID_DISK_ESTIMATE_UNKNOWN", "最终占用未知", 409)

    with TestClient(app) as client:
        rejected = client.post(f"/api/v1/android/management/backups/{backup['id']}/restore", json={"requestId": "unconfirmed", "newName": "copy"})
        replay_conflict = client.post(f"/api/v1/android/management/backups/{backup['id']}/restore", json={"requestId": "unconfirmed", "newName": "copy", "allowUnknownDiskEstimate": True})

    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["error"]["code"] == "ANDROID_DISK_ESTIMATE_UNKNOWN"
    assert replay_conflict.status_code == 409
    assert operations.by_request(str(tmp_path.resolve()), "unconfirmed").result_code == "ANDROID_DISK_ESTIMATE_UNKNOWN"
    assert runtime.restore_calls == 0
    target_id = operations.by_request(str(tmp_path.resolve()), "unconfirmed").target_id
    assert "allowUnknownDiskEstimate" not in repository.get(target_id)["creationConfig"]
    assert runtime.disk_checks == [False]
    assert repository.get("source")["creationConfig"]["allowUnknownDiskEstimate"] is True
    sessions.dispose()


@pytest.mark.asyncio
async def test_cancelled_restore_disk_recheck_keeps_created_target_unknown(tmp_path: Path) -> None:
    sessions = _sessions(tmp_path)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    repository = SqlAlchemyDeviceRepository(sessions)
    runtime = _Runtime(_tar(b"source"), IMAGE)
    devices = AndroidDeviceService(repository, runtime)
    devices.management.workspace_identity = str(tmp_path.resolve())
    backups = AndroidBackupService(resources, tmp_path, operations)
    source = {"deviceId": "source", "imageId": IMAGE, "control": "idle", "ownerRunId": None, "generation": 1,
              "creationConfig": {"width": 720, "height": 1280, "dpi": 320, "cpu": 1, "memoryMb": 1536}}
    repository.save(source)
    backup = await backups.create_with_runtime(source, None, runtime, "backup-source", 1)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), operations, backups=backups, devices=devices))
    runtime.disk_error = AndroidDiskPreflightCancelled()

    with TestClient(app) as client, pytest.raises(CancelledError):
        client.post(f"/api/v1/android/management/backups/{backup['id']}/restore", json={"requestId": "cancel-recheck", "newName": "copy", "allowUnknownDiskEstimate": True})

    operation = operations.by_request(str(tmp_path.resolve()), "cancel-recheck")
    assert operation.state == "needs_verification"
    assert repository.get(operation.target_id)["restoreState"] == "pending"
    assert runtime.restore_calls == 0
    sessions.dispose()


@pytest.mark.asyncio
async def test_restore_accepts_cached_custom_image_missing_from_default_environment_list(tmp_path: Path) -> None:
    sessions = _sessions(tmp_path)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    repository = SqlAlchemyDeviceRepository(sessions)
    runtime = _Runtime(_tar(b"source"), IMAGE)
    devices = AndroidDeviceService(repository, runtime)
    devices.management.workspace_identity = str(tmp_path.resolve())
    backups = AndroidBackupService(resources, tmp_path, operations)
    source = {
        "deviceId": "source-device", "name": "source", "imageId": IMAGE,
        "control": "idle", "ownerRunId": None, "generation": 1,
        "creationConfig": {"width": 720, "height": 1280, "dpi": 320, "cpu": 2, "memoryMb": 1536},
    }
    repository.save(source)
    backup = await backups.create_with_runtime(source, None, runtime, "backup-custom-image", 1)
    original_environment = runtime.environment

    async def only_default_images():
        result = await original_environment()
        result["images"] = []
        return result

    runtime.environment = only_default_images

    async def inspect_custom_image(reference: str):
        assert reference == IMAGE
        return {"imageId": IMAGE, "architecture": "arm64", "os": "linux"}

    runtime.inspect_image = inspect_custom_image
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), operations, backups=backups, devices=devices))
    with TestClient(app) as client:
        response = client.post(f"/api/v1/android/management/backups/{backup['id']}/restore", json={"requestId": "restore-custom", "newName": "copy"})

    assert response.status_code == 202, response.text
    assert response.json()["state"] == "restored"
    assert runtime.restore_calls == 1
    sessions.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "commit_ack", "commit_before", "copy", "cancel"])
async def test_restore_request_id_creates_one_isolated_target(tmp_path: Path, monkeypatch, fault) -> None:
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
    original_transition = operations.transition_with_device

    def faulty_transition(*args):
        if args[2] == "succeeded" and args[4].get("restoreState") == "restored":
            if fault == "commit_before":
                raise OSError("database unavailable before commit")
            result = original_transition(*args)
            if fault == "commit_ack":
                raise OSError("committed but acknowledgement lost")
            return result
        return original_transition(*args)

    monkeypatch.setattr(operations, "transition_with_device", faulty_transition)
    if fault in {"copy", "cancel"}:
        async def interrupted_copy(_device, _data):
            runtime.restore_calls += 1
            if fault == "cancel":
                raise asyncio.CancelledError
            raise TimeoutError("partial write, connection lost")
        monkeypatch.setattr(runtime, "restore_volume", interrupted_copy)
    body = {"requestId": "restore-request", "newName": "copy"}
    with TestClient(app) as client:
        if fault == "cancel":
            with pytest.raises(CancelledError):
                client.post(f"/api/v1/android/management/backups/{backup['id']}/restore", json=body)
        else:
            first = client.post(
                f"/api/v1/android/management/backups/{backup['id']}/restore", json=body
            )
        second = client.post(
            f"/api/v1/android/management/backups/{backup['id']}/restore", json=body
        )

    if fault in {"copy", "commit_before", "cancel"}:
        if fault != "cancel":
            assert first.status_code == 503, first.text
        assert second.status_code == 409, second.text
        operation = operations.by_request(str(tmp_path.resolve()), "restore-request")
        assert operation.state == "needs_verification"
        target = repository.get(operation.target_id)
        assert target["restoreState"] == "pending"
        assert target["control"] == "recovery_required"
        # Reconstruct management and verify runtime recovery cannot publish restored data.
        devices.management.operate(target["deviceId"], {"requestId": "recover", "action": "recover", "deleteData": False})
        await devices.management.task
        target = repository.get(target["deviceId"])
        assert target["control"] == "idle"
        if fault in {"copy", "commit_before"}:
            with pytest.raises(AndroidError) as rejected:
                await backups.restore_data(backup["id"], target, runtime)
            assert rejected.value.code == "ANDROID_RESTORE_TARGET_INVALID"
        with pytest.raises(AndroidError, match="恢复"):
            devices.management.operate(target["deviceId"], {"requestId": "start", "action": "start", "deleteData": False})
        with pytest.raises(AndroidError, match="恢复"):
            repository.claim(target["deviceId"], "console")
        with pytest.raises(AndroidError, match="恢复"):
            await backups.create_with_runtime(target, None, runtime)
        assert repository.get(source["deviceId"]) == source
        assert runtime.restore_calls == 1
        sessions.dispose()
        return
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
@pytest.mark.parametrize("change", ["missing", "generation", "volume", "deleted", "control", "completed", "no_operations"])
async def test_direct_restore_checks_persisted_target_and_operation_before_writing(tmp_path: Path, change: str) -> None:
    sessions = _sessions(tmp_path)
    resources = AndroidResourceRepository(sessions)
    repository = SqlAlchemyDeviceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    runtime = _Runtime(_tar(b"source"), IMAGE)
    backups = AndroidBackupService(resources, tmp_path, operations)
    source = {"deviceId": "source", "imageId": IMAGE, "control": "idle"}
    backup = await backups.create_with_runtime(source, {"androidStatus": "stopped"}, runtime)
    workspace = str(tmp_path.resolve())
    target = {"deviceId": "target", "workspaceId": "workspace", "imageId": IMAGE, "volumeId": "target-volume", "generation": 1, "androidStatus": "stopped", "control": "idle", "restoreState": "pending", "restoreRequestId": "restore-request", "restoreBackupId": backup["id"], "creationConfig": {"restoreRequestId": "restore-request", "restoreBackupId": backup["id"], "start": False}}
    operation = operations.accept(workspace, "restore-request", "target", "restore", "digest", {"backupId": backup["id"], "newDeviceId": "target"})
    operations.transition(operation.operation_id, "queued", "running", {})
    target["restoreOperationId"] = operation.operation_id
    if change != "missing":
        stored = dict(target)
        if change == "generation":
            stored["generation"] = 2
        elif change == "volume":
            stored["volumeId"] = "other-volume"
        elif change == "deleted":
            stored["deleted"] = True
        elif change == "control":
            stored["control"] = "manual"
        repository.save(stored)
    if change == "completed":
        operations.transition(operation.operation_id, "running", "needs_verification", {})
    elif change == "no_operations":
        backups.operations = None

    with pytest.raises(AndroidError) as rejected:
        await backups.restore_data(backup["id"], target, runtime)
    assert rejected.value.code == "ANDROID_RESTORE_TARGET_INVALID"
    assert runtime.restore_calls == 0
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("probe_error", "expected_state", "expected_code", "http_status"),
    [
        (OSError("runtime probe lost"), "needs_verification", "RESTORE_RESULT_UNKNOWN", 503),
        (AndroidError("ANDROID_COMMAND_FAILED", "image inventory failed", 502), "failed", "ANDROID_COMMAND_FAILED", 502),
    ],
)
async def test_restore_environment_failure_records_terminal_preflight_state(tmp_path: Path, probe_error, expected_state, expected_code, http_status) -> None:
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
    backup = await backups.create_with_runtime(source, None, runtime, "backup-request", 1)
    runtime.environment_error = probe_error

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
    body = {"requestId": "restore-environment-failure", "newName": "copy"}
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            f"/api/v1/android/management/backups/{backup['id']}/restore", json=body
        )

    assert response.status_code == http_status, response.text
    operation = operations.by_request(str(tmp_path.resolve()), body["requestId"])
    assert operation.state == expected_state
    assert operation.result_code == expected_code
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
        self.environment_error: BaseException | None = None
        self.disk_error: BaseException | None = None
        self.disk_checks: list[bool] = []

    async def require_vm_disk_space(self, *, allow_unknown_disk_estimate: bool = False):
        self.disk_checks.append(allow_unknown_disk_estimate)
        if self.disk_error is not None:
            raise self.disk_error

    def lock(self):
        self.locked += 1

    def unlock(self):
        self.locked -= 1

    async def inspect(self, _device):
        return {"androidStatus": "stopped"}

    async def estimate_backup_bytes(self, _device):
        return len(self.payload)

    async def backup_volume(self, _device):
        return self.payload

    async def restore_volume(self, _device, data):
        assert data == self.payload
        self.restore_calls += 1

    async def environment(self):
        if self.environment_error:
            raise self.environment_error
        return {
            "available": True,
            "platformSupported": True,
            "runtimeId": "test",
            "images": [{"id": self.image}],
        }

    def new_device(self, config):
        # Match the production adapter: restoration metadata is the application owner's responsibility.
        return MacAndroidRuntime(Path("/runtime"), Path("/workspace")).new_device(config)

    async def manage(self, device, _request, _stage, save):
        device["androidStatus"] = "stopped"
        save()
