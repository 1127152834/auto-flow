from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from autoflow.application.workflows.executors.ai_vision_act import AIVisionActExecutor
from autoflow.domain.models import ModelInvocationResult
from autoflow.domain.workflows.execution import ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_ai_vision_act_harness.py")


class Models:
    async def invoke(
        self, _model_id: str, _payload: Mapping[str, Any]
    ) -> ModelInvocationResult:
        return ModelInvocationResult(
            "vision", '{"found":true,"x":500,"y":250}', "", {}, "fixture://model"
        )


class Mouse:
    async def move(self, _x: float, _y: float, **_options: Any) -> None:
        return

    async def click(
        self, _x: float, _y: float, *, button: str, click_count: int
    ) -> None:
        return


class Page:
    def __init__(self) -> None:
        self.viewport_size = {"width": 1200, "height": 800}
        self.mouse = Mouse()

    async def screenshot(self, *, full_page: bool = False) -> bytes:
        return b"PAGE"


class Browser:
    def current_page(self) -> Page:
        return Page()


def test_ai_vision_act_coordinate_algorithm_matches_frozen_source() -> None:
    source_config = {
        "apiUrl": "https://model.invalid/v1",
        "apiKey": "source-only",
        "model": "vision",
        "instruction": "登录按钮",
        "action": "locate",
        "variableName": "point",
    }
    env = dict(os.environ)
    env["PYTHONPATH"] = str(FROZEN_BACKEND)
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS)],
        input=json.dumps({"config": source_config}, ensure_ascii=False),
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    source = json.loads(completed.stdout.splitlines()[-1])

    context = ExecutionContext(browser=Browser(), models=Models())
    result = asyncio.run(
        AIVisionActExecutor().execute(
            {
                "modelId": "fixture",
                "instruction": "登录按钮",
                "action": "locate",
                "variableName": "point",
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
