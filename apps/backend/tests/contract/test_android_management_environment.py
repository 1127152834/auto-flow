from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import android_management_router
from autoflow.application.android.diagnostics import EnvironmentCheckService


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [OSError("socket closed"), TimeoutError("probe timed out"), RuntimeError("probe crashed")])
async def test_environment_probe_failure_returns_stable_unknown_checks(error: Exception) -> None:
    runtime = AsyncMock()
    runtime.environment.side_effect = error

    result = await EnvironmentCheckService(runtime).check("check-failed")

    assert result.runtime_id == "unknown"
    assert set(result.checks) == {"platform", "adb", "lima", "ssh", "scrcpy", "vm", "docker", "binder", "images", "capacity", "disk"}
    assert {check.status for check in result.checks.values()} == {"unknown"}
    assert {check.code for check in result.checks.values()} == {"ANDROID_ENVIRONMENT_UNKNOWN"}
    assert result.capabilities == {"management": False, "control": False, "images": "unknown", "workflow": False}


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


def test_environment_route_keeps_probe_failure_reviewable() -> None:
    runtime = AsyncMock()
    runtime.environment.side_effect = OSError("socket closed")
    app = FastAPI()
    app.include_router(android_management_router(EnvironmentCheckService(runtime)))

    with TestClient(app) as client:
        response = client.get("/api/v1/android/management/environment")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["platformSupported"] is None
    assert body["checks"]["platform"] == {
        "status": "unknown",
        "code": "ANDROID_ENVIRONMENT_UNKNOWN",
        "message": "运行环境探测失败，请稍后重试",
        "action": None,
    }


def test_capabilities_report_configured_bulk_service() -> None:
    runtime = AsyncMock()
    runtime.environment.return_value = {
        "available": True,
        "platformSupported": True,
        "runtimeId": "autoflow-redroid",
        "message": "可用",
        "images": [{"id": "sha256:" + "a" * 64}],
    }
    app = FastAPI()
    app.include_router(android_management_router(EnvironmentCheckService(runtime), bulk=object()))

    with TestClient(app) as client:
        capabilities = client.get("/api/v1/android/management/capabilities")

    assert capabilities.status_code == 200
    assert capabilities.json()["bulk"] is True
    assert capabilities.json()["backups"] is False
