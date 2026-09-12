from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from autoflow.domain.profiles.models import (
    ProfileTestBrowserSession,
    ProfileTestBrowserStatus,
)
from autoflow.infrastructure.database.models import ProxyPoolRow, ProxyRow


def test_duplicate_keeps_settings_but_changes_seed(
    client: TestClient, profile_payload: dict[str, Any]
) -> None:
    original = client.post("/api/v1/profiles", json=profile_payload).json()
    source_data = client.app.state.paths.profiles / original["id"]
    source_data.mkdir()
    (source_data / "Cookies").write_text("private")
    response = client.post(
        f"/api/v1/profiles/{original['id']}/duplicate", json={"name": "副本"}
    )
    assert response.status_code == 201, response.text
    copied = response.json()
    assert copied["browserVersion"] == original["browserVersion"]
    assert copied["fingerprintSeed"] != original["fingerprintSeed"]
    assert copied["id"] != original["id"]
    assert copied["name"] == "副本"
    for key in profile_payload.keys() - {"name", "expertArgsJson"}:
        assert copied[key] == original[key]
    assert not (client.app.state.paths.profiles / copied["id"]).exists()


def test_profile_crud_and_fingerprint_lifecycle(
    client: TestClient, profile_payload: dict[str, Any]
) -> None:
    created_response = client.post("/api/v1/profiles", json=profile_payload)
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    assert 10000 <= created["fingerprintSeed"] <= 99999
    assert created["expertArgsJson"] == ["--lang=zh-CN"]

    listed = client.get("/api/v1/profiles")
    assert listed.status_code == 200
    assert listed.json() == {"items": [created], "total": 1}
    assert client.get(f"/api/v1/profiles/{created['id']}").json() == created

    updated_payload = {**profile_payload, "name": "已更新", "description": "new"}
    updated_response = client.put(f"/api/v1/profiles/{created['id']}", json=updated_payload)
    assert updated_response.status_code == 200, updated_response.text
    updated = updated_response.json()
    assert updated["name"] == "已更新"
    assert updated["description"] == "new"
    assert updated["fingerprintSeed"] == created["fingerprintSeed"]
    assert updated["createdAt"] == created["createdAt"]

    regenerated_response = client.post(
        f"/api/v1/profiles/{created['id']}/regenerate-fingerprint"
    )
    assert regenerated_response.status_code == 200
    regenerated = regenerated_response.json()
    assert regenerated["fingerprintSeed"] != updated["fingerprintSeed"]

    profile_data = client.app.state.paths.profiles / created["id"]
    profile_data.mkdir()
    (profile_data / "Cookies").write_text("private")

    deleted = client.delete(f"/api/v1/profiles/{created['id']}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert not profile_data.exists()
    assert client.get(f"/api/v1/profiles/{created['id']}").status_code == 404


def test_profile_test_browser_contract_returns_only_ready_session(
    client: TestClient, profile_payload: dict[str, Any], monkeypatch
) -> None:
    profile = client.post("/api/v1/profiles", json=profile_payload).json()
    session_id = str(uuid4())
    start = AsyncMock(
        return_value=ProfileTestBrowserSession(
            session_id,
            profile["id"],
            profile["fingerprintSeed"],
            "起始网址加载失败，浏览器已保留，可手动重试",
        )
    )
    monkeypatch.setattr(client.app.state.profile_test_browser, "start", start)

    response = client.post(f"/api/v1/profiles/{profile['id']}/test-browser")

    assert response.status_code == 201
    assert response.json() == {
        "sessionId": session_id,
        "profileId": profile["id"],
        "fingerprintSeed": profile["fingerprintSeed"],
        "warning": "起始网址加载失败，浏览器已保留，可手动重试",
    }
    start.assert_awaited_once_with(profile["id"])
    schema = client.get("/openapi.json").json()["components"]["schemas"]
    assert set(schema["ProfileTestBrowserRead"]["required"]) == {
        "sessionId",
        "profileId",
        "fingerprintSeed",
    }


def test_profile_test_browser_status_and_idempotent_close_contract(
    client: TestClient, profile_payload: dict[str, Any], monkeypatch
) -> None:
    profile = client.post("/api/v1/profiles", json=profile_payload).json()
    session_id = str(uuid4())
    status_item = ProfileTestBrowserStatus(profile["id"], session_id, "running")
    statuses = lambda: [status_item]
    stop = AsyncMock(return_value=None)
    monkeypatch.setattr(client.app.state.profile_test_browser, "statuses", statuses)
    monkeypatch.setattr(client.app.state.profile_test_browser, "stop", stop)

    listed = client.get("/api/v1/profiles/test-browsers")
    closed = client.delete(f"/api/v1/profiles/{profile['id']}/test-browser")
    closed_again = client.delete(f"/api/v1/profiles/{profile['id']}/test-browser")
    profile_delete = client.delete(f"/api/v1/profiles/{profile['id']}")

    assert listed.status_code == 200
    assert listed.json() == {
        "items": [
            {
                "profileId": profile["id"],
                "sessionId": session_id,
                "state": "running",
            }
        ]
    }
    assert closed.status_code == closed_again.status_code == 204
    assert stop.await_count == 2
    assert profile_delete.status_code == 409
    assert profile_delete.json()["error"]["code"] == "PROFILE_TEST_BROWSER_BUSY"
    schema = client.get("/openapi.json").json()["components"]["schemas"]
    assert set(schema["ProfileTestBrowserList"]["required"]) == {"items"}
    assert set(schema["ProfileTestBrowserStatusRead"]["required"]) == {
        "profileId",
        "sessionId",
        "state",
    }


def test_profile_errors_use_stable_envelope_and_camel_case_fields(
    client: TestClient, profile_payload: dict[str, Any]
) -> None:
    original = client.post("/api/v1/profiles", json=profile_payload)
    assert original.status_code == 201

    conflict = client.post("/api/v1/profiles", json=profile_payload)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "PROFILE_NAME_CONFLICT"
    assert conflict.json()["error"]["requestId"]
    assert conflict.json()["error"]["details"]["fields"] == {"name": "Profile name is already in use"}
    duplicate = client.post(
        f"/api/v1/profiles/{original.json()['id']}/duplicate", json={"name": profile_payload["name"]}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["details"]["fields"] == conflict.json()["error"]["details"]["fields"]

    invalid = client.post(
        "/api/v1/profiles",
        json={**profile_payload, "viewportJson": {"width": 100, "height": 720}},
    )
    assert invalid.status_code == 422
    body = invalid.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert "viewportJson" in body["details"]["fields"]
    assert body["requestId"]

    extra = client.post("/api/v1/profiles", json={**profile_payload, "profilePath": "/tmp/x"})
    assert extra.status_code == 422
    assert "profilePath" in extra.json()["error"]["details"]["fields"]

    reserved = client.post(
        "/api/v1/profiles",
        json={**profile_payload, "name": "Reserved", "expertArgsJson": ["--proxy-server x"]},
    )
    assert reserved.status_code == 422
    assert "expertArgsJson" in reserved.json()["error"]["details"]["fields"]

    missing_proxy_id = client.post(
        "/api/v1/profiles",
        json={**profile_payload, "name": "Proxy", "proxyMode": "proxy", "proxyId": None},
    )
    assert missing_proxy_id.status_code == 422
    assert "proxyId" in missing_proxy_id.json()["error"]["details"]["fields"]


def test_unavailable_kernel_and_proxy_are_rejected(
    client: TestClient,
    profile_payload: dict[str, Any],
    installed_kernels: Any,
) -> None:
    installed_kernels.installed.clear()
    missing_kernel = client.post("/api/v1/profiles", json=profile_payload)
    assert missing_kernel.status_code == 409
    assert missing_kernel.json()["error"]["code"] == "KERNEL_NOT_INSTALLED"

    installed_kernels.installed.add(("public", "146.0.1.1"))
    missing_proxy = client.post(
        "/api/v1/profiles",
        json={**profile_payload, "proxyMode": "proxy", "proxyId": "missing"},
    )
    assert missing_proxy.status_code == 409
    assert missing_proxy.json()["error"]["code"] == "PROXY_UNAVAILABLE"


def test_proxy_options_and_missing_profile_contract(client: TestClient) -> None:
    options = client.get("/api/v1/proxy-options")
    assert options.status_code == 200
    assert options.json() == {"proxies": [], "pools": []}

    missing = client.get("/api/v1/profiles/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "PROFILE_NOT_FOUND"


def test_browser_error_runtime_matches_openapi_schema(client: TestClient) -> None:
    document = client.get("/openapi.json").json()
    schemas = document["components"]["schemas"]
    error = schemas["BrowserApiError"]
    assert set(error["required"]) == {"code", "message", "requestId"}
    assert "details" in error["properties"]

    response = document["paths"]["/api/v1/profiles/{profile_id}"]["get"]["responses"]["404"]
    assert response["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/BrowserErrorEnvelope"
    }

    runtime = client.get("/api/v1/profiles/00000000-0000-0000-0000-000000000000")
    assert set(runtime.json()["error"]) == set(error["properties"])


def test_proxy_options_only_expose_usable_resources(
    client: TestClient, profile_payload: dict[str, Any]
) -> None:
    with client.app.state.session_factory.begin() as session:
        session.add_all(
            [
                ProxyRow(id="proxy-enabled", name="可用代理", enabled=True),
                ProxyRow(id="proxy-disabled", name="停用代理", enabled=False),
                ProxyPoolRow(id="pool-1", name="代理池"),
            ]
        )

    response = client.get("/api/v1/proxy-options")
    assert response.status_code == 200
    assert response.json() == {
        "proxies": [{"id": "proxy-enabled", "name": "可用代理", "enabled": True}],
        "pools": [{"id": "pool-1", "name": "代理池"}],
    }
    created = client.post(
        "/api/v1/profiles",
        json={**profile_payload, "proxyMode": "proxy", "proxyId": "proxy-enabled"},
    )
    assert created.status_code == 201, created.text


def test_delete_rejects_profile_with_chromium_activity_marker(
    client: TestClient, profile_payload: dict[str, Any]
) -> None:
    profile = client.post("/api/v1/profiles", json=profile_payload).json()
    profile_data = client.app.state.paths.profiles / profile["id"]
    profile_data.mkdir()
    (profile_data / "SingletonLock").symlink_to("host-12345")

    deleted = client.delete(f"/api/v1/profiles/{profile['id']}")

    assert deleted.status_code == 409
    assert deleted.json()["error"]["code"] == "PROFILE_DIRECTORY_BUSY"
    assert client.get(f"/api/v1/profiles/{profile['id']}").status_code == 200
    assert profile_data.is_dir()
