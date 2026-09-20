"""Real response shapes, synthetic transport and vault; never uses live secrets."""

import json
from pathlib import Path

import httpx
import pytest

from autoflow.application.proxies.credential_loader import ProxyCredentialLoader
from autoflow.application.proxies.facade import ProxyApplication
from autoflow.domain.proxies.errors import (
    CapabilityUnavailableError,
    RevisionConflictError,
)
from autoflow.infrastructure.database.proxies import SqlAlchemyProxyUnitOfWork
from autoflow.infrastructure.database.proxy_options import SqlAlchemyProxyOptions
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.providers.proxy.probe import HttpProxyProbe
from autoflow.providers.proxy.proxypanel import ProxyPanelReadProvider

FIXTURES = Path(__file__).parents[1] / "fixtures" / "proxypanel"


class Memory:
    def __init__(self):
        self.values = {}

    def read(self, key):
        return self.values.get(key)

    def write(self, key, value):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)


@pytest.fixture
def runtime(tmp_path):
    body = json.loads((FIXTURES / "list-redacted.json").read_text(encoding="utf-8"))
    body["proxies"].append({**body["proxies"][0], "id": "expired", "state": "expired"})
    secret = json.loads((FIXTURES / "credentials-redacted.json").read_text(encoding="utf-8"))
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return httpx.Response(
            200, json=secret if request.url.path.endswith("/credentials") else body
        )

    provider = ProxyPanelReadProvider(transport=httpx.MockTransport(respond))
    db = tmp_path / "autoflow.sqlite3"
    migrate_database(db)
    factory = create_session_factory(db)
    uow = lambda: SqlAlchemyProxyUnitOfWork(factory)
    memory = Memory()
    loader = ProxyCredentialLoader(uow, memory, provider)
    probe = HttpProxyProbe(
        memory,
        load_credentials=loader,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"ip": "8.8.4.4"})
        ),
    )
    service = ProxyApplication(uow, memory, provider, probe)
    yield service, loader, memory, factory, provider, calls
    factory.dispose()


@pytest.mark.asyncio
async def test_sync_to_lazy_credentials_to_probe_and_browser_options(runtime):
    service, loader, memory, factory, _, calls = runtime
    connection = await service.create_connection("Test", "test-key")
    await service.sync_connection(connection.id)
    proxies, count = service.list_projections(limit=100)
    assert count == 2
    active = next(x for x in proxies if x.credential_available)
    expired = next(x for x in proxies if not x.credential_available)
    assert memory.read(f"proxy-endpoint:{active.id}") is None
    options = SqlAlchemyProxyOptions(factory)
    assert options.proxy_is_available(active.id)
    assert not options.proxy_is_available(expired.id)
    assert {x.id: x.enabled for x in options.list_proxies()}[expired.id] is False
    for protocol in ("http", "socks5"):
        assert (await service.check_health(active.id, protocol)).state == "healthy"
    assert calls.count("/api/v1/proxies/pp-test-1/credentials") == 2
    assert memory.read(f"proxy-endpoint:{active.id}") is None
    with pytest.raises(CapabilityUnavailableError):
        await loader(expired)
    # Metadata changes preserve the provider projection and lazily fetched credential state.
    current = service.get_projection(active.id)
    service.update_projection(
        active.id,
        expected_revision=current.revision,
        name_override="Local",
        enabled=True,
        change_name=True,
    )
    await service.sync_connection(connection.id)
    assert service.get_projection(active.id).name_override == "Local"


@pytest.mark.asyncio
async def test_late_credentials_cannot_overwrite_a_changed_connection(runtime):
    service, loader, memory, _, provider, _ = runtime
    connection = await service.create_connection("Test", "test-key")
    await service.sync_connection(connection.id)
    active = next(
        x for x in service.list_projections(limit=100)[0] if x.credential_available
    )
    original = provider.get_credentials

    async def changed(key, provider_id):
        value = await original(key, provider_id)
        latest = service.list_connections()[0]
        await service.replace_api_key(latest.id, latest.revision, "new-key")
        return value

    provider.get_credentials = changed
    with pytest.raises(RevisionConflictError):
        await loader(active)
    assert memory.read(f"proxy-endpoint:{active.id}") is None


@pytest.mark.asyncio
async def test_changed_credential_endpoints_require_resync(runtime):
    service, loader, memory, _, provider, _ = runtime
    connection = await service.create_connection("Test", "test-key")
    await service.sync_connection(connection.id)
    active = next(
        x for x in service.list_projections(limit=100)[0] if x.credential_available
    )
    original = provider.get_credentials

    async def changed(key, provider_id):
        from dataclasses import replace

        from autoflow.domain.proxies.models import Endpoint

        return replace(
            await original(key, provider_id),
            http_endpoint=Endpoint("changed.example.test", 8080),
        )

    provider.get_credentials = changed
    with pytest.raises(RevisionConflictError):
        await loader(active)
    assert memory.read(f"proxy-endpoint:{active.id}") is None
