from __future__ import annotations

import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_ai import AssistantChatRequest, AssistantMessage


def test_assistant_chat_uses_main_model_id_and_rejects_renderer_secrets() -> None:
    parsed = AssistantChatRequest.model_validate(
        {
            "sessionId": "session-1",
            "message": "添加节点",
            "config": {
                "modelId": "model-main",
                "temperature": 0.2,
                "maxTokens": 2048,
                "systemPrompt": "只操作当前画布",
                "enableTools": True,
                "autoApprove": False,
            },
            "workflowContext": {"revision": 3},
        }
    )

    assert parsed.config.model_id == "model-main"
    assert parsed.workflow_context == {"revision": 3}
    with pytest.raises(ValidationError):
        AssistantChatRequest.model_validate(
            {
                "message": "不安全",
                "config": {
                    "modelId": "model-main",
                    "apiUrl": "https://shadow-provider.test",
                    "apiKey": "must-not-cross-renderer",
                },
            }
        )


@pytest.mark.parametrize("field,value", [("temperature", float("nan")), ("maxTokens", 0)])
def test_assistant_chat_rejects_invalid_model_controls(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        AssistantChatRequest.model_validate(
            {"message": "测试", "config": {"modelId": "model-main", field: value}}
        )


def test_assistant_message_keeps_frozen_webrpa_tool_field_names() -> None:
    message = AssistantMessage.model_validate(
        {
            "id": "message-1",
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "tool-1", "status": "running"}],
            "reasoning_content": "分析",
            "attachmentNames": ["需求.txt"],
        }
    )

    assert message.model_dump(by_alias=True, exclude_none=True) == {
        "id": "message-1",
        "role": "assistant",
        "content": "",
        "tool_calls": [{"id": "tool-1", "status": "running"}],
        "attachmentNames": ["需求.txt"],
        "reasoning_content": "分析",
    }
