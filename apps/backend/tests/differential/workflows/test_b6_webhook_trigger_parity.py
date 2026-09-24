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
HARNESS = Path(__file__).with_name("frozen_b6_webhook_trigger_harness.py")


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


class ImmediateWebhook:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    async def wait_for_webhook(self, **_request: Any) -> dict[str, Any]:
        return self.data


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"config": {}},
        {"config": {"webhookId": "hook", "validateHeaders": "{"}},
        {"config": {"webhookId": "hook", "validateParams": "{"}},
        {"config": {"webhookId": "hook", "responseBody": "{"}},
    ],
)
async def test_webhook_trigger_validation_matches_frozen_source(
    payload: dict[str, Any],
) -> None:
    executor = build_production_executor_registry().get("webhook_trigger")

    assert executor is not None
    result = await executor.execute(payload["config"], ExecutionContext())

    assert {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": {},
    } == source(payload)


@pytest.mark.asyncio
async def test_webhook_trigger_result_matches_frozen_source() -> None:
    data = {
        "method": "POST",
        "query": {"user": "42"},
        "body": {"action": "sync"},
        "headers": {"x-source": "fixture", "user-agent": "ignored"},
        "timestamp": "2026-09-21T00:00:00",
    }
    payload = {
        "config": {
            "webhookId": "hook",
            "method": "POST",
            "saveToVariable": "request",
            "autoSetParams": True,
            "paramPrefix": "hook_",
        },
        "trigger": {"method": "POST", "data": data},
    }
    context = ExecutionContext(webhook_triggers=ImmediateWebhook(data))
    executor = build_production_executor_registry().get("webhook_trigger")

    assert executor is not None
    result = await executor.execute(payload["config"], context)

    assert {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    } == source(payload)
