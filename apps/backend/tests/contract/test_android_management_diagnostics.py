from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import (
    android_management_internal_router,
    android_management_router,
)
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.diagnostics import EnvironmentCheckService


class _Resources:
    def __init__(self):
        self.items = {}

    def list(self, kind):
        return [value for (stored_kind, _), value in self.items.items() if stored_kind == kind]

    def save(self, kind, item):
        self.items[(kind, item["id"])] = item


def _client(resources):
    runtime = SimpleNamespace(
        environment=lambda: {
            "available": True,
            "platformSupported": True,
            "runtimeId": "test",
            "images": [],
        }
    )
    devices = SimpleNamespace(management=SimpleNamespace(workspace_identity="owned"))
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(
        android_management_router(
            EnvironmentCheckService(runtime), devices=devices, resources=resources
        )
    )
    return TestClient(app)


def test_diagnostics_request_is_idempotent_and_workspace_scoped():
    resources = _Resources()
    with _client(resources) as client:
        body = {"requestId": "diag-1", "deviceIds": ["d1"]}
        first = client.post("/api/v1/android/management/diagnostics", json=body)
        replay = client.post("/api/v1/android/management/diagnostics", json=body)
        conflict = client.post(
            "/api/v1/android/management/diagnostics",
            json={"requestId": "diag-1", "deviceIds": ["d2"]},
        )

    assert first.status_code == replay.status_code == 202
    assert first.json() == replay.json()
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "ANDROID_REQUEST_CONFLICT"
    records = resources.list("diagnostic")
    assert len(records) == 1
    assert records[0]["workspaceId"] == "owned"


def test_diagnostic_download_is_host_authenticated_workspace_scoped_and_expiring():
    resources = _Resources()
    resources.save("diagnostic", {
        "id": "diag-ready", "requestId": "diag-ready", "workspaceId": "owned", "state": "ready",
        "payload": {"environment": {"checks": {"platform": {"status": "pass"}}}},
        "createdAt": datetime.now(UTC).isoformat(),
        "expiresAt": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    })
    resources.save("diagnostic", {
        "id": "diag-expired", "requestId": "diag-expired", "workspaceId": "owned", "state": "ready",
        "payload": {}, "createdAt": datetime.now(UTC).isoformat(),
        "expiresAt": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    })
    app = FastAPI()
    install_error_handlers(app)
    app.state.config = SimpleNamespace(host_token="host-token")
    app.include_router(android_management_internal_router(resources, lambda: "owned"))

    with TestClient(app) as client:
        unauthorized = client.get("/internal/android/management/diagnostics/diag-ready")
        wrong_token = client.get("/internal/android/management/diagnostics/diag-ready", headers={"x-autoflow-host-token": "wrong"})
        downloaded = client.get("/internal/android/management/diagnostics/diag-ready", headers={"x-autoflow-host-token": "host-token"})
        expired = client.get("/internal/android/management/diagnostics/diag-expired", headers={"x-autoflow-host-token": "host-token"})

    assert unauthorized.status_code == 401
    assert wrong_token.status_code == 401
    assert downloaded.status_code == 200
    assert downloaded.json()["payload"]["environment"]["checks"]["platform"]["status"] == "pass"
    assert expired.status_code == 410
    assert expired.json()["error"]["code"] == "ANDROID_DIAGNOSTIC_EXPIRED"


def test_diagnostics_advanced_logs_require_single_request_consent_and_redact_messages():
    resources = _Resources()
    now = datetime.now(UTC).timestamp()

    class Runtime:
        workspace_id = "runtime-owned"

        async def environment(self):
            return {"available": True, "platformSupported": True, "runtimeId": "test", "images": []}

        async def collect_diagnostic_logs(self, device, *, window_seconds, max_bytes):
            assert device["deviceId"] == "d1"
            assert window_seconds == 300 and max_bytes == 65536
            return f"{now:.3f}  1  2 E SafeTag: account=private@example.com password=hunter2\n".encode()

    runtime = Runtime()
    devices = SimpleNamespace(runtime=runtime, repository=SimpleNamespace(list=lambda: [
        {"deviceId": "d1", "workspaceId": "runtime-owned", "deleted": False},
        {"deviceId": "foreign", "workspaceId": "elsewhere", "deleted": False},
    ]), management=SimpleNamespace(workspace_identity="owned"))
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), devices=devices, resources=resources))

    with TestClient(app) as client:
        denied = client.post("/api/v1/android/management/diagnostics", json={"requestId": "diag-denied", "deviceIds": ["d1"], "includeAdvancedLogs": True})
        foreign = client.post("/api/v1/android/management/diagnostics", json={"requestId": "diag-foreign", "deviceIds": ["foreign"], "includeAdvancedLogs": True, "advancedLogsConsent": True})
        response = client.post("/api/v1/android/management/diagnostics", json={"requestId": "diag-advanced", "deviceIds": ["d1"], "includeAdvancedLogs": True, "advancedLogsConsent": True})

    assert denied.status_code == 422
    assert foreign.status_code == 403
    assert response.status_code == 202
    advanced = response.json()["payload"]["advancedLogs"]
    assert advanced["status"] == "ready"
    assert advanced["windowSeconds"] == 300
    assert advanced["devices"][0]["entries"] == [{"at": round(now, 3), "priority": "E"}]
    assert "private@example.com" not in str(response.json())
    assert "hunter2" not in str(resources.items)


def test_diagnostic_snapshot_uses_runtime_ownership_and_excludes_unapproved_fields():
    import json

    class Runtime:
        workspace_id = "runtime-workspace-hash"

        async def environment(self):
            return {"available": True, "platformSupported": True, "runtimeId": "lima",
                    "newSecretField": "private-token", "message": "private-token",
                    "checks": {"adb": {"status": "fail", "code": "ANDROID_ADB_UNKNOWN",
                                        "message": "password=private-token"}}}

    own = {"deviceId": "d1", "workspaceId": "runtime-workspace-hash", "androidStatus": "ready",
           "name": "private-token", "creationConfig": {"newSecretField": "private-token"},
           "operation": {"state": "failed", "error": "password=private-token"}}
    devices = SimpleNamespace(runtime=Runtime(), management=SimpleNamespace(workspace_identity="/workspace/path"),
                              repository=SimpleNamespace(list=lambda: [own, dict(own, deviceId="foreign", workspaceId="other"),
                                                                       dict(own, deviceId="unowned", workspaceId=None)]))
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(devices.runtime), devices=devices, resources=_Resources()))
    with TestClient(app) as client:
        response = client.post("/api/v1/android/management/diagnostics", json={"requestId": "scoped-diagnostics"})
    assert response.status_code == 202
    payload = response.json()["payload"]
    assert [item["deviceId"] for item in payload["devices"]] == ["d1"]
    assert "private-token" not in json.dumps(payload)
    assert "legacy" not in payload["environment"]
    assert payload["environment"]["checks"]["adb"] == {"status": "fail", "code": "ANDROID_ADB_UNKNOWN"}
