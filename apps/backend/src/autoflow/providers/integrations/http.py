from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx

MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class HttpIntegrationGateway:
    async def call(self, integration: str, payload: Mapping[str, Any]) -> Any:
        if integration != "http":
            raise RuntimeError(f"不支持的外部服务: {integration}")
        url = payload.get("url")
        method = payload.get("method")
        if not isinstance(url, str) or not url:
            raise RuntimeError("HTTP请求地址不能为空")
        if not isinstance(method, str) or not method:
            raise RuntimeError("HTTP请求方法不能为空")
        timeout = float(payload.get("timeoutSeconds", 30))
        try:
            async with (
                httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=bool(payload.get("followRedirects", False)),
                    verify=bool(payload.get("verifySSL", True)),
                    trust_env=False,
                    cookies=dict(payload.get("cookies") or {}),
                ) as client,
                client.stream(
                    method,
                    url,
                    headers=dict(payload.get("headers") or {}),
                    json=payload.get("json"),
                    content=payload.get("content"),
                    data=payload.get("form"),
                ) as response,
            ):
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise RuntimeError("HTTP响应超过8 MiB限制")
                raw = bytes(content)
                try:
                    body: Any = json.loads(raw) if raw else ""
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body = raw.decode(response.encoding or "utf-8", errors="replace")
                return {
                    "statusCode": response.status_code,
                    "body": body,
                    "headers": dict(response.headers),
                    "cookies": dict(response.cookies),
                }
        except httpx.TimeoutException as error:
            raise RuntimeError(f"HTTP请求超时 ({timeout:g}秒)") from error
        except httpx.RequestError as error:
            raise RuntimeError("无法连接到HTTP服务") from error
