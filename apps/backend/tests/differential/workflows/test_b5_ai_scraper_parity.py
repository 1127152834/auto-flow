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
FROZEN_HARNESS = Path(__file__).with_name("frozen_ai_scraper_harness.py")

CASES = (
    (
        "ai_smart_scraper",
        {"prompt": "提取列表", "variableName": "out"},
        '{"items":["一","二"]}',
    ),
    (
        "ai_element_selector",
        {"elementDescription": "登录按钮", "variableName": "out"},
        '{"selector":"#login","description":"登录按钮","confidence":96}',
    ),
)


class Models:
    def __init__(self, response: str) -> None:
        self.response = response

    async def invoke(
        self, _model_id: str, _payload: Mapping[str, Any]
    ) -> ModelInvocationResult:
        return ModelInvocationResult("fixture", self.response, "", {}, "fixture://model")


class Page:
    url = "about:blank"

    def __init__(self) -> None:
        self.closed = False

    async def goto(self, url: str, *, wait_until: str, timeout_ms: float) -> None:
        self.url = url

    async def content(self) -> str:
        return "<html><button id='login'>登录</button></html>"

    async def close(self) -> None:
        self.closed = True


class Browser:
    def current_page(self) -> Page:
        return Page()

    async def new_page(self) -> Page:
        return Page()


@pytest.mark.parametrize(("module_type", "partial", "response"), CASES)
def test_ai_scraper_outputs_match_frozen_source(
    module_type: str, partial: dict[str, Any], response: str
) -> None:
    source_config = {
        **partial,
        "url": "https://example.test/page",
        "waitTime": 0,
        "llmProvider": "ollama",
    }
    env = dict(os.environ)
    env["PYTHONPATH"] = str(FROZEN_BACKEND)
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS)],
        input=json.dumps({"type": module_type, "config": source_config}, ensure_ascii=False),
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    source = json.loads(completed.stdout.splitlines()[-1])

    context = ExecutionContext(browser=Browser(), models=Models(response))
    result = asyncio.run(
        build_production_executor_registry().get(module_type).execute(
            {
                **partial,
                "url": "https://example.test/page",
                "waitTime": 0,
                "modelId": "fixture",
            },
            context,
        )
    )
    target = {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }

    assert target == source
