from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from autoflow.application.workflows.executors import face_trigger
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext

ROOT = Path(__file__).resolve().parents[5]
HARNESS = Path(__file__).with_name("frozen_b6_face_trigger_harness.py")


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


class _Capture:
    def isOpened(self) -> bool:
        return True

    def read(self) -> tuple[bool, str]:
        return True, "frame"

    def release(self) -> None:
        return None


@pytest.mark.asyncio
async def test_face_trigger_validation_matches_frozen_source() -> None:
    executor = build_production_executor_registry().get("face_trigger")
    assert executor is not None
    context = ExecutionContext()
    result = await executor.execute({}, context)
    assert _view(result, context) == source({"config": {}})


@pytest.mark.asyncio
async def test_face_trigger_match_matches_frozen_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "face.png"
    target.write_bytes(b"face")
    monkeypatch.setattr(face_trigger, "_load_target_face", lambda _path: "target")
    monkeypatch.setattr(face_trigger, "_open_camera", lambda _index: _Capture())
    monkeypatch.setattr(
        face_trigger, "_find_match", lambda *_args: (0.75, (1, 2, 3, 4))
    )
    payload = {
        "config": {
            "targetFaceImage": str(target),
            "tolerance": 0.6,
            "checkInterval": 0,
            "cameraIndex": 0,
            "saveToVariable": "face",
        }
    }
    context = ExecutionContext()
    executor = build_production_executor_registry().get("face_trigger")
    assert executor is not None
    result = await executor.execute(payload["config"], context)

    assert _view(result, context) == source(payload)


def _view(result: Any, context: ExecutionContext) -> dict[str, Any]:
    variables = {key: value for key, value in context.variables.items()}
    for value in variables.values():
        if isinstance(value, dict):
            value.pop("timestamp", None)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": variables,
    }
