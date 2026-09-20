from collections.abc import Mapping
from typing import Any

import pytest
from autoflow.application.workflows.executors.ai import AIChatExecutor
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.models import ModelError, ModelInvocationResult
from autoflow.domain.workflows.execution import ExecutionContext


class FakeModels:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    async def invoke(
        self, model_id: str, payload: Mapping[str, Any]
    ) -> ModelInvocationResult:
        self.calls.append((model_id, payload))
        if model_id == "primary":
            raise ModelError("MODEL_PROVIDER_RATE_LIMITED", "模型限流", 429)
        return ModelInvocationResult(
            "fallback-key",
            "最终回答",
            "",
            {"total_tokens": 8},
            "https://model.example/v1/chat/completions",
        )


@pytest.mark.asyncio
async def test_ai_chat_uses_managed_model_ids_and_fallback_without_node_secret():
    models = FakeModels()
    context = ExecutionContext(
        variables={"question": "中文问题"},
        models=models,
    )

    result = await AIChatExecutor().execute(
        {
            "modelId": "primary",
            "fallbackModels": [{"modelId": "fallback", "temperature": 0.2}],
            "systemPrompt": "系统规则",
            "userPrompt": "${question}",
            "temperature": 0.7,
            "maxTokens": 200,
            "variableName": "answer",
        },
        context,
    )

    assert result.success is True
    assert context.variables["answer"] == "最终回答"
    assert [model_id for model_id, _payload in models.calls] == [
        "primary",
        "fallback",
    ]
    assert models.calls[0][1]["messages"] == [
        {"role": "system", "content": "系统规则"},
        {"role": "user", "content": "中文问题"},
    ]
    assert models.calls[1][1]["temperature"] == 0.2
    assert result.data == {
        "response": "最终回答",
        "reasoning": None,
        "model": "fallback-key",
        "modelId": "fallback",
        "usage": {"total_tokens": 8},
    }


def test_ai_chat_is_registered_and_rejects_legacy_embedded_connection():
    executor = build_production_executor_registry().get("ai_chat")
    valid, message = executor.validate_config(
        {
            "apiUrl": "https://legacy.invalid/v1",
            "apiKey": "must-not-be-copied",
            "model": "legacy-model",
            "userPrompt": "问题",
        }
    )
    assert valid is False
    assert message == "请选择主应用中的模型"
