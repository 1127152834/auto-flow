from collections.abc import Mapping
from typing import Any

import pytest
from autoflow.application.workflows.executors.ai import AIChatExecutor, AIVisionExecutor
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


class FakeElement:
    def __init__(self, tag: str = "div", source: str | None = None) -> None:
        self.first = self
        self.tag = tag
        self.source = source
        self.waited: tuple[str, float | None] | None = None

    async def wait_for(self, *, state="visible", timeout_ms=None) -> None:
        self.waited = (state, timeout_ms)

    async def evaluate(self, _expression: str) -> str:
        return self.tag

    async def get_attribute(self, name: str) -> str | None:
        return self.source if name == "src" else None

    async def screenshot(self) -> bytes:
        return b"ELEMENT"


class FakePage:
    def __init__(self, element: FakeElement | None = None) -> None:
        self.element = element or FakeElement()

    def locator(self, _selector: str) -> FakeElement:
        return self.element

    async def screenshot(self, *, full_page=False) -> bytes:
        assert full_page is False
        return b"PAGE"


class FakeBrowser:
    def __init__(self, page: FakePage) -> None:
        self.page = page

    def current_page(self) -> FakePage:
        return self.page


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


@pytest.mark.asyncio
async def test_ai_vision_uses_managed_model_and_preserves_source_result(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"PNG")
    models = FakeModels()
    context = ExecutionContext(models=models)

    result = await AIVisionExecutor().execute(
        {
            "modelId": "fallback",
            "imageSource": "url",
            "imageUrl": str(image),
            "userPrompt": "识别图片",
            "maxTokens": 321,
            "variableName": "vision",
        },
        context,
    )

    assert result.success is True
    assert context.variables["vision"] == "最终回答"
    model_id, payload = models.calls[0]
    assert model_id == "fallback"
    assert payload["maxTokens"] == 321
    assert payload["messages"] == [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,UE5H"},
                },
                {"type": "text", "text": "识别图片"},
            ],
        }
    ]
    assert result.data == {
        "response": "最终回答",
        "reasoning": None,
        "model": "fallback-key",
        "modelId": "fallback",
        "image_source": "url",
        "usage": {"total_tokens": 8},
    }


def test_ai_vision_is_registered_and_requires_managed_model():
    executor = build_production_executor_registry().get("ai_vision")
    valid, message = executor.validate_config(
        {
            "apiUrl": "https://legacy.invalid/v1",
            "apiKey": "must-not-be-copied",
            "model": "legacy-model",
            "userPrompt": "识别",
        }
    )

    assert valid is False
    assert message == "请选择主应用中的模型"
    assert executor.requires_browser_for({"imageSource": "element"}) is True
    assert executor.requires_browser_for({"imageSource": "screenshot"}) is True
    assert executor.requires_browser_for({"imageSource": "url"}) is False
    assert executor.requires_browser_for({"imageSource": "variable"}) is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config", "variables", "page", "expected_url"),
    [
        (
            {"imageSource": "screenshot"},
            {},
            FakePage(),
            "data:image/png;base64,UEFHRQ==",
        ),
        (
            {"imageSource": "element", "imageSelector": "#image"},
            {},
            FakePage(FakeElement("div")),
            "data:image/png;base64,RUxFTUVOVA==",
        ),
        (
            {"imageSource": "element", "imageSelector": "#image"},
            {},
            FakePage(FakeElement("img", "https://image.example/a.png")),
            "https://image.example/a.png",
        ),
        (
            {"imageSource": "variable", "imageVariable": "image"},
            {"image": "UkFX"},
            None,
            "data:image/png;base64,UkFX",
        ),
    ],
)
async def test_ai_vision_supports_every_non_file_image_source(
    config, variables, page, expected_url
):
    models = FakeModels()
    context = ExecutionContext(
        variables=variables,
        models=models,
        browser=FakeBrowser(page) if page else None,
    )

    result = await AIVisionExecutor().execute(
        {**config, "modelId": "fallback", "userPrompt": "识别", "timeout": 2},
        context,
    )

    assert result.success is True
    content = models.calls[0][1]["messages"][0]["content"]
    assert content[0]["image_url"]["url"] == expected_url
    if config["imageSource"] == "element":
        assert page.element.waited == ("visible", 2000)
