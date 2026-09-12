"""Synthetic local runtime checks. These do not verify ProxyPanel's live schema."""

import pytest
from fastapi.testclient import TestClient

from autoflow.bootstrap import proxies as composition
from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.proxies.models import (
    Endpoint,
    ProviderCredentials,
    ProviderPage,
    ProviderProxy,
)


class MemoryCredentials:
    def __init__(self):
        self.values: dict[str, bytes] = {}

    def read(self, key: str) -> bytes | None:
        return self.values.get(key)

    def write(self, key: str, value: bytes) -> None:
        self.values[key] = value

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


class SyntheticProvider:
    async def verify(self, _api_key):
        return ProviderPage((), "unknown")

    async def get_credentials(self, _api_key, _provider_id):
        return ProviderCredentials("user@example", "secret:/@?", Endpoint("8.8.8.8", 1080))

    async def list_proxies(self, _api_key):
        return ProviderPage((ProviderProxy(
            "synthetic-1", "合成测试代理", http_endpoint=Endpoint("8.8.8.8", 1080),
            credential_available=True,
        ),), "complete", 1)


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    credentials = MemoryCredentials()
    monkeypatch.setattr(composition, "LazySystemCredentialStore", lambda: credentials)
    monkeypatch.setattr(composition, "ProxyPanelReadProvider", SyntheticProvider)
    app = create_app(Settings(
        data_dir=str(tmp_path), instance_id="test", instance_token="renderer-token",
        host_token="independent-host-token", renderer_origin="http://localhost:5173",
    ))
    with TestClient(app) as client:
        yield client, credentials


def test_runtime_mounts_proxies_but_never_publishes_host_contract(runtime):
    client, _ = runtime
    assert client.get("/api/v1/proxies").status_code == 401
    assert client.get("/api/v1/proxies", headers={"x-autoflow-token": "renderer-token"}).json()["items"] == []
    document = client.get("/openapi.json").json()
    assert "/api/v1/proxies/{projection_id}/probe" in document["paths"]
    assert not any(path.startswith("/internal") for path in document["paths"])
    schemas = document["components"]["schemas"]
    assert schemas["ConnectionCreate"]["properties"]["api_key"]["writeOnly"]
    assert all("password" not in schema.get("properties", {}) for schema in schemas.values())


@pytest.mark.parametrize("headers", [
    {}, {"x-autoflow-token": "renderer-token"},
    {"x-autoflow-host-token": "renderer-token"},
    {"x-autoflow-host-token": "independent-host-token", "origin": "http://localhost:5173"},
])
def test_renderer_cannot_call_host_credential_endpoint(runtime, headers):
    client, _ = runtime
    response = client.post("/internal/proxy-credentials/resolve", json={}, headers=headers)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


def test_valid_host_only_copy_encodes_auth_without_renderer_secret(runtime):
    client, credentials = runtime
    headers = {"x-autoflow-token": "renderer-token"}
    created = client.post("/api/v1/proxy-panel/connections", json={
        "name": "测试连接", "api_key": "synthetic-secret",
    }, headers=headers)
    assert created.status_code == 201
    identifier = created.json()["id"]
    assert client.post(f"/api/v1/proxy-panel/connections/{identifier}/sync", json={}, headers=headers).status_code == 200
    page = client.get("/api/v1/proxies", headers=headers)
    proxy_id = page.json()["items"][0]["id"]
    assert credentials.read(f"proxy-endpoint:{proxy_id}") is None
    response = client.post("/internal/proxy-credentials/resolve", json={
        "proxy_id": proxy_id, "protocol": "http", "format": "url",
    }, headers={"x-autoflow-host-token": "independent-host-token"})
    assert response.status_code == 200
    assert response.json() == {"value": "http://user%40example:secret%3A%2F%40%3F@8.8.8.8:1080"}
    assert response.headers["cache-control"] == "no-store"
    ordinary = client.get(f"/api/v1/proxies/{proxy_id}", headers=headers)
    assert "user@example" not in ordinary.text and "secret:/@?" not in ordinary.text
    assert "synthetic-secret" not in created.text


def test_secret_validation_errors_never_echo_input(runtime):
    client, _ = runtime
    response = client.post("/api/v1/proxy-panel/connections", json={
        "name": "test", "api_key": {"nested_secret": "do-not-echo-me"},
    }, headers={"x-autoflow-token": "renderer-token"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "api_key" in response.json()["error"]["field_errors"]
    assert "do-not-echo-me" not in response.text and "nested_secret" not in response.text


def test_cors_allows_request_key_but_rejects_host_token(runtime):
    client, _ = runtime
    headers = {
        "origin": "http://localhost:5173", "access-control-request-method": "POST",
        "access-control-request-headers": "x-autoflow-token, content-type, idempotency-key",
    }
    assert client.options("/api/v1/proxies", headers=headers).status_code == 200
    headers["access-control-request-headers"] = "x-autoflow-host-token"
    assert client.options("/internal/proxy-credentials/resolve", headers=headers).status_code == 400
