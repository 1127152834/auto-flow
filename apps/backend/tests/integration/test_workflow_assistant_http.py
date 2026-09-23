from __future__ import annotations

import asyncio
import base64
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import faster_whisper
import httpx
import openpyxl
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
        image_reference = restored.json()["messages"][0]["images"][0]
        image = await client.get(
            "/api/ai-assistant/artifacts/attachment/"
            + image_reference.removeprefix("assistant-attachment://")
        )
    finally:
        await client.aclose()

    assert restored.json()["status"] == "completed"
    assert restored.json()["messages"][-1]["content"] == "已完成"
    assert image_reference.startswith("assistant-attachment://")
    assert image.status_code == 200
    assert image.content == b"a"
    assert image.headers["content-type"] == "image/png"
    assert gateway.invocations[0]["temperature"] == 0.25
    assert gateway.invocations[0]["maxTokens"] == 512
    assert gateway.invocations[0]["messages"][-1]["content"] == [
        {"type": "text", "text": "说明当前画布"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,YQ=="}},
    ]
    assert "apiKey" not in str(gateway.invocations)
    assert app.state.workflow_services.assistant is not None
    database = (tmp_path / "data" / "autoflow.sqlite3").read_bytes()
    assert b"data:image/png;base64,YQ==" not in database
    checkpoint = (
        tmp_path / "workspace" / "assistant" / "checkpoints.sqlite3"
    ).read_bytes()
    assert b"data:image/png;base64,YQ==" not in checkpoint
    assert (
        len(list((tmp_path / "workspace" / "assistant" / "attachments").glob("*.png")))
        == 1
    )


@pytest.mark.asyncio
async def test_http_chat_rejects_non_local_image_references(tmp_path) -> None:
    _app, client, model_id = await _client(tmp_path, AssistantGateway())
    try:
        response = await client.post(
            "/api/ai-assistant/chat",
            json={
                "sessionId": "invalid-image",
                "message": "分析图片",
                "config": {"modelId": model_id, "enableTools": False},
                "images": ["https://outside.example/image.png"],
            },
        )
    finally:
        await client.aclose()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ASSISTANT_ATTACHMENT_INVALID"


@pytest.mark.asyncio
async def test_http_extracts_text_and_xlsx_attachments_with_source_limits(
    tmp_path,
) -> None:
    _app, client, _model_id = await _client(tmp_path, AssistantGateway())
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "数据"
    sheet.append(["姓名", "数量"])
    sheet.append(["甲", 2])
    content = io.BytesIO()
    workbook.save(content)
    workbook.close()
    try:
        text = await client.post(
            "/api/ai-assistant/extract-file",
            json={
                "filename": "说明.txt",
                "content_base64": base64.b64encode("中文内容".encode()).decode(),
            },
        )
        xlsx = await client.post(
            "/api/ai-assistant/extract-file",
            json={
                "filename": "数据.xlsx",
                "content_base64": base64.b64encode(content.getvalue()).decode(),
            },
        )
        invalid = await client.post(
            "/api/ai-assistant/extract-file",
            json={"filename": "损坏.pdf", "content_base64": "%%%"},
        )
    finally:
        await client.aclose()

    assert text.json() == {"success": True, "text": "中文内容", "error": ""}
    assert xlsx.status_code == 200
    assert xlsx.json() == {
        "success": True,
        "text": "# 工作表: 数据\n姓名\t数量\n甲\t2",
        "error": "",
    }
    assert invalid.status_code == 200
    assert invalid.json()["success"] is False
    assert invalid.json()["text"] == ""
    assert invalid.json()["error"].startswith("文件解码失败")


@pytest.mark.asyncio
async def test_http_transcribes_audio_with_cached_local_whisper(
    tmp_path, monkeypatch
) -> None:
    created = []

    class FakeWhisper:
        def __init__(self, model, **options):
            created.append((model, options))

        def transcribe(self, path, *, language):
            assert Path(path).read_bytes() == b"audio"
            assert language == "zh"
            return [type("Segment", (), {"text": " 语音指令"})()], type(
                "Info", (), {"language": "zh"}
            )()

    monkeypatch.setattr(faster_whisper, "WhisperModel", FakeWhisper)
    _app, client, _model_id = await _client(tmp_path, AssistantGateway())
    payload = {
        "audio_base64": "data:audio/webm;base64," + base64.b64encode(b"audio").decode(),
        "language": "zh",
        "model_size": "base",
    }
    try:
        first = await client.post("/api/ai-assistant/transcribe", json=payload)
        second = await client.post("/api/ai-assistant/transcribe", json=payload)
    finally:
        await client.aclose()

    assert first.json() == {
        "success": True,
        "text": "语音指令",
        "error": "",
        "language": "zh",
    }
    assert second.json() == first.json()
    assert len(created) == 1
    assert created[0][0] == "Systran/faster-whisper-base"
    assert list((tmp_path / "workspace" / "assistant" / "tmp").iterdir()) == []


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
            if (
                response.status_code == 200
                and response.json()["status"] == "waiting_for_action"
            ):
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
