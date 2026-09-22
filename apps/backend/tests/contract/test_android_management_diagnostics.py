from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import android_management_router
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
