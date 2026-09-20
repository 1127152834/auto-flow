from __future__ import annotations

import asyncio
import json
import smtplib
from collections.abc import Mapping
from email.message import EmailMessage
from typing import Any

import httpx

MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class HttpIntegrationGateway:
    async def call(self, integration: str, payload: Mapping[str, Any]) -> Any:
        if integration == "telegram":
            return await self._telegram(payload)
        if integration == "smtp_qq":
            return await asyncio.to_thread(self._smtp_qq, payload)
        if integration != "http":
            raise RuntimeError("不支持的外部服务")
        return await self._http(payload)

    async def _telegram(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        token = str(payload.get("botToken") or "")
        chat_id = str(payload.get("chatId") or "")
        message = str(payload.get("message") or "")
        title = str(payload.get("title") or "")
        response = await self._http(
            {
                "url": f"https://api.telegram.org/bot{token}/sendMessage",
                "method": "POST",
                "json": {
                    "chat_id": chat_id,
                    "text": f"{title}\n{message}" if title else message,
                },
                "timeoutSeconds": payload.get("timeoutSeconds", 30),
                "followRedirects": False,
                "verifySSL": True,
            }
        )
        body = response.get("body")
        if (
            response.get("statusCode") != 200
            or not isinstance(body, Mapping)
            or body.get("ok") is not True
        ):
            raise RuntimeError("Telegram通知失败")
        return {"ok": True}

    @staticmethod
    def _smtp_qq(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        sender = str(payload.get("senderEmail") or "")
        recipient = str(payload.get("recipientEmail") or "")
        auth_code = str(payload.get("authCode") or "")
        message = EmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = str(payload.get("subject") or "(无标题)")
        message.set_content(str(payload.get("content") or ""))
        try:
            with smtplib.SMTP_SSL(
                "smtp.qq.com", 465, timeout=float(payload.get("timeoutSeconds", 30))
            ) as client:
                client.login(sender, auth_code)
                client.send_message(message)
        except smtplib.SMTPAuthenticationError as error:
            raise RuntimeError("邮箱认证失败，请检查邮箱地址和授权码") from error
        except (OSError, smtplib.SMTPException) as error:
            raise RuntimeError("发送邮件失败") from error
        return {"accepted": True}

    async def _http(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
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
