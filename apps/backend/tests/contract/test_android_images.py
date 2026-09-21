from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.diagnostics import EnvironmentCheckService


def test_image_pull_rejects_command_options_before_provider_access() -> None:
    runtime = type("Runtime", (), {"environment": lambda _self: {"available": True, "platformSupported": True, "runtimeId": "test", "images": []}})()
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), images=object()))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/android/management/image-pulls",
            json={"requestId": "pull-1", "reference": "repo:tag\n--privileged"},
        )

    assert response.status_code == 422
