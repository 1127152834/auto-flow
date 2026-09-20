from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.models import ModelError, ModelInvocationResult
from autoflow.domain.workflows.execution import ExecutionContext

TASK_TYPES = (
    "ai_extract",
    "ai_classify",
    "ai_summarize",
    "ai_translate",
    "ai_sentiment",
    "ai_normalize",
    "ai_dedup_semantic",
    "ai_route",
)


class FakeModels:
    def __init__(self, content: str, *, fail: set[str] | None = None) -> None:
        self.content = content
        self.fail = fail or set()
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    async def invoke(
        self, model_id: str, payload: Mapping[str, Any]
    ) -> ModelInvocationResult:
        self.calls.append((model_id, payload))
        if model_id in self.fail:
            raise ModelError("MODEL_PROVIDER_RATE_LIMITED", "模型限流", 429)
        return ModelInvocationResult(
            f"{model_id}-key",
            self.content,
            "",
            {"total_tokens": 12},
            "https://model.fixture/v1/chat/completions",
        )


@pytest.mark.parametrize("module_type", TASK_TYPES)
def test_ai_task_family_is_registered_and_requires_managed_model_id(module_type: str):
    executor = build_production_executor_registry().get(module_type)

    valid, message = executor.validate_config(
        {
            "apiUrl": "https://legacy.invalid/v1",
            "apiKey": "must-not-be-copied",
            "model": "legacy-model",
        }
    )

    assert valid is False
    assert message == "请选择主应用中的模型"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module_type", "config", "content", "variable", "expected", "data_key", "prompt_fragment"),
    [
        ("ai_extract", {"inputText": "姓名张三", "fields": "姓名"}, "```json\n{\"姓名\":\"张三\"}\n```", "out", {"姓名": "张三"}, "result", "要抽取的字段"),
        ("ai_classify", {"inputText": "我要退款", "categories": "退款,咨询"}, '{"category":"退款","confidence":0.9}', "out", "退款", "category", "可选类别"),
        ("ai_summarize", {"inputText": "很长的原文", "maxWords": 20, "style": "一句话"}, "简短摘要", "out", "简短摘要", "summary", "不超过 20 字"),
        ("ai_translate", {"inputText": "你好", "targetLang": "英文"}, "Hello", "out", "Hello", "translation", "翻译成英文"),
        ("ai_sentiment", {"inputText": "非常满意"}, '{"sentiment":"正面","score":1}', "out", {"sentiment": "正面", "score": 1}, "sentiment", "情感分析引擎"),
        ("ai_normalize", {"inputText": "2026年9月21日", "normalizeType": "date"}, '"2026-09-21"', "out", "2026-09-21", "result", "数据规整引擎"),
        ("ai_dedup_semantic", {"inputList": '["苹果","Apple","香蕉"]'}, "[0,2]", "out", ["苹果", "香蕉"], "result", "带编号的列表项"),
        ("ai_route", {"inputText": "我要退款", "routes": "退款:退钱;咨询:问信息"}, '{"route":"退款","confidence":0.8}', "out", "退款", "route", "可选分支"),
    ],
)
async def test_ai_task_family_preserves_source_behavior_with_managed_model(
    module_type: str,
    config: dict[str, Any],
    content: str,
    variable: str,
    expected: Any,
    data_key: str,
    prompt_fragment: str,
):
    models = FakeModels(content)
    context = ExecutionContext(variables={}, models=models)
    executor = build_production_executor_registry().get(module_type)

    result = await executor.execute(
        {
            **config,
            "modelId": "primary",
            "temperature": 0.2,
            "maxTokens": 321,
            "variableName": variable,
        },
        context,
    )

    assert result.success is True
    assert context.variables[variable] == expected
    assert result.data[data_key] == ("正面" if module_type == "ai_sentiment" else expected)
    assert models.calls[0][0] == "primary"
    messages = models.calls[0][1]["messages"]
    assert prompt_fragment in "\n".join(message["content"] for message in messages)
    assert models.calls[0][1]["temperature"] == 0.2
    assert models.calls[0][1]["maxTokens"] == 321


@pytest.mark.asyncio
async def test_ai_task_family_uses_ordered_managed_fallback_ids():
    models = FakeModels('{"姓名":"张三"}', fail={"primary"})
    context = ExecutionContext(models=models)
    executor = build_production_executor_registry().get("ai_extract")

    result = await executor.execute(
        {
            "modelId": "primary",
            "fallbackModelIds": ["fallback"],
            "inputText": "姓名张三",
            "fields": "姓名",
            "variableName": "out",
        },
        context,
    )

    assert result.success is True
    assert [model_id for model_id, _payload in models.calls] == ["primary", "fallback"]
    assert context.variables["out"] == {"姓名": "张三"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module_type", "config", "error"),
    [
        ("ai_extract", {"inputText": "", "fields": "姓名"}, "待抽取文本(inputText)不能为空"),
        ("ai_classify", {"inputText": "文本", "categories": "唯一"}, "请提供至少两个类别"),
        ("ai_summarize", {"inputText": ""}, "待摘要文本(inputText)不能为空"),
        ("ai_translate", {"inputText": ""}, "待翻译文本(inputText)不能为空"),
        ("ai_sentiment", {"inputText": ""}, "待分析文本(inputText)不能为空"),
        ("ai_normalize", {"inputText": "值", "normalizeType": "unknown"}, "未知规整类型"),
        ("ai_dedup_semantic", {"inputList": list(range(301))}, "列表过长(301项)"),
        ("ai_route", {"inputText": "文本", "routes": "唯一"}, "请提供至少两个分支"),
    ],
)
async def test_ai_task_family_preserves_source_validation_errors(
    module_type: str, config: dict[str, Any], error: str
):
    models = FakeModels("unused")
    result = await build_production_executor_registry().get(module_type).execute(
        {**config, "modelId": "primary"}, ExecutionContext(models=models)
    )

    assert result.success is False
    assert error in (result.error or "")
    assert models.calls == []
