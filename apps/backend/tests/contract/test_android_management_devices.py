from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.diagnostics import EnvironmentCheckService


class _Runtime:
    async def environment(self):
        return {"available": True, "platformSupported": True, "runtimeId": "lima"}

    async def inspect(self, _device):
        raise AssertionError("management list must use observations, not inspect inline")


class _Devices:
    runtime = _Runtime()

    def __init__(self):
        self.repository = type("Repository", (), {"list": lambda _self: [{
            "deviceId": "11111111-1111-4111-8111-111111111111", "name": "设备", "generation": 2,
            "androidStatus": "ready", "control": "idle", "ownerRunId": None,
            "profileId": "22222222-2222-4222-8222-222222222222", "dataRetained": False,
            "deleted": False, "creationConfig": {"imageId": "sha256:" + "a" * 64},
        }]})()


def test_management_device_list_is_a_snapshot_page_and_does_not_inspect_inline():
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(_Devices().runtime), devices=_Devices()))
    with TestClient(app) as client:
        response = client.get("/api/v1/android/management/devices?limit=50")
    assert response.status_code == 200
    assert response.json()["items"][0]["deviceId"].startswith("1111")
    assert response.json()["nextCursor"] is None


def test_management_device_profile_filter_uses_public_camel_case_parameter():
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(_Devices().runtime), devices=_Devices()))
    with TestClient(app) as client:
        response = client.get("/api/v1/android/management/devices?profileId=another-profile")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


def test_manual_console_owner_is_projected_as_manual_session():
    class _ManualDevices:
        runtime = _Runtime()

        def __init__(self):
            self.repository = type("Repository", (), {"list": lambda _self: [{
                "deviceId": "33333333-3333-4333-8333-333333333333",
                "name": "手动设备",
                "generation": 3,
                "androidStatus": "ready",
                "control": "manual",
                "ownerRunId": "console-session",
                "deleted": False,
                "creationConfig": {},
            }]})()

    app = FastAPI()
    install_error_handlers(app)
    devices = _ManualDevices()
    app.include_router(android_management_router(EnvironmentCheckService(devices.runtime), devices=devices))

    with TestClient(app) as client:
        response = client.get("/api/v1/android/management/devices")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["owner"] == {"kind": "manualSession", "id": "console-session"}
    assert "return_to_console" in item["allowedActions"]
    assert "verify" not in item["allowedActions"]


def test_management_list_fails_closed_before_first_observation() -> None:
    class _Observations:
        def get(self, _device_id):
            return None

    app = FastAPI()
    install_error_handlers(app)
    devices = _Devices()
    app.include_router(
        android_management_router(
            EnvironmentCheckService(devices.runtime),
            devices=devices,
            observations=_Observations(),
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/android/management/devices")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["runtimeState"] == "unknown"
    assert item["stale"] is True
    assert "start" not in item["allowedActions"]
