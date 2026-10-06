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

    async def screen(self, run_id: str) -> bytes:
        self.calls.append(("screen", run_id))
        if run_id != "run-1":
            raise AndroidError("AI_TEST_STATE_CONFLICT", "测试未在设备工作台中运行，无法查看实时画面", 409)
        return b"PNG-live"


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
    service.repository.create(_run(1))
    run_dir = service.artifacts_root / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "s1.png").write_bytes(b"png")
    (service.artifacts_root / "secret.txt").write_text("nope")
    ok = client.get(f"{BASE}/runs/run-1/artifacts/s1.png")
    assert ok.status_code == 200 and ok.content == b"png" and ok.headers["content-type"] == "image/png"
    names = ("..%2Fsecret.txt", "..%2F..%2Fx", "%2Fetc%2Fpasswd", "missing.png", "%2E%2E%2Fsecret.txt",
             "..%5Csecret.txt", "C:%5Cx", "C:%2Fx", "%2E%2E")
    for name in names:
        response = client.get(f"{BASE}/runs/run-1/artifacts/{name}")
        assert response.status_code == 404, name
        assert response.json()["error"]["code"] == "AI_TEST_ARTIFACT_NOT_FOUND", name


def test_artifact_rejects_traversing_run_id_and_unrecorded_directories(env: tuple[TestClient, FakeService]) -> None:
    client, service = env
    service.artifacts_root.mkdir(parents=True)
    (service.artifacts_root / "secret.txt").write_text("nope")
    orphan = service.artifacts_root / "orphan"
    orphan.mkdir()
    (orphan / "a.png").write_bytes(b"x")
    for run_id in ("..", "%2E%2E", "..%5C..", "orphan"):
        response = client.get(f"{BASE}/runs/{run_id}/artifacts/secret.txt")
        assert response.status_code == 404, run_id
    response = client.get(f"{BASE}/runs/orphan/artifacts/a.png")
    assert response.status_code == 404 and response.json()["error"]["code"] == "AI_TEST_NOT_FOUND"
    # a recorded run whose id escapes the artifacts root is still refused by the directory check
    service.repository.create(_run(5, id=".."))
    response = client.get(f"{BASE}/runs/%2E%2E/artifacts/secret.txt")
    assert response.status_code == 404


def test_delete_rejects_active_and_removes_finished(env: tuple[TestClient, FakeService]) -> None:
    client, service = env
    service.repository.create(_run(1, state="running"))
    service.repository.create(_run(2))
    service.repository.create(_run(3, state="queued"))
    service.repository.create(_run(4, state="needs_verification"))
    done_dir = service.artifacts_root / "run-2"
    done_dir.mkdir(parents=True)
    (done_dir / "a.png").write_bytes(b"x")
    for active in ("run-1", "run-3"):
        conflict = client.delete(f"{BASE}/runs/{active}")
        assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "AI_TEST_STATE_CONFLICT"
    assert client.delete(f"{BASE}/runs/run-2").status_code == 204
    assert not done_dir.exists() and client.get(f"{BASE}/runs/run-2").status_code == 404
    assert client.delete(f"{BASE}/runs/run-2").status_code == 404
    assert client.delete(f"{BASE}/runs/run-4").status_code == 204  # interrupted runs can be cleared


def test_delete_logs_cleanup_failure_but_removes_record(
    env: tuple[TestClient, FakeService], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    client, service = env
    service.repository.create(_run(2))
    (service.artifacts_root / "run-2").mkdir(parents=True)

    def broken(path: str, onerror: Any = None, **_: Any) -> None:
        onerror(None, path, (OSError, OSError("locked"), None))

    monkeypatch.setattr("autoflow.adapters.http.android_ai_tests.shutil.rmtree", broken)
    with caplog.at_level("WARNING"):
        assert client.delete(f"{BASE}/runs/run-2").status_code == 204
    assert "locked" in caplog.text and "run-2" in caplog.text
    assert client.get(f"{BASE}/runs/run-2").status_code == 404


def test_live_screen_is_png_or_state_conflict(env: tuple[TestClient, FakeService]) -> None:
    client, service = env
    ok = client.get(f"{BASE}/runs/run-1/screen")
    assert ok.status_code == 200 and ok.headers["content-type"] == "image/png" and ok.content == b"PNG-live"
    assert ok.headers["cache-control"] == "no-store"
    refused = client.get(f"{BASE}/runs/run-2/screen")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "AI_TEST_STATE_CONFLICT"


def test_app_recovers_ai_tests_before_serving_and_shuts_them_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    from autoflow.application.android.ai_tests import AiTestService
    from autoflow.bootstrap.app import create_app
    from autoflow.bootstrap.config import Settings

    events: list[str] = []

    async def recover(self: AiTestService) -> None:
        await asyncio.sleep(0)  # only an awaited handler gets past this point
        events.append("recovered")

    async def shutdown(self: AiTestService) -> None:
        await asyncio.sleep(0)
        events.append("shut down")

    monkeypatch.setenv("AUTOFLOW_ANDROID_RUNTIME_ROOT", str(tmp_path / "android"))
    monkeypatch.setattr(AiTestService, "recover", recover)
    monkeypatch.setattr(AiTestService, "shutdown", shutdown)
    app = create_app(Settings(data_dir=str(tmp_path / "data"), instance_id="t", instance_token="secret",
                              host_token="host-secret"))
    assert isinstance(app.state.ai_tests, AiTestService) and events == []
    with TestClient(app, headers={"x-autoflow-token": "secret"}) as client:
        assert events == ["recovered"]  # startup finished recovery before the first request
        assert client.get(f"{BASE}/runs/missing").status_code == 404
    assert events == ["recovered", "shut down"]
