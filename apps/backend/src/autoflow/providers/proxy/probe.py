"""A bounded HTTPS probe through a configured proxy, never an arbitrary URL."""

import ipaddress
import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import httpx

from autoflow.domain.credentials import CredentialStore, CredentialStoreUnavailableError
from autoflow.domain.proxies.errors import (
    CapabilityUnavailableError,
    CredentialStoreError,
)
from autoflow.domain.proxies.models import Health, Projection, ProviderCredentials

PROBE_URL = "https://api.ipify.org?format=json"


class HttpProxyProbe:
    def __init__(
        self,
        credentials: CredentialStore,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        load_credentials: Callable[[Projection], Awaitable[ProviderCredentials]] | None = None,
    ):
        self._credentials = credentials
        self._transport = transport
        self._load_credentials = load_credentials

    async def probe(self, projection: Projection) -> Health:
        endpoint = projection.socks5_endpoint or projection.http_endpoint
        if endpoint is None or not projection.credential_available:
            raise CapabilityUnavailableError("代理端点或凭据尚未验证，无法检测连接")
        try:
            if self._load_credentials is not None:
                value = await self._load_credentials(projection)
                username, password = value.username, value.password
            else:
                raw = self._credentials.read(f"proxy-endpoint:{projection.id}")
                if raw is None:
                    raise CredentialStoreError("代理凭据不可用，请重新同步连接信息")
                credentials = json.loads(raw)
                username, password = credentials["username"], credentials["password"]
                if not isinstance(username, str) or not isinstance(password, str):
                    raise TypeError("invalid credentials")
        except CredentialStoreUnavailableError:
            raise CredentialStoreError("无法读取系统凭据库") from None
        except (ValueError, KeyError, TypeError):
            raise CredentialStoreError("代理凭据格式无效，请重新同步连接信息") from None
        scheme = "socks5" if projection.socks5_endpoint else "http"
        host = endpoint.host
        # Ports and endpoints only originate in a reviewed Provider projection.
        if (
            not host
            or any(char in host for char in "/?#@\\\r\n ")
            or not 1 <= endpoint.port <= 65535
        ):
            raise CapabilityUnavailableError("代理地址无效，无法检测连接")
        try:
            parsed = ipaddress.ip_address(host.strip("[]"))
            if not parsed.is_global:
                raise CapabilityUnavailableError("不允许使用本机或内网地址作为远程代理")
            if parsed.version == 6:
                host = f"[{parsed}]"
        except ValueError:
            if host.lower() == "localhost" or host.lower().endswith(".localhost"):
                raise CapabilityUnavailableError("不允许使用本机地址作为远程代理")
        started = time.perf_counter()
        checked_at = datetime.now(UTC)
        try:
            # A custom transport is only supplied by tests; production uses the
            # configured proxy with separate auth, keeping secrets out of URLs.
            proxy = (
                None
                if self._transport
                else httpx.Proxy(
                    f"{scheme}://{host}:{endpoint.port}", auth=(username, password)
                )
            )
            async with (
                httpx.AsyncClient(
                    proxy=proxy,
                    transport=self._transport,
                    timeout=10,
                    follow_redirects=False,
                    trust_env=False,
                ) as client,
                client.stream("GET", PROBE_URL) as response,
            ):
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 4096:
                        raise ValueError("oversized probe response")
                parsed_address = ipaddress.ip_address(json.loads(body)["ip"])
                if not parsed_address.is_global:
                    raise ValueError("probe returned a non-public IP address")
                address = str(parsed_address)
            return Health(
                state="healthy",
                latency_ms=round((time.perf_counter() - started) * 1000, 1),
                exit_ip=address,
                checked_at=checked_at,
                source="local_probe",
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            message = (
                f"{scheme.upper()} 代理 HTTPS 检测超时，请检查网络或尝试另一协议"
                if isinstance(exc, httpx.TimeoutException)
                else f"{scheme.upper()} 代理 HTTPS 检测失败，请检查端点与凭据"
            )
            return Health(
                state="unhealthy",
                checked_at=checked_at,
                source="local_probe",
                error={
                    "code": "PROXY_PROBE_FAILED",
                    "message": message,
                },
            )
