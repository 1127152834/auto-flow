from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.proxies import proxy_router
from autoflow.application.proxies.facade import ProxyApplication
from autoflow.domain.proxies.models import Endpoint, Health, ProviderPage, ProviderProxy
from autoflow.infrastructure.database.proxies import SqlAlchemyProxyUnitOfWork
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


class MemoryCredentials:
    def __init__(self):
        self.values = {}

    def read(self, key):
        return self.values.get(key)

    def write(self, key, value):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)


class FakeProvider:
    async def verify(self, api_key):
        assert api_key == b"top-secret"
        return ProviderPage((), "unknown")

    async def list_proxies(self, api_key):
        return ProviderPage(
            (
                ProviderProxy(
                    "remote-1",
                    "Remote One",
                    http_endpoint=Endpoint("proxy.example", 8000),
                    credential_available=True,
                ),
            ),
            "complete",
            1,
        )


class FakeProbe:
    async def probe(self, projection):
        return Health(state="healthy", latency_ms=12.5, exit_ip="203.0.113.9", source="local_probe")


def _client(tmp_path: Path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    app = FastAPI()
    application = ProxyApplication(
        lambda: SqlAlchemyProxyUnitOfWork(factory), MemoryCredentials(), FakeProvider(), FakeProbe()
    )
    app.include_router(proxy_router(application))
    return TestClient(app), factory


def test_connection_sync_proxy_page_and_group_risk_contract(tmp_path: Path):
    client, factory = _client(tmp_path)
    created = client.post("/api/v1/proxy-panel/connections", json={"name": "Main", "api_key": "top-secret"})
    assert created.status_code == 201
    assert "api_key" not in created.text and "top-secret" not in created.text
    connection = created.json()
    assert connection["last_synced_at"] is None
    assert all(not item["available"] and item["evidence"] == "unknown" for item in connection["capabilities"])

    synced = client.post(f"/api/v1/proxy-panel/connections/{connection['id']}/sync", json={})
    assert synced.status_code == 200
    assert synced.json()["resource"]["completeness"] == "complete"
    page = client.get("/api/v1/proxies", params={"offset": 0, "limit": 1}).json()
    assert page["matched_count"] == 1
    assert page["items"][0]["remote_status"] is None
    assert page["items"][0]["subscription_expires_at"] is None
    risk = client.post(
        "/api/v1/proxy-groups",
        json={"name": "Local", "description": "", "member_ids": [page["items"][0]["id"]]},
    )
    assert risk.status_code == 409
    assert risk.json()["error"]["code"] == "PROXY_MEMBER_RISK_CONFIRMATION_REQUIRED"
    assert risk.json()["error"]["field_errors"]["member_ids"] == [page["items"][0]["id"]]
    accepted = client.post(
        "/api/v1/proxy-groups",
        json={
            "name": "Local",
            "description": "",
            "member_ids": [page["items"][0]["id"]],
            "acknowledge_risk": True,
        },
    )
    assert accepted.status_code == 201
    assert accepted.json()["member_ids"] == [page["items"][0]["id"]]
    checked = client.post(f"/api/v1/proxies/{page['items'][0]['id']}/probe", json={"protocol": "http"})
    assert checked.status_code == 200
    assert checked.json()["resource"]["state"] == "healthy"
    remote_write = client.post(
        f"/api/v1/proxies/{page['items'][0]['id']}/change-ip",
        json={"expected_revision": page["items"][0]["revision"]},
    )
    assert remote_write.status_code == 503
    assert remote_write.json()["error"]["code"] == "CAPABILITY_UNAVAILABLE"
    factory.dispose()


def test_proxy_openapi_marks_api_key_write_only_and_never_models_password(tmp_path: Path):
    client, factory = _client(tmp_path)
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert schemas["ConnectionCreate"]["properties"]["api_key"]["writeOnly"] is True
    assert schemas["ApiKeyUpdate"]["properties"]["api_key"]["writeOnly"] is True
    assert all("password" not in schema.get("properties", {}) for schema in schemas.values())
    factory.dispose()
