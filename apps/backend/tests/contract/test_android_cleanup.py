from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.cleanup import CleanupService
from autoflow.application.android.diagnostics import EnvironmentCheckService


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
            EnvironmentCheckService(runtime),
            devices=devices,
            cleanup=CleanupService(resources),
        )
    )
    return TestClient(app)


def test_cleanup_contract_exposes_frozen_summary_and_rejects_replay():
    resources = [
        {
            "id": "owned",
            "workspaceId": "owned",
            "revision": 4,
            "size": 9,
            "path": "/private/owned.tar",
            "sha256": "a" * 64,
        },
        {"id": "foreign", "workspaceId": "outside", "size": 11},
    ]
    with _client(resources) as client:
        response = client.post(
            "/api/v1/android/management/cleanup/previews",
            json={"resourceIds": ["owned", "foreign"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert [item["id"] for item in body["items"]] == ["owned"]
        assert body["previewId"] != body["confirmationDigest"]
        item = body["items"][0]
        assert item["revision"] == 4
        assert item["workspaceId"] == "owned"
        assert item["summary"]["sha256"] == "a" * 64
        assert item["fingerprint"]
        assert "/private" not in str(item)

        cleanup = client.post(
            "/api/v1/android/management/cleanup",
            json={"requestId": "cleanup-1", "previewId": body["previewId"], "confirmationDigest": body["confirmationDigest"]},
        )
        assert cleanup.status_code == 200
        assert cleanup.json()["state"] == "accepted"

        replay = client.post(
            "/api/v1/android/management/cleanup",
            json={"requestId": "cleanup-1", "confirmationDigest": body["confirmationDigest"]},
        )
        assert replay.status_code == 409
        assert replay.json()["error"]["code"] == "ANDROID_CLEANUP_CHANGED"

        mismatch = client.post(
            "/api/v1/android/management/cleanup",
            json={"requestId": "cleanup-2", "previewId": "foreign-preview", "confirmationDigest": body["confirmationDigest"]},
        )
        assert mismatch.status_code == 409
        assert mismatch.json()["error"]["code"] == "ANDROID_CLEANUP_CHANGED"


def test_cleanup_inventory_is_read_only_and_scoped_to_the_current_workspace():
    resources = [{"id": "staging:partial", "workspaceId": "owned", "kind": "backup-staging", "size": 12}, {"id": "foreign", "workspaceId": "other"}]
    with _client(resources) as client:
        response = client.get("/api/v1/android/management/cleanup/resources")
        assert response.status_code == 200
        assert [item["id"] for item in response.json()["items"]] == ["staging:partial"]
        assert response.json()["items"][0]["fingerprint"]
        assert len(resources) == 2
