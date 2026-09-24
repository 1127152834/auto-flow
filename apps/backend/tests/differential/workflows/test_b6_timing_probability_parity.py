from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext

ROOT = Path(__file__).resolve().parents[5]
HARNESS = Path(__file__).with_name("frozen_b6_timing_probability_harness.py")


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
@pytest.mark.parametrize(
    "payload",
    [
        {"moduleType": "scheduled_task", "config": {}},
        {"moduleType": "scheduled_task", "config": {"scheduleType": "delay"}},
        {"moduleType": "scheduled_task", "config": {"scheduleType": "other"}},
        {
            "moduleType": "scheduled_task",
            "config": {
                "scheduleType": "datetime",
                "targetDate": "2000-01-01",
                "targetTime": "00:00",
            },
        },
        {"moduleType": "probability_trigger", "config": {}, "seed": 7},
        {
            "moduleType": "probability_trigger",
            "config": {"probability": 0},
            "seed": 7,
        },
        {
            "moduleType": "probability_trigger",
            "config": {"probability": 100},
            "seed": 7,
        },
        {
            "moduleType": "probability_trigger",
            "config": {"probability": 101},
            "seed": 7,
        },
        {
            "moduleType": "probability_trigger",
            "config": {"probability": "bad"},
            "seed": 7,
        },
    ],
)
async def test_timing_and_probability_match_frozen_source(
    payload: dict[str, Any],
) -> None:
    random.seed(payload.get("seed", 1))
    result = (
        await build_production_executor_registry()
        .get(payload["moduleType"])
        .execute(payload.get("config", {}), ExecutionContext())
    )
    assert {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "branch": result.branch,
    } == source(payload)
