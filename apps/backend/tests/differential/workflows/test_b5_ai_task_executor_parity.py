from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.models import ModelInvocationResult
from autoflow.domain.workflows.execution import ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_ai_tasks_harness.py")

CASES = (
    ("ai_extract", {"inputText": "姓名张三", "fields": "姓名"}, '{"姓名":"张三"}'),
    ("ai_classify", {"inputText": "我要退款", "categories": "退款,咨询"}, '{"category":"退款"}'),
    ("ai_summarize", {"inputText": "很长的原文", "maxWords": 20}, "简短摘要"),
    ("ai_translate", {"inputText": "你好", "targetLang": "英文"}, "Hello"),
    ("ai_sentiment", {"inputText": "非常满意"}, '{"sentiment":"正面"}'),
    ("ai_normalize", {"inputText": "2026年9月21日", "normalizeType": "date"}, '"2026-09-21"'),
    ("ai_dedup_semantic", {"inputList": '["苹果","Apple","香蕉"]'}, "[0,2]"),
    ("ai_route", {"inputText": "我要退款", "routes": "退款:退钱;咨询:问信息"}, '{"route":"退款"}'),
)


class FixtureModels:
    def __init__(self, content: str) -> None:
        self.content = content

    async def invoke(
        self, _model_id: str, _payload: Mapping[str, Any]
    ) -> ModelInvocationResult:
        return ModelInvocationResult("fixture", self.content, "", {}, "fixture://model")


def _source_result(payload: dict[str, Any]) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(FROZEN_BACKEND)
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout.splitlines()[-1])


async def _target_result(
    module_type: str, config: dict[str, Any], response: str
) -> dict[str, Any]:
    context = ExecutionContext(models=FixtureModels(response))
    result = await build_production_executor_registry().get(module_type).execute(
        {**config, "modelId": "fixture", "_fixtureResponse": response}, context
    )
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


@pytest.mark.parametrize(("module_type", "config", "response"), CASES)
def test_ai_task_output_and_variable_changes_match_frozen_source(
    module_type: str, config: dict[str, Any], response: str
) -> None:
    source = _source_result(
        {
            "type": module_type,
            "config": {
                **config,
                "_fixtureResponse": response,
                "variableName": "out",
            },
        }
    )
    target = asyncio.run(
        _target_result(
            module_type,
            {**config, "variableName": "out"},
            response,
        )
    )

    assert target == source
