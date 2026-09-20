from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import httpx
import pytest

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.models import ModelInvocationResult
from tests.contract.test_models_api import _provider
from tests.fixtures.model_management import FakeCredentialStore, FakeModelGateway


class AssistantGateway(FakeModelGateway):
    def __init__(self, *, use_tool: bool = False) -> None:
        super().__init__()
        self.use_tool = use_tool
        self.invocations: list[Mapping[str, Any]] = []

    async def invoke(self, connection, secret, model_key, payload):
        self.invocations.append(payload)
        if self.use_tool and len(self.invocations) == 1:
            return ModelInvocationResult(
                model_key,
                "",
                "",
                {},
                "http://127.0.0.1:9999/v1/chat/completions",
                (
                    {
                        "id": "tool-http-1",
                        "name": "client_action",
                        "arguments": {
                            "action": "add_nodes",
                            "payload": {"nodes": [{"type": "open_page"}]},
                        },
                    },
                ),
            )
        return ModelInvocationResult(
            model_key,
            "已完成",
            "",
            {},
            "http://127.0.0.1:9999/v1/chat/completions",
        )


async def _client(tmp_path, gateway: AssistantGateway):
    app = create_app(
        Settings(
            data_dir=str(tmp_path),
            instance_id="assistant-http",
            instance_token="test-token",
        ),
        credential_store=FakeCredentialStore(),
        model_gateway=gateway,
    )
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"x-autoflow-token": "test-token"},
    )
    response = await client.post(
        "/api/v1/model-providers/connect",
        json=_provider(
            [
                {
                    "modelKey": "Model-A",
                    "displayName": "A",
                    "tagsJson": [],
                    "contextWindow": None,
                    "enabled": True,
                    "description": "",
                }
            ]
        ),
    )
    assert response.status_code == 201
    return app, client, response.json()["models"][0]["id"]


@pytest.mark.asyncio
async def test_http_chat_uses_managed_model_and_persists_session(tmp_path) -> None:
    gateway = AssistantGateway()
    app, client, model_id = await _client(tmp_path, gateway)
    try:
        response = await client.post(
            "/api/ai-assistant/chat",
            json={
                "sessionId": "http-session",
                "message": "说明当前画布",
                "config": {
                    "modelId": model_id,
                    "temperature": 0.25,
                    "maxTokens": 512,
                    "enableTools": False,
                },
                "workflowContext": {"revision": 4},
                "images": ["data:image/png;base64,YQ=="],
            },
        )
        assert response.status_code == 200
        restored = await client.get("/api/ai-assistant/sessions/http-session")
    finally:
        await client.aclose()

    assert restored.json()["status"] == "completed"
    assert restored.json()["messages"][-1]["content"] == "已完成"
    assert gateway.invocations[0]["temperature"] == 0.25
    assert gateway.invocations[0]["maxTokens"] == 512
    assert gateway.invocations[0]["messages"][-1]["content"] == [
        {"type": "text", "text": "说明当前画布"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,YQ=="}},
    ]
    assert "apiKey" not in str(gateway.invocations)
    assert app.state.workflow_services.assistant is not None


@pytest.mark.asyncio
async def test_http_event_command_resumes_exact_pending_action(tmp_path) -> None:
    gateway = AssistantGateway(use_tool=True)
    _app, client, model_id = await _client(tmp_path, gateway)
    try:
        chat = asyncio.create_task(
            client.post(
                "/api/ai-assistant/chat",
                json={
                    "sessionId": "tool-session",
                    "message": "添加打开网页节点",
                    "config": {"modelId": model_id},
                    "workflowContext": {"nodes": []},
                },
            )
        )
        pending = None
        for _ in range(100):
            response = await client.get("/api/ai-assistant/sessions/tool-session")
            if response.status_code == 200 and response.json()["status"] == "waiting_for_action":
                pending = response.json()["pendingAction"]
                break
            await asyncio.sleep(0.01)
        assert pending == {
            "commandId": "tool-http-1",
            "action": "add_nodes",
            "payload": {"nodes": [{"type": "open_page"}]},
        }

        ack = {
            "commandId": "claim-tool-http-1",
            "event": "ai_client_action_claim",
            "data": {
                "session_id": "tool-session",
                "tool_call_id": "tool-http-1",
                "executor_id": "http-test-window",
            },
        }
        claim = await client.post("/api/events/commands", json=ack)
        ack = {
            "commandId": "ack-tool-http-1",
            "event": "ai_client_action_ack",
            "data": {
                "session_id": "tool-session",
                "tool_call_id": "tool-http-1",
                "claim_command_id": "claim-tool-http-1",
                "result": {"success": True, "data": {"nodeIds": ["node-1"]}},
            },
        }
        receipt = await client.post("/api/events/commands", json=ack)
        repeated = await client.post("/api/events/commands", json=ack)
        assert claim.status_code == 200, claim.text
        assert receipt.status_code == 200, receipt.text
        assert repeated.json() == receipt.json()
        completed = await asyncio.wait_for(chat, 2)
    finally:
        await client.aclose()

    assert completed.status_code == 200
    assert completed.json()["message"]["content"] == "已完成"
    assert len(gateway.invocations) == 2
