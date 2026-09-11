import httpx
import pytest

from autoflow.domain.proxies.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderSchemaError,
)
from autoflow.providers.proxy.proxypanel import (
    ProxyPanelReadProvider,
    retry_after_seconds,
)


@pytest.mark.asyncio
async def test_verify_sends_key_only_to_fixed_origin_and_does_not_guess_schema():
    calls = []

    def respond(request):
        calls.append(request)
        assert str(request.url) == "https://proxypanel.io/api/v1/proxies"
        assert request.headers["Authorization"] == "Bearer synthetic-test-key"
        return httpx.Response(200, json={"unreviewed_field": [{"id": "example"}]})

    provider = ProxyPanelReadProvider(transport=httpx.MockTransport(respond))
    result = await provider.verify(b"synthetic-test-key")
    assert result.completeness == "unknown" and result.items == ()
    with pytest.raises(ProviderSchemaError, match="字段尚未"):
        await provider.list_proxies(b"synthetic-test-key")
    assert len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code",
    [
        (401, "PROXYPANEL_AUTH_FAILED"),
        (403, "PROXYPANEL_AUTH_FAILED"),
        (429, "PROXYPANEL_RATE_LIMITED"),
        (503, "PROXYPANEL_UNAVAILABLE"),
        (302, "PROXYPANEL_UNAVAILABLE"),
    ],
)
async def test_provider_errors_never_echo_body_key_or_redirect(status, code):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(
            status,
            text="secret=synthetic-test-key",
            headers={"Retry-After": "12", "Location": "https://example.com/collect"},
        )

    provider = ProxyPanelReadProvider(transport=httpx.MockTransport(respond))
    with pytest.raises(ProviderError) as raised:
        await provider.verify(b"synthetic-test-key")
    assert raised.value.code == code
    assert "synthetic-test-key" not in str(raised.value)
    assert len(calls) == 1
    if status == 429:
        assert raised.value.retry_after_seconds == 12


@pytest.mark.asyncio
async def test_header_injection_fails_before_network():
    provider = ProxyPanelReadProvider(
        transport=httpx.MockTransport(lambda _: pytest.fail("network called"))
    )
    with pytest.raises(ProviderAuthenticationError):
        await provider.verify(b"bad\r\nkey")


def test_retry_after_does_not_invent_cooldown():
    assert retry_after_seconds(None) is None
    assert retry_after_seconds("not-a-date") is None
    assert retry_after_seconds("25") == 25
