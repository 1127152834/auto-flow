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
HARNESS = Path(__file__).with_name("frozen_b6_email_trigger_harness.py")


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
async def test_email_trigger_validation_matches_frozen_source() -> None:
    executor = build_production_executor_registry().get("email_trigger")
    assert executor is not None
    result = await executor.execute({}, ExecutionContext())

    assert {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": {},
    } == source({"config": {}})


@pytest.mark.asyncio
async def test_email_trigger_success_matches_frozen_source() -> None:
    email_data = {
        "from": "sender@example.com",
        "subject": "订单已完成",
        "date": "Sun, 21 Sep 2026 10:00:00 +0800",
        "body": "正文",
        "timestamp": "2026-09-21T10:00:00",
    }
    payload = {
        "config": {
            "emailServer": "imap.example.com",
            "emailPort": 993,
            "emailAccount": "user@example.com",
            "emailPassword": "secret",
            "fromFilter": "sender@",
            "subjectFilter": "订单",
            "checkInterval": 0,
            "timeout": 1,
            "saveToVariable": "mail",
        },
        "email": email_data,
    }

    class Gateway:
        async def call(self, integration: str, _request: Any) -> list[dict[str, str]]:
            assert integration == "imap_unseen"
            return [email_data]

    context = ExecutionContext(external_integrations=Gateway())
    executor = build_production_executor_registry().get("email_trigger")
    assert executor is not None
    result = await executor.execute(payload["config"], context)

    assert {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    } == source(payload)
