from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.diagnostics import EnvironmentCheckService


def test_bulk_routes_project_persistent_internal_fields() -> None:
    record = {
        "id": "batch-1",
        "requestId": "request-1",
        "action": "stop",
        "deleteData": False,
        "state": "running",
        "items": [{"deviceId": "device-1", "expectedRevision": 1, "state": "queued"}],
        "createdAt": datetime.now(UTC).isoformat(),
        "workspaceIdentity": "/private/tmp/isolated-workspace",
        "actionReceipts": {},
    }

    class Bulk:
        def create(self, *_args):
            return record

        def run(self, *_args):
            return record

        def get(self, *_args):
            return record

        def action(self, *_args):
            return record

        async def verify(self, *_args):
            return record

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), bulk=Bulk()))

    with TestClient(app, raise_server_exceptions=False) as client:
        created = client.post("/api/v1/android/management/bulk-operations", json={
            "requestId": "request-1", "action": "stop", "items": [{"deviceId": "device-1", "expectedRevision": 1}],
        })
        fetched = client.get("/api/v1/android/management/bulk-operations/batch-1")
        acted = client.post("/api/v1/android/management/bulk-operations/batch-1/actions", json={"requestId": "action-1", "action": "cancelPending"})
        verified = client.post("/api/v1/android/management/bulk-operations/batch-1/actions", json={"requestId": "action-2", "action": "verify"})

    assert [created.status_code, fetched.status_code, acted.status_code, verified.status_code] == [202, 200, 200, 200]
    assert all("workspaceIdentity" not in response.json() for response in (created, fetched, acted, verified))
