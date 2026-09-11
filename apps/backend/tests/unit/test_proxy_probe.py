"""Synthetic-only tests for the bounded proxy probe; these do not verify a live proxy."""

from datetime import UTC, datetime

import httpx
import pytest

from autoflow.domain.credentials import CredentialStoreUnavailableError
from autoflow.domain.proxies.errors import (
    CapabilityUnavailableError,
    CredentialStoreError,
)
from autoflow.domain.proxies.models import Endpoint, Health, Projection
from autoflow.providers.proxy.probe import PROBE_URL, HttpProxyProbe

DEFAULT_HTTP_ENDPOINT = Endpoint("proxy.example", 8000)


class MemoryCredentials:
    def __init__(self, value: bytes | None = b'{"username":"proxy-user","password":"proxy-secret"}'):
        self.value = value

    def read(self, key: str) -> bytes | None:
        assert key == "proxy-endpoint:4cc4bd80-8f6a-48a7-a989-748e43a45389"
        return self.value

    def write(self, key: str, value: bytes) -> None:
        raise AssertionError("probe must not write credentials")

    def delete(self, key: str) -> None:
        raise AssertionError("probe must not delete credentials")


def projection(
    *,
    http_endpoint: Endpoint | None = DEFAULT_HTTP_ENDPOINT,
    socks5_endpoint: Endpoint | None = None,
    credential_available: bool = True,
) -> Projection:
    now = datetime.now(UTC)
    return Projection(
        id="4cc4bd80-8f6a-48a7-a989-748e43a45389",
        connection_id="connection-1",
        provider_id="provider-1",
        name="Synthetic proxy",
        name_override=None,
        enabled=True,
        remote_status="running",
        remote_missing=False,
        carrier=None,
        city=None,
        region=None,
        exit_ip=None,
        http_endpoint=http_endpoint,
        socks5_endpoint=socks5_endpoint,
        credential_available=credential_available,
        health=Health(),
        subscription_expires_at=None,
        last_synced_at=now,
        stale=False,
        revision=0,
        generation=1,
        capabilities=(),
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_probe_reports_public_exit_ip_and_measured_latency():
    async def respond(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == PROBE_URL
        return httpx.Response(200, json={"ip": "1.1.1.1"})

    result = await HttpProxyProbe(
        MemoryCredentials(),  # type: ignore[arg-type]
        transport=httpx.MockTransport(respond),
    ).probe(projection())

    assert result.state == "healthy"
    assert result.exit_ip == "1.1.1.1"
    assert result.latency_ms is not None and result.latency_ms >= 0
    assert result.checked_at is not None and result.checked_at.tzinfo is UTC
    assert result.source == "local_probe"
    assert result.error is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "candidate",
    [
        projection(http_endpoint=None),
        projection(credential_available=False),
    ],
)
async def test_probe_requires_a_verified_endpoint_and_credentials(candidate: Projection):
    with pytest.raises(CapabilityUnavailableError, match="端点或凭据"):
        await HttpProxyProbe(MemoryCredentials()).probe(candidate)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_probe_requires_credentials_to_exist_in_the_system_store():
    with pytest.raises(CredentialStoreError, match="重新同步"):
        await HttpProxyProbe(MemoryCredentials(None)).probe(projection())  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint",
    [
        Endpoint("127.0.0.1", 8000),
        Endpoint("10.0.0.1", 8000),
        Endpoint("[::1]", 8000),
        Endpoint("localhost", 8000),
        Endpoint("worker.localhost", 8000),
        Endpoint("proxy.example/path", 8000),
        Endpoint("proxy.example", 0),
        Endpoint("proxy.example", 65536),
    ],
)
async def test_probe_rejects_private_or_invalid_proxy_endpoints(endpoint: Endpoint):
    with pytest.raises(CapabilityUnavailableError):
        await HttpProxyProbe(MemoryCredentials()).probe(  # type: ignore[arg-type]
            projection(http_endpoint=endpoint)
        )


@pytest.mark.asyncio
async def test_probe_timeout_returns_a_fixed_error_without_credentials():
    async def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(
            "proxy-user:proxy-secret@proxy.example timed out",
            request=request,
        )

    result = await HttpProxyProbe(
        MemoryCredentials(),  # type: ignore[arg-type]
        transport=httpx.MockTransport(timeout),
    ).probe(projection())

    assert result.state == "unhealthy"
    assert result.latency_ms is None
    assert result.exit_ip is None
    assert result.error == {
        "code": "PROXY_PROBE_FAILED",
        "message": "通过代理的 HTTPS 检测失败，请检查端点与凭据",
    }
    assert "proxy-user" not in str(result)
    assert "proxy-secret" not in str(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{"ip": "not-an-ip"}, {"ip": "192.168.1.3"}, {}, []])
async def test_probe_rejects_invalid_or_non_public_exit_ip(body):
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=body))

    result = await HttpProxyProbe(
        MemoryCredentials(),  # type: ignore[arg-type]
        transport=transport,
    ).probe(projection())

    assert result.state == "unhealthy"
    assert result.exit_ip is None
    assert result.error is not None and result.error["code"] == "PROXY_PROBE_FAILED"


@pytest.mark.asyncio
async def test_production_probe_configures_the_proxy_and_never_falls_back_to_direct(monkeypatch):
    captured: dict[str, object] = {}

    class Response:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self):
            yield b'{"ip":"1.1.1.1"}'

    class Client:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, method: str, url: str):
            captured["request"] = (method, url)
            return Response()

    monkeypatch.setattr(httpx, "AsyncClient", Client)

    result = await HttpProxyProbe(MemoryCredentials()).probe(projection())  # type: ignore[arg-type]

    configured_proxy = captured["proxy"]
    assert isinstance(configured_proxy, httpx.Proxy)
    assert str(configured_proxy.url) == "http://proxy.example:8000"
    assert configured_proxy.raw_auth == (b"proxy-user", b"proxy-secret")
    assert captured["transport"] is None
    assert captured["trust_env"] is False
    assert captured["request"] == ("GET", PROBE_URL)
    assert result.state == "healthy"


@pytest.mark.asyncio
async def test_system_credential_store_failures_are_mapped_without_details():
    class UnavailableCredentials(MemoryCredentials):
        def read(self, key: str) -> bytes | None:
            raise CredentialStoreUnavailableError(f"secret path {key}")

    with pytest.raises(CredentialStoreError, match="无法读取系统凭据库") as error:
        await HttpProxyProbe(UnavailableCredentials()).probe(projection())  # type: ignore[arg-type]

    assert "proxy-endpoint" not in str(error.value)
