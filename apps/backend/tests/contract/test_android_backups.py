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
