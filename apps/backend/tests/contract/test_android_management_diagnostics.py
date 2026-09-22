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


def test_diagnostics_advanced_logs_are_explicitly_unsupported():
    resources = _Resources()
    runtime = SimpleNamespace(
        environment=lambda: {
            "available": False,
            "platformSupported": None,
            "runtimeId": "test",
            "images": [],
        }
    )
    devices = SimpleNamespace(management=SimpleNamespace(workspace_identity="owned"))
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), devices=devices, resources=resources))

    with TestClient(app) as client:
        response = client.post("/api/v1/android/management/diagnostics", json={"requestId": "diag-advanced", "includeAdvancedLogs": True})

    assert response.status_code == 202
    assert response.json()["payload"]["advancedLogs"]["status"] == "unsupported"
    assert response.json()["payload"]["advancedLogs"]["code"] == "ANDROID_DIAGNOSTICS_ADVANCED_LOGS_UNSUPPORTED"
