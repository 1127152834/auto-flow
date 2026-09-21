from __future__ import annotations

from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext


class RecordingGateway:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call(self, integration: str, payload: dict[str, Any]) -> Any:
        self.calls.append((integration, payload))
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_api_request_preserves_source_status_semantics_and_sets_response() -> (
    None
):
    gateway = RecordingGateway(
        [{"statusCode": 418, "body": {"echo": "张三"}, "headers": {}, "cookies": {}}]
    )
    context = ExecutionContext(
        variables={"name": "张三", "token": "secret"},
        external_integrations=gateway,
    )
    executor = build_production_executor_registry().get("api_request")

    assert executor is not None
    result = await executor.execute(
        {
            "requestUrl": "http://127.0.0.1/api/{name}",
            "requestMethod": "POST",
            "requestHeaders": '{"Authorization":"Bearer {token}"}',
            "requestCookies": "session={token}",
            "requestBody": '{"name":"{name}"}',
            "requestTimeout": 7,
            "variableName": "api_response",
        },
        context,
    )

    assert result.success is True
    assert result.data == {"status_code": 418, "response": {"echo": "张三"}}
    assert context.variables["api_response"] == {"echo": "张三"}
    assert gateway.calls == [
        (
            "http",
            {
                "url": "http://127.0.0.1/api/张三",
                "method": "POST",
                "headers": {"Authorization": "Bearer secret"},
                "cookies": {"session": "secret"},
                "json": {"name": "张三"},
                "content": None,
                "form": None,
                "timeoutSeconds": 7.0,
                "followRedirects": False,
                "verifySSL": True,
            },
        )
    ]


@pytest.mark.asyncio
async def test_api_trigger_polls_until_json_path_condition_matches() -> None:
    gateway = RecordingGateway(
        [
            {
                "statusCode": 200,
                "body": {"data": {"status": "pending"}},
                "headers": {},
                "cookies": {},
            },
            {
                "statusCode": 200,
                "body": {"data": {"status": "ready"}},
                "headers": {},
                "cookies": {},
            },
        ]
    )
    context = ExecutionContext(external_integrations=gateway)
    executor = build_production_executor_registry().get("api_trigger")

    assert executor is not None
    result = await executor.execute(
        {
            "apiUrl": "http://127.0.0.1/status",
            "method": "GET",
            "headers": "{}",
            "conditionPath": "$.data.status",
            "conditionValue": "ready",
            "conditionOperator": "==",
            "checkInterval": 0,
            "timeout": 1,
            "saveToVariable": "api_result",
        },
        context,
    )

    assert result.success is True
    assert result.message == "API条件满足（第2次检查）: $.data.status = ready"
    assert context.variables["api_result"] == {"data": {"status": "ready"}}
    assert [call[1]["method"] for call in gateway.calls] == ["GET", "GET"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config", "error"),
    [
        ({}, "API地址不能为空"),
        (
            {"apiUrl": "http://127.0.0.1", "headers": "{"},
            "请求头格式错误，必须是有效的JSON",
        ),
        (
            {"apiUrl": "http://127.0.0.1", "method": "POST", "body": "{"},
            "请求体格式错误，必须是有效的JSON",
        ),
    ],
)
async def test_api_trigger_rejects_invalid_source_configuration(
    config: dict[str, Any], error: str
) -> None:
    executor = build_production_executor_registry().get("api_trigger")

    assert executor is not None
    result = await executor.execute(config, ExecutionContext())

    assert result.success is False
    assert result.error == error


@pytest.mark.asyncio
async def test_webhook_request_saves_metadata_and_rejects_non_success_status() -> None:
    gateway = RecordingGateway(
        [
            {
                "statusCode": 503,
                "body": "temporarily unavailable",
                "headers": {"retry-after": "3"},
                "cookies": {"attempt": "1"},
            }
        ]
    )
    context = ExecutionContext(external_integrations=gateway)
    executor = build_production_executor_registry().get("webhook_request")

    assert executor is not None
    result = await executor.execute(
        {
            "url": "http://127.0.0.1/hook",
            "method": "POST",
            "headers": '{"X-Test":"yes"}',
            "cookies": '{"sid":"1"}',
            "bodyType": "raw",
            "body": "hello",
            "timeout": 4,
            "followRedirects": True,
            "verifySSL": False,
            "saveResponse": True,
            "responseVariable": "response",
            "saveStatus": True,
            "statusVariable": "status",
            "saveHeaders": True,
            "headersVariable": "response_headers",
            "saveCookies": True,
            "cookiesVariable": "response_cookies",
        },
        context,
    )

    assert result.success is False
    assert result.error == "HTTP 503: temporarily unavailable"
    assert context.variables == {
        "response": "temporarily unavailable",
        "status": 503,
        "response_headers": {"retry-after": "3"},
        "response_cookies": {"attempt": "1"},
    }
    assert gateway.calls[0][1]["content"] == "hello"
    assert gateway.calls[0][1]["followRedirects"] is True
    assert gateway.calls[0][1]["verifySSL"] is False


@pytest.mark.asyncio
async def test_notify_webhook_posts_resolved_json_message() -> None:
    gateway = RecordingGateway(
        [{"statusCode": 204, "body": "", "headers": {}, "cookies": {}}]
    )
    context = ExecutionContext(
        variables={"name": "AutoFlow"}, external_integrations=gateway
    )
    executor = build_production_executor_registry().get("notify_webhook")

    assert executor is not None
    result = await executor.execute(
        {
            "webhookUrl": "http://127.0.0.1/notify",
            "message": '{"message":"{name}"}',
        },
        context,
    )

    assert result.success is True
    assert gateway.calls[0][1]["json"] == {"message": "AutoFlow"}
    assert gateway.calls[0][1]["method"] == "POST"
