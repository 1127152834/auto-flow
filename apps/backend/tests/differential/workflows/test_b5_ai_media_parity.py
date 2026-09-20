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
from autoflow.domain.workflows.execution import ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_ai_media_harness.py")

CASES = (
    (
        "ai_generate_image",
        {"provider": "openai", "apiKey": "fixture", "prompt": "猫"},
        {
            "modelKey": "fixture-image",
            "items": [{"url": "https://media.example/image.png"}],
        },
    ),
    (
        "ai_generate_video",
        {
            "provider": "custom",
            "apiUrl": "https://model.example/media",
            "prompt": "海上日出",
        },
        {
            "modelKey": "fixture-video",
            "url": "https://media.example/video.mp4",
        },
    ),
)


class FixtureModels:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self.response = response

    async def invoke_media(
        self,
        _model_id: str,
        _payload: Mapping[str, Any],
        **_options: Any,
    ) -> Mapping[str, Any]:
        return self.response


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
    module_type: str, config: dict[str, Any], response: Mapping[str, Any]
) -> dict[str, Any]:
    context = ExecutionContext(models=FixtureModels(response))
    result = (
        await build_production_executor_registry()
        .get(module_type)
        .execute({**config, "modelId": "fixture"}, context)
    )
    data = dict(result.data or {})
    data.pop("model", None)
    data.pop("modelId", None)
    return {
        "success": result.success,
        "message": result.message,
        "data": data,
        "error": result.error,
        "variables": context.variables,
    }


@pytest.mark.parametrize(("module_type", "config", "response"), CASES)
def test_ai_media_output_and_variable_changes_match_frozen_source(
    module_type: str,
    config: dict[str, Any],
    response: Mapping[str, Any],
) -> None:
    source = _source_result(
        {
            "type": module_type,
            "config": {**config, "variableName": "out"},
        }
    )
    target = asyncio.run(
        _target_result(module_type, {**config, "variableName": "out"}, response)
    )

    assert target == source
