from __future__ import annotations

from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext


class RecordingGateway:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call(self, integration: str, payload: dict[str, Any]) -> Any:
        self.calls.append((integration, payload))
        return self.response


@pytest.mark.asyncio
async def test_telegram_notification_uses_resolved_managed_values() -> None:
    gateway = RecordingGateway({"ok": True})
    context = ExecutionContext(
        variables={"token": "bot-secret", "chat": "123", "name": "AutoFlow"},
        sensitive_variables={"token"},
        external_integrations=gateway,
    )
    executor = build_production_executor_registry().get("notify_telegram")

    assert executor is not None
    result = await executor.execute(
        {
            "botToken": "{token}",
            "chatId": "{chat}",
            "message": "完成 {name}",
            "title": "通知",
        },
        context,
    )

    assert result.success is True
    assert gateway.calls == [
        (
            "telegram",
            {
                "botToken": "bot-secret",
                "chatId": "123",
                "title": "通知",
                "message": "完成 AutoFlow",
                "timeoutSeconds": 30.0,
            },
        )
    ]
    assert context.node_uses_sensitive_values is True
    assert "bot-secret" not in result.message


@pytest.mark.asyncio
async def test_email_uses_qq_smtp_contract_without_exposing_auth_code() -> None:
    gateway = RecordingGateway({"accepted": True})
    context = ExecutionContext(
        variables={"auth": "smtp-secret", "recipient": "to@example.com"},
        sensitive_variables={"auth"},
        external_integrations=gateway,
    )
    executor = build_production_executor_registry().get("send_email")

    assert executor is not None
    result = await executor.execute(
        {
            "senderEmail": "from@qq.com",
            "authCode": "{auth}",
            "recipientEmail": "{recipient}",
            "emailSubject": "主题",
            "emailContent": "正文",
        },
        context,
    )

    assert result.success is True
    assert result.data == {"recipient": "to@example.com", "subject": "主题"}
    assert gateway.calls == [
        (
            "smtp_qq",
            {
                "senderEmail": "from@qq.com",
                "authCode": "smtp-secret",
                "recipientEmail": "to@example.com",
                "subject": "主题",
                "content": "正文",
                "timeoutSeconds": 30.0,
            },
        )
    ]
    assert "smtp-secret" not in result.message
