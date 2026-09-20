"""Live response shapes with replaced identifiers/hosts/secrets; edge cases synthetic."""

import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from autoflow.domain.proxies.errors import ProviderSchemaError
from autoflow.providers.proxy.proxypanel import ProxyPanelReadProvider

FIXTURES = Path(__file__).parents[1] / "fixtures" / "proxypanel"


def sample():
    return json.loads((FIXTURES / "list-redacted.json").read_text(encoding="utf-8"))


def provider(body):
    return ProxyPanelReadProvider(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    )


@pytest.mark.asyncio
async def test_verified_fleet_maps_protocol_ports_expiry_and_never_retains_username():
    page = await provider(sample()).list_proxies(b"test-key")
    assert page.completeness == "complete" and page.total == 1
    proxy = page.items[0]
    assert proxy.http_endpoint.port == 8083
    assert proxy.socks5_endpoint.port == 9093
    assert proxy.subscription_expires_at.year == 2030
    assert proxy.credential_available
    assert "test-user" not in repr(page)
    assert next(c for c in proxy.capabilities if c.key == "credentials").available


@pytest.mark.asyncio
async def test_expired_proxies_stay_visible_but_cannot_be_used():
    body = sample()
    body["proxies"][0]["state"] = "expired"
    proxy = (await provider(body).list_proxies(b"test-key")).items[0]
    assert proxy.remote_status == "expired"
    assert not proxy.credential_available


@pytest.mark.asyncio
async def test_empty_complete_list_is_supported():
    assert (await provider({"proxies": []}).list_proxies(b"test-key")).total == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["pagination", "duplicate", "bad_date", "bad_port", "bad_id"]
)
async def test_schema_drift_does_not_partially_import_or_infer_completeness(change):
    body = sample()
    item = body["proxies"][0]
    if change == "pagination":
        body["next_cursor"] = "next"
    elif change == "duplicate":
        body["proxies"].append(deepcopy(item))
    elif change == "bad_date":
        item["expires_at"] = "tomorrow"
    elif change == "bad_port":
        item["connection"]["http_port"] = True
    else:
        item["id"] = "../../credentials"
    with pytest.raises(ProviderSchemaError):
        await provider(body).list_proxies(b"test-key")


@pytest.mark.asyncio
async def test_credentials_use_fixed_origin_and_validated_id_not_server_url():
    data = json.loads((FIXTURES / "credentials-redacted.json").read_text(encoding="utf-8"))
    calls = []

    def response(request):
        calls.append(request)
        assert (
            str(request.url)
            == "https://proxypanel.io/api/v1/proxies/pp-test-1/credentials"
        )
        return httpx.Response(200, json=data)

    adapter = ProxyPanelReadProvider(transport=httpx.MockTransport(response))
    value = await adapter.get_credentials(b"test-key", "pp-test-1")
    assert value.password == "test-password"
    assert "test-password" not in repr(value) and "test-user" not in repr(value)
    with pytest.raises(ProviderSchemaError):
        await adapter.get_credentials(b"test-key", "//other.example/secrets")
    for invalid_id in (".", ".."):
        with pytest.raises(ProviderSchemaError):
            await adapter.get_credentials(b"test-key", invalid_id)
    assert len(calls) == 1
