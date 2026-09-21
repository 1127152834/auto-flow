from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from autoflow.application.workflows.executors import sound_trigger
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext

ROOT = Path(__file__).resolve().parents[5]
HARNESS = Path(__file__).with_name("frozen_b6_sound_trigger_harness.py")


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


class _Meter:
    def GetPeakValue(self) -> float:  # noqa: N802 - COM API compatibility.
        return 0.67


@pytest.mark.asyncio
async def test_sound_trigger_result_matches_frozen_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sound_trigger, "_audio_meter", lambda: _Meter())
    payload = {
        "config": {
            "volumeThreshold": 50,
            "checkInterval": 0,
            "saveToVariable": "volume",
        }
    }
    context = ExecutionContext()
    executor = build_production_executor_registry().get("sound_trigger")
    assert executor is not None
    result = await executor.execute(payload["config"], context)

    assert {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    } == source(payload)
