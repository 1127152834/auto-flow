from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from PIL import Image, ImageGrab

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext

ROOT = Path(__file__).resolve().parents[5]
HARNESS = Path(__file__).with_name("frozen_b6_image_trigger_harness.py")


def source(payload: dict[str, Any]) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "reference" / "WebRPA" / "backend")
    completed = subprocess.run(
        [sys.executable, str(HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
        env=environment,
    )
    return json.loads(completed.stdout.splitlines()[-1])


@pytest.mark.asyncio
async def test_image_trigger_validation_matches_frozen_source() -> None:
    executor = build_production_executor_registry().get("image_trigger")
    assert executor is not None
    result = await executor.execute({}, ExecutionContext())
    assert _view(result, ExecutionContext()) == source(
        {"config": {}, "screenPath": "unused"}
    )


@pytest.mark.asyncio
async def test_image_trigger_match_matches_frozen_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    random = np.random.default_rng(42)
    template = random.integers(0, 256, size=(7, 9, 3), dtype=np.uint8)
    screen = np.zeros((30, 40, 3), dtype=np.uint8)
    screen[8:15, 13:22] = template
    template_path = tmp_path / "template.png"
    screen_path = tmp_path / "screen.png"
    assert cv2.imwrite(str(template_path), template)
    assert cv2.imwrite(str(screen_path), screen)
    monkeypatch.setattr(ImageGrab, "grab", lambda **_options: Image.open(screen_path))
    payload = {
        "config": {
            "imagePath": str(template_path),
            "confidence": 0.9,
            "timeout": 1,
            "saveToVariable": "match",
        },
        "screenPath": str(screen_path),
    }
    context = ExecutionContext()
    executor = build_production_executor_registry().get("image_trigger")
    assert executor is not None
    result = await executor.execute(payload["config"], context)

    assert _view(result, context) == source(payload)


def _view(result: Any, context: ExecutionContext) -> dict[str, Any]:
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }
