from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from autoflow.application.workflows.executors.ai import AIVisionExecutor
from autoflow.domain.models import ModelInvocationResult
from autoflow.domain.workflows.execution import ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_ai_vision_harness.py")


class FixtureModels:
    async def invoke(
        self, _model_id: str, _payload: Mapping[str, Any]
    ) -> ModelInvocationResult:
        return ModelInvocationResult(
            "fixture", "识别结果", "", {"total_tokens": 4}, "fixture://model"
        )


def test_ai_vision_url_output_and_variable_match_frozen_source() -> None:
    source_config = {
        "apiUrl": "https://model.invalid/v1",
        "apiKey": "source-only",
        "model": "vision",
        "imageSource": "url",
        "imageUrl": "https://image.example/sample.png",
        "userPrompt": "识别",
        "variableName": "vision",
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

    context = ExecutionContext(models=FixtureModels())
    result = asyncio.run(
        AIVisionExecutor().execute(
            {
                "modelId": "fixture",
                "imageSource": "url",
                "imageUrl": source_config["imageUrl"],
                "userPrompt": "识别",
                "variableName": "vision",
            },
            context,
        )
    )
    target = {
        "success": result.success,
        "message": result.message,
        "response": result.data.get("response"),
        "image_source": result.data.get("image_source"),
        "error": result.error,
        "variables": context.variables,
    }

    assert target == source
