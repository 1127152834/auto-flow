"""Read-only ProxyPanel transport; unknown response shapes fail closed.

The docs establish authentication and endpoint paths, not the response schema.
Until a real response is reviewed, verification may validate credentials but
synchronization must not invent a projection from guessed fields.
"""

import json
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from autoflow.domain.proxies.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderSchemaError,
    ProviderUnavailableError,
)
from autoflow.domain.proxies.models import ProviderPage

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

    async def _list_response(self, api_key: bytes) -> object:
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
                    "GET", "proxies", headers={"Authorization": f"Bearer {key}"}
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
                        "PROXYPANEL_UNAVAILABLE", "ProxyPanel 未接受列表请求"
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
        await self._list_response(api_key)
        # A successful authenticated read is evidence only of authentication.
        return ProviderPage(items=(), completeness="unknown")

    async def list_proxies(self, api_key: bytes) -> ProviderPage:
        await self._list_response(api_key)
        raise ProviderSchemaError(
            "API Key 已通过验证，但代理列表字段尚未完成真实响应核验；本地数据保持不变"
        )
