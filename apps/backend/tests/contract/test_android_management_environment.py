from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import android_management_router
from autoflow.application.android.diagnostics import EnvironmentCheckService


@pytest.mark.asyncio
async def test_environment_check_is_read_only_and_keeps_unknown_checks_explicit() -> None:
    runtime = AsyncMock()
    runtime.environment.return_value = {
        "available": False,
        "platformSupported": False,
        "runtimeId": "autoflow-redroid",
        "message": "不支持",
        "images": [],
    }

    result = await EnvironmentCheckService(runtime).check("check-1")

    assert result.runtime_id == "autoflow-redroid"
    assert result.checks["platform"].status == "unsupported"
    assert result.checks["adb"].status == "unknown"
    runtime.manage.assert_not_called()


def test_environment_route_exposes_capabilities_without_workflow_entrypoints() -> None:
    runtime = AsyncMock()
    runtime.environment.return_value = {
        "available": False,
        "platformSupported": False,
        "runtimeId": "autoflow-redroid",
        "message": "不支持",
        "images": [],
    }
    app = FastAPI()
    app.include_router(android_management_router(EnvironmentCheckService(runtime)))

    with TestClient(app) as client:
        response = client.get("/api/v1/android/management/environment")
        capabilities = client.get("/api/v1/android/management/capabilities")

    assert response.status_code == 200
    assert response.json()["checks"]["platform"]["status"] == "unsupported"
    assert capabilities.json()["workflow"] is False
