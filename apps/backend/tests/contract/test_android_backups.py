import io
import tarfile

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.backups import AndroidBackupService
from autoflow.application.android.diagnostics import EnvironmentCheckService


def test_management_backup_requires_stopped_observation(tmp_path) -> None:
    device = {"deviceId": "device-1", "imageId": "sha256:" + "a" * 64, "control": "idle", "ownerRunId": None, "creationConfig": {}}
    devices = _Devices(device)
    backups = AndroidBackupService(_Resources(), tmp_path)
    runtime = type("Runtime", (), {"environment": lambda _self: {"available": True, "platformSupported": True, "runtimeId": "test", "images": []}})()
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), backups=backups, devices=devices))

    with TestClient(app) as client:
        response = client.post("/api/v1/android/management/backups", json={"requestId": "r1", "deviceId": "device-1", "expectedRevision": 1})

    assert response.status_code == 409


def test_management_backup_requires_runtime_volume_adapter(tmp_path) -> None:
    device = {"deviceId": "device-1", "imageId": "sha256:" + "a" * 64, "control": "idle", "ownerRunId": None, "creationConfig": {}}
    backups = AndroidBackupService(_Resources(), tmp_path)
    devices = _Devices(device)
    devices.runtime.inspect = _stopped
    runtime = type("Runtime", (), {"environment": lambda _self: {"available": True, "platformSupported": True, "runtimeId": "test", "images": []}})()
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), backups=backups, devices=devices))

    with TestClient(app) as client:
        response = client.post("/api/v1/android/management/backups", json={"requestId": "r1", "deviceId": "device-1", "expectedRevision": 1})

    assert response.status_code == 503


def test_management_backup_route_returns_public_backup_contract(tmp_path) -> None:
    device = {
        "deviceId": "device-1",
        "imageId": "sha256:" + "a" * 64,
        "control": "idle",
        "ownerRunId": None,
        "generation": 1,
        "creationConfig": {"width": 720, "height": 1280, "dpi": 320, "cpu": 2, "memoryMb": 1024},
    }
    runtime = _BackupRuntime(_archive())
    devices = _BackupDevices(device, runtime)
    resources = _BackupResources()
    backups = AndroidBackupService(resources, tmp_path)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), backups=backups, devices=devices))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/android/management/devices/device-1/backups",
            json={"requestId": "backup-route", "deviceId": "device-1", "expectedRevision": 2},
        )

    assert response.status_code == 201, response.text
    assert set(response.json()) == {"id", "deviceId", "imageId", "formatVersion", "sha256", "bytes", "createdAt", "state"}
    assert response.json()["state"] == "available"


def test_backup_rejects_revision_frozen_before_first_generation_change(tmp_path) -> None:
    device = {"deviceId": "device-1", "generation": 1, "control": "idle", "ownerRunId": None}
    runtime = _BackupRuntime(_archive())
    devices = _BackupDevices(device, runtime)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), backups=AndroidBackupService(_BackupResources(), tmp_path), devices=devices))

    with TestClient(app) as client:
        response = client.post("/api/v1/android/management/devices/device-1/backups", json={"requestId": "stale-backup", "deviceId": "device-1", "expectedRevision": 1})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ANDROID_REVISION_CONFLICT"


async def _stopped(_device):
    return {"androidStatus": "stopped"}


class _Devices:
    def __init__(self, device):
        self.device = device
        self.runtime = type("Runtime", (), {"inspect": self.inspect})()

    def get(self, identifier):
        assert identifier == self.device["deviceId"]
        return dict(self.device)

    async def inspect(self, _device):
        return {"androidStatus": "ready"}


class _Resources:
    def list(self, _kind):
        return []

    def save(self, _kind, _item):
        raise AssertionError("running device must not publish a backup")


class _BackupResources:
    def __init__(self):
        self.items = []

    def list(self, _kind):
        return list(self.items)

    def save(self, _kind, item):
        self.items.append(item)


class _BackupDevices:
    def __init__(self, device, runtime):
        self.device = device
        self.runtime = runtime

    def get(self, identifier):
        assert identifier == self.device["deviceId"]
        return dict(self.device)


class _BackupRuntime:
    def __init__(self, payload):
        self.payload = payload

    def lock(self):
        pass

    def unlock(self):
        pass

    async def inspect(self, _device):
        return {"androidStatus": "stopped"}

    async def backup_volume(self, _device):
        return self.payload

    async def environment(self):
        return {"available": True, "platformSupported": True, "runtimeId": "test", "images": []}


def _archive():
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        info = tarfile.TarInfo("data/settings.json")
        content = b"{}"
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    return payload.getvalue()
