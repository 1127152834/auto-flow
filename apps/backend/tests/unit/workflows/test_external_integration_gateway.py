from __future__ import annotations

from typing import Any, Self
from unittest.mock import AsyncMock

import pytest
from autoflow.providers.integrations import WorkflowIntegrationGateway


@pytest.mark.asyncio
async def test_telegram_gateway_uses_bot_api_without_returning_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = WorkflowIntegrationGateway()
    request = AsyncMock(return_value={"statusCode": 200, "body": {"ok": True}})
    monkeypatch.setattr(gateway, "_http", request)

    result = await gateway.call(
        "telegram",
        {
            "botToken": "secret-token",
            "chatId": "123",
            "title": "通知",
            "message": "完成",
            "timeoutSeconds": 8,
        },
    )

    assert result == {"ok": True}
    payload = request.await_args.args[0]
    assert payload["url"] == "https://api.telegram.org/botsecret-token/sendMessage"
    assert payload["json"] == {"chat_id": "123", "text": "通知\n完成"}
    assert "secret-token" not in str(result)


def test_qq_smtp_gateway_sends_utf8_message_without_returning_auth_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    class SMTP:
        def __init__(self, host: str, port: int, timeout: float) -> None:
            seen.update(host=host, port=port, timeout=timeout)

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def login(self, sender: str, auth_code: str) -> None:
            seen.update(sender=sender, auth_code=auth_code)

        def send_message(self, message: Any) -> None:
            seen["message"] = message

    monkeypatch.setattr(
        "autoflow.providers.integrations.gateway.smtplib.SMTP_SSL", SMTP
    )

    result = WorkflowIntegrationGateway._smtp_qq(
        {
            "senderEmail": "from@qq.com",
            "authCode": "smtp-secret",
            "recipientEmail": "to@example.com",
            "subject": "主题",
            "content": "正文",
            "timeoutSeconds": 9,
        }
    )

    assert result == {"accepted": True}
    assert seen["host"] == "smtp.qq.com"
    assert seen["port"] == 465
    assert seen["message"]["Subject"] == "主题"
    assert "smtp-secret" not in str(result)
