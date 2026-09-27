from __future__ import annotations

import json
import os
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
HARNESS = Path(__file__).with_name("frozen_b6_allure_harness.py")


def source(payload: dict[str, Any]) -> list[dict[str, Any]]:
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


async def target(payload: dict[str, Any]) -> list[dict[str, Any]]:
    context = ExecutionContext(variables=payload.get("variables", {}))
    registry = build_production_executor_registry()
    results = []
    for item in payload["steps"]:
        result = await registry.get(item["moduleType"]).execute(
            item.get("config", {}), context
        )
        data = result.data
        if item["moduleType"] == "allure_init" and data:
            data = {"suite_id": "<uuid>"}
        results.append(
            {
                "success": result.success,
                "message": result.message,
                "data": data,
                "error": result.error,
            }
        )
    return results


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"steps": [{"moduleType": "allure_start_test"}]},
        {
            "variables": {"case": "变量用例"},
            "steps": [
                {"moduleType": "allure_init", "config": {"testSuite": "回归"}},
                {"moduleType": "allure_start_test", "config": {"name": "{case}"}},
                {"moduleType": "allure_add_step", "config": {"stepName": "步骤"}},
                {
                    "moduleType": "allure_stop_test",
                    "config": {"status": "failed", "failMsg": "失败"},
                },
            ],
        },
        {
            "steps": [
                {"moduleType": "allure_init"},
                {"moduleType": "allure_add_step"},
                {"moduleType": "allure_stop_test"},
                {"moduleType": "allure_add_attachment"},
            ]
        },
    ],
)
async def test_allure_sequence_matches_frozen_source(payload: dict[str, Any]) -> None:
    assert await target(payload) == source(payload)
