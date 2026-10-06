import base64
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from autoflow.adapters.http.android_ai_tests import android_ai_tests_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android_ai_tests import AiTestRepository
from autoflow.infrastructure.database.models import Base

BASE = "/api/v1/android/ai-tests"


class FakeService:
    def __init__(self, repository: AiTestRepository, root: Path) -> None:
        self.repository, self.artifacts_root = repository, root
        self.calls: list[tuple[str, Any]] = []

    async def tool_status(self) -> Any:
        return type("S", (), {"state": "ready", "version": "abc", "message": None})()

    async def install_tool(self, request_id: str) -> dict[str, Any]:
        self.calls.append(("install", request_id))
        return {"state": "installing", "version": None, "message": None}

    async def external_devices(self) -> list[dict[str, Any]]:
        return [{"serial": "S1", "state": "device", "model": "Pixel", "product": None}]

    async def start(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("start", request))
        if request["instruction"] == "boom":
            raise AndroidError("AI_TEST_DEVICE_BUSY", "忙", 409)
        return self.repository.create(_run(9, requestId=request["requestId"]))

    async def install_helper(self, kind: str, device_id: str | None, serial: str | None) -> bool:
        self.calls.append(("helper", (kind, device_id, serial)))
        return True

    async def cancel(self, run_id: str) -> dict[str, Any]:
        self.calls.append(("cancel", run_id))
        return self.repository.get(run_id)


def _run(n: int, **extra: Any) -> dict[str, Any]:
    return {
        "id": f"run-{n}", "requestId": f"req-{n}", "deviceKind": "managed", "deviceId": "dev-1", "serial": None,
        "state": "succeeded", "createdAt": datetime(2026, 10, n, tzinfo=UTC).isoformat(), "startedAt": None,
        "finishedAt": None, "instruction": "打开设置", "mode": "flash", "modelId": "m", "modelKey": "k",
        "maxSteps": 5, "timeoutSeconds": 60, "requestDigest": f"d{n}", "artifactsDir": f"/abs/run-{n}",
        "toolVersion": "abc", "steps": [{"index": 1, "summary": "点击", "screenshot": "s1.png"}],
        "succeeded": True, "traceId": None, "artifacts": ["s1.png"], "errorCode": None, "errorMessage": None, **extra,
    }


@pytest.fixture
def env(tmp_path: Path) -> tuple[TestClient, FakeService]:
    engine = create_engine(f"sqlite:///{tmp_path / 'ai.sqlite3'}")
    Base.metadata.create_all(engine)
    service = FakeService(AiTestRepository(sessionmaker(engine, expire_on_commit=False)), tmp_path / "ai-tests")
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_ai_tests_router(service))  # type: ignore[arg-type]
    return TestClient(app), service


def test_tool_and_devices(env: tuple[TestClient, FakeService]) -> None:
    client, service = env
    assert client.get(f"{BASE}/tool").json() == {"state": "ready", "version": "abc", "message": None}
    installed = client.post(f"{BASE}/tool/install", json={"requestId": "r1"})
    assert installed.status_code == 200 and installed.json()["state"] == "installing"
    assert ("install", "r1") in service.calls
    assert client.get(f"{BASE}/external-devices").json()[0]["serial"] == "S1"


def test_start_returns_202_and_hides_internal_fields(env: tuple[TestClient, FakeService]) -> None:
    client, _ = env
    body = {"requestId": "r9", "deviceKind": "managed", "deviceId": "dev-1", "instruction": "x",
            "mode": "flash", "modelId": "m", "maxSteps": 5, "timeoutSeconds": 60}
    response = client.post(f"{BASE}/runs", json=body)
    assert response.status_code == 202
    data = response.json()
    assert data["artifacts"] == ["s1.png"] and data["steps"][0]["screenshot"] == "s1.png"
    assert "requestDigest" not in data and "artifactsDir" not in data
    assert client.post(f"{BASE}/runs", json={**body, "instruction": "boom"}).json()["error"]["code"] == "AI_TEST_DEVICE_BUSY"


def test_list_get_cancel_and_helper(env: tuple[TestClient, FakeService]) -> None:
    client, service = env
    for n in (1, 2, 3):
        service.repository.create(_run(n))
    page = client.get(f"{BASE}/runs", params={"deviceKind": "managed", "deviceId": "dev-1"}).json()
    assert [r["id"] for r in page["items"]] == ["run-3", "run-2", "run-1"] and page["nextCursor"] is None
    assert client.get(f"{BASE}/runs/run-1").json()["modelKey"] == "k"
    assert client.get(f"{BASE}/runs/nope").status_code == 404
    assert client.post(f"{BASE}/runs/run-1/cancel").status_code == 200
    helper = client.post(f"{BASE}/helper", json={"deviceKind": "external", "serial": "S1"})
    assert helper.status_code == 200 and ("helper", ("external", None, "S1")) in service.calls


def test_list_requires_a_device_scope(env: tuple[TestClient, FakeService]) -> None:
    client, _ = env
    assert client.get(f"{BASE}/runs", params={"deviceKind": "managed"}).status_code == 422
    assert client.get(f"{BASE}/runs", params={"deviceKind": "external"}).status_code == 422


@pytest.mark.parametrize("cursor", [base64.urlsafe_b64encode(b"[1,2]").decode(), "!!garbage!!", "e30="])
def test_invalid_cursor_is_422(env: tuple[TestClient, FakeService], cursor: str) -> None:
    client, _ = env
    response = client.get(f"{BASE}/runs", params={"deviceKind": "managed", "deviceId": "dev-1", "cursor": cursor})
    assert response.status_code == 422 and response.json()["error"]["code"] == "AI_TEST_CURSOR_INVALID"


def test_artifact_download_and_traversal(env: tuple[TestClient, FakeService]) -> None:
    client, service = env
    run_dir = service.artifacts_root / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "s1.png").write_bytes(b"png")
    (service.artifacts_root / "secret.txt").write_text("nope")
    ok = client.get(f"{BASE}/runs/run-1/artifacts/s1.png")
    assert ok.status_code == 200 and ok.content == b"png" and ok.headers["content-type"] == "image/png"
    for name in ("..%2Fsecret.txt", "..%2F..%2Fx", "%2Fetc%2Fpasswd", "missing.png", "%2E%2E%2Fsecret.txt"):
        response = client.get(f"{BASE}/runs/run-1/artifacts/{name}")
        assert response.status_code == 404, name
        assert response.json()["error"]["code"] == "AI_TEST_ARTIFACT_NOT_FOUND", name
    assert client.get(f"{BASE}/runs/run-1/artifacts/../../x").status_code == 404


def test_delete_rejects_active_and_removes_finished(env: tuple[TestClient, FakeService]) -> None:
    client, service = env
    service.repository.create(_run(1, state="running"))
    service.repository.create(_run(2))
    done_dir = service.artifacts_root / "run-2"
    done_dir.mkdir(parents=True)
    (done_dir / "a.png").write_bytes(b"x")
    conflict = client.delete(f"{BASE}/runs/run-1")
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "AI_TEST_STATE_CONFLICT"
    assert client.delete(f"{BASE}/runs/run-2").status_code == 204
    assert not done_dir.exists() and client.get(f"{BASE}/runs/run-2").status_code == 404
    assert client.delete(f"{BASE}/runs/run-2").status_code == 404
