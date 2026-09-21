from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.diagnostics import EnvironmentCheckService
from autoflow.domain.android.ports import AndroidError


def test_template_archive_requires_matching_revision() -> None:
    image_id = "sha256:" + "a" * 64
    profile = {"id": "22222222-2222-4222-8222-222222222222", "revision": 2, "name": "标准", "imageId": image_id, "width": 720, "height": 1280, "dpi": 320, "cpu": 1, "memoryMb": 1536, "locale": "zh-CN", "timezone": "Asia/Shanghai", "shellRoot": "unknown", "applicationRoot": "unknown"}
    resources = _Resources(profile)
    runtime = type("Runtime", (), {"environment": lambda _self: {"available": True, "platformSupported": True, "runtimeId": "test", "images": []}})()
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), profiles=resources))

    with TestClient(app) as client:
        conflict = client.post("/api/v1/android/management/profiles/22222222-2222-4222-8222-222222222222/archive", json={"requestId": "r1", "expectedRevision": 1})
        archived = client.post("/api/v1/android/management/profiles/22222222-2222-4222-8222-222222222222/archive", json={"requestId": "r2", "expectedRevision": 2})

    assert conflict.status_code == 409
    assert archived.status_code == 200
    assert resources.get("profile", "22222222-2222-4222-8222-222222222222")["archived"] is True


class _Resources:
    def __init__(self, profile):
        self.profile = profile

    def get(self, kind, identifier):
        if kind != "profile" or identifier != self.profile["id"]:
            raise AndroidError("NOT_FOUND", "not found", 404)
        return dict(self.profile)

    def save(self, kind, value):
        assert kind == "profile"
        self.profile = dict(value)
