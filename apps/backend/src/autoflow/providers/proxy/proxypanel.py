import ipaddress
import json
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import httpx

from autoflow.domain.proxies.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderSchemaError,
    ProviderUnavailableError,
)
from autoflow.domain.proxies.models import (
    Capability,
    Endpoint,
    ProviderCredentials,
    ProviderPage,
    ProviderProxy,
    unavailable_capabilities,
)

BASE_URL = "https://proxypanel.io/api/v1/"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class ProxyPanelHttpError(ProviderError):
    def __init__(self, code: str, message: str, *, retry_after: int | None = None):
        super().__init__(message, retry_after_seconds=retry_after)
        self.code = code


def retry_after_seconds(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        if value.isdecimal():
            return max(0, int(value))
        deadline = parsedate_to_datetime(value)
        if deadline.tzinfo is None:
            return None
        return max(0, int((deadline - datetime.now(UTC)).total_seconds()))
    except (ValueError, TypeError, OverflowError):
        return None


class ProxyPanelReadProvider:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        self._transport = transport

    async def _request(self, api_key: bytes, path: str) -> object:
        try:
            key = api_key.decode("utf-8")
            if not key or any(ord(char) < 32 or ord(char) > 126 for char in key):
                raise ProviderAuthenticationError("API Key 格式无效，请重新输入")
            async with (
                httpx.AsyncClient(
                    base_url=BASE_URL,
                    transport=self._transport,
                    timeout=15,
                    follow_redirects=False,
                    trust_env=False,
                ) as client,
                client.stream(
                    "GET", path, headers={"Authorization": f"Bearer {key}"}
                ) as response,
            ):
                if response.status_code in (401, 403):
                    raise ProviderAuthenticationError(
                        "ProxyPanel 拒绝了此 API Key，请检查连接设置"
                    )
                if response.status_code == 429:
                    raise ProxyPanelHttpError(
                        "PROXYPANEL_RATE_LIMITED",
                        "ProxyPanel 请求过于频繁，请稍后重试",
                        retry_after=retry_after_seconds(
                            response.headers.get("retry-after")
                        ),
                    )
                if response.is_redirect:
                    raise ProviderUnavailableError(
                        "ProxyPanel 返回了重定向，未转发认证信息"
                    )
                if response.status_code >= 500:
                    raise ProviderUnavailableError("ProxyPanel 服务暂时不可用")
                if not response.is_success:
                    raise ProxyPanelHttpError(
                        "PROXYPANEL_UNAVAILABLE", "ProxyPanel 未接受此请求"
                    )
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > MAX_RESPONSE_BYTES:
                        raise ProviderSchemaError("代理列表响应过大，未更新本地数据")
                try:
                    return json.loads(chunks)
                except (ValueError, UnicodeDecodeError):
                    raise ProviderSchemaError(
                        "ProxyPanel 未返回有效 JSON，未更新本地数据"
                    ) from None
        except UnicodeDecodeError:
            raise ProviderAuthenticationError("API Key 格式无效，请重新输入") from None
        except httpx.HTTPError:
            # Never surface the request URL, authentication header or raw body.
            raise ProviderUnavailableError(
                "无法连接 ProxyPanel，请检查网络后重试"
            ) from None

    async def verify(self, api_key: bytes) -> ProviderPage:
        await self._request(api_key, "proxies")
        # A successful authenticated read is evidence only of authentication.
        return ProviderPage(items=(), completeness="unknown")

    async def list_proxies(self, api_key: bytes) -> ProviderPage:
        payload = _object(await self._request(api_key, "proxies"))
        # Observed v1 returns the complete account fleet, without pagination.
        # A new envelope must not silently mark unseen local proxies as missing.
        if set(payload) != {"proxies"} or not isinstance(payload["proxies"], list):
            raise _schema()
        items = tuple(parse_proxy(item) for item in payload["proxies"])
        if len({item.provider_id for item in items}) != len(items):
            raise _schema()
        return ProviderPage(items=items, completeness="complete", total=len(items))

    async def get_credentials(self, api_key: bytes, provider_id: str) -> ProviderCredentials:
        body = _object(await self._request(api_key, f"proxies/{_id(provider_id)}/credentials"))
        return ProviderCredentials(
            username=_string(body.get("username")),
            password=_string(body.get("password")),
            http_endpoint=_endpoint(body, "http_port"),
            socks5_endpoint=_endpoint(body, "socks5_port"),
        )


def _schema() -> ProviderSchemaError:
    return ProviderSchemaError("ProxyPanel 响应格式不符合已核验契约；本地数据保持不变")


def _object(value: object) -> dict:
    if not isinstance(value, dict):
        raise _schema()
    return value


def _string(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise _schema()
    return value


def _id(value: object) -> str:
    result = _string(value)
    if result in {".", ".."} or len(result) > 240 or not re.fullmatch(r"[A-Za-z0-9_.-]+", result):
        raise _schema()
    return quote(result, safe="")


def _optional(value: object) -> str | None:
    if value is None or value == "":
        return None
    return _string(value)


def _endpoint(body: dict, port_key: str) -> Endpoint:
    host = _string(body.get("host"))
    port = body.get(port_key)
    if len(host) > 255 or any(ord(c) < 33 or c in "/\\@?#[]" for c in host):
        raise _schema()
    if type(port) is not int or not 1 <= port <= 65535:
        raise _schema()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9.-]+", host):
            raise _schema() from None
    return Endpoint(host, port)


def parse_proxy(value: object) -> ProviderProxy:
    body = _object(value)
    provider_id = _id(body.get("id"))
    state = _string(body.get("state"))
    location = _object(body.get("location") or {})
    connection = _object(body.get("connection") or {})
    protocols = connection.get("protocols", [])
    if not isinstance(protocols, list) or not all(isinstance(p, str) for p in protocols):
        raise _schema()
    http = _endpoint(connection, "http_port") if "http" in protocols else None
    socks = _endpoint(connection, "socks5_port") if "socks5" in protocols else None
    expires = body.get("expires_at")
    try:
        expiry = datetime.fromisoformat(_string(expires)) if expires is not None else None
        if expiry and expiry.tzinfo is None:
            raise ValueError
        last_ip = _optional(body.get("last_ip"))
        address = str(ipaddress.ip_address(last_ip)) if last_ip else None
    except (ValueError, TypeError):
        raise _schema() from None
    available = state == "active" and bool(http or socks)
    caps = tuple(
        Capability(key=c.key, available=True, evidence="fixture-verified", reason=None)
        if c.key in {"remote_status", "subscription_expiry"} or c.key == "credentials" and available
        else c for c in unavailable_capabilities()
    )
    return ProviderProxy(
        provider_id=provider_id, name=_optional(body.get("label")) or provider_id,
        remote_status=state, city=_optional(location.get("city")),
        region=_optional(location.get("state_code")), carrier=_optional(location.get("carrier")),
        exit_ip=address, http_endpoint=http, socks5_endpoint=socks,
        credential_available=available, subscription_expires_at=expiry, capabilities=caps,
    )
