from __future__ import annotations

from email.message import EmailMessage
from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.integrations import WorkflowIntegrationGateway


def test_imap_gateway_filters_parses_and_marks_matching_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = EmailMessage()
    first["From"] = "Other <other@example.com>"
    first["Subject"] = "忽略"
    first.set_content("other")
    second = EmailMessage()
    second["From"] = "Sender <sender@example.com>"
    second["Subject"] = "订单 已完成"
    second["Date"] = "Sun, 21 Sep 2026 10:00:00 +0800"
    second.set_content("正文")
    seen: dict[str, Any] = {"stored": []}

    class Client:
        def __init__(self, host: str, port: int, timeout: float) -> None:
            seen.update(host=host, port=port, timeout=timeout)

        def login(self, account: str, password: str) -> None:
            seen.update(account=account, password=password)

        def select(self, mailbox: str) -> None:
            seen["mailbox"] = mailbox

        def search(self, charset: Any, criteria: str) -> tuple[str, list[bytes]]:
            seen.update(charset=charset, criteria=criteria)
            return "OK", [b"1 2"]

        def fetch(self, email_id: bytes, query: str) -> tuple[str, list[Any]]:
            message = first if email_id == b"1" else second
            return "OK", [(query.encode(), message.as_bytes())]

        def store(self, email_id: bytes, operation: str, flag: str) -> None:
            seen["stored"].append((email_id, operation, flag))

        def close(self) -> None:
            seen["closed"] = True

        def logout(self) -> None:
            seen["loggedOut"] = True

    monkeypatch.setattr(
        "autoflow.providers.integrations.gateway.imaplib.IMAP4_SSL", Client
    )

    result = WorkflowIntegrationGateway._imap_unseen(
        {
            "server": "imap.example.com",
            "port": 993,
            "account": "user@example.com",
            "password": "secret",
            "fromFilter": "sender@",
            "subjectFilter": "完成",
            "timeoutSeconds": 7,
        }
    )

    assert [{key: value for key, value in result[0].items() if key != "timestamp"}] == [
        {
            "from": "sender@example.com",
            "subject": "订单 已完成",
            "date": "Mon, 21 Sep 2026 10:00:00 +0800",
            "body": "正文\n",
        }
    ]
    assert seen == {
        "stored": [(b"2", "+FLAGS", "\\Seen")],
        "host": "imap.example.com",
        "port": 993,
        "timeout": 7.0,
        "account": "user@example.com",
        "password": "secret",
        "mailbox": "INBOX",
        "charset": None,
        "criteria": "UNSEEN",
        "closed": True,
        "loggedOut": True,
    }


@pytest.mark.asyncio
async def test_email_trigger_retries_then_writes_last_matching_email() -> None:
    message = {
        "from": "sender@example.com",
        "subject": "完成",
        "date": "date",
        "body": "正文",
        "timestamp": "timestamp",
    }

    class Gateway:
        def __init__(self) -> None:
            self.calls = 0

        async def call(self, integration: str, payload: Any) -> Any:
            assert integration == "imap_unseen"
            assert payload["password"] == "secret"
            self.calls += 1
            if self.calls == 1:
                raise OSError("temporary")
            return [message]

    gateway = Gateway()
    context = ExecutionContext(external_integrations=gateway)
    executor = build_production_executor_registry().get("email_trigger")

    assert executor is not None
    result = await executor.execute(
        {
            "emailServer": "imap.example.com",
            "emailAccount": "user@example.com",
            "emailPassword": "secret",
            "checkInterval": 0,
            "timeout": 1,
            "saveToVariable": "mail",
        },
        context,
    )

    assert result.success is True
    assert result.message == "收到新邮件: 完成"
    assert result.data == message
    assert context.variables["mail"] == message
    assert gateway.calls == 2


@pytest.mark.asyncio
async def test_email_trigger_requires_connection_fields_and_times_out() -> None:
    executor = build_production_executor_registry().get("email_trigger")
    assert executor is not None
    missing = await executor.execute({}, ExecutionContext())
    assert missing.error == "邮件服务器、账号和密码不能为空"

    class EmptyGateway:
        async def call(self, _integration: str, _payload: Any) -> list[Any]:
            return []

    timed_out = await executor.execute(
        {
            "emailServer": "imap.example.com",
            "emailAccount": "user@example.com",
            "emailPassword": "secret",
            "checkInterval": 1,
            "timeout": 1,
        },
        ExecutionContext(external_integrations=EmptyGateway()),
    )
    assert timed_out.error == "邮件监控等待超时（1秒）"
