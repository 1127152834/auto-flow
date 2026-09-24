from __future__ import annotations

import asyncio
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
HARNESS = Path(__file__).with_name("frozen_b6_file_watcher_harness.py")


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
@pytest.mark.parametrize("config", [{}, {"watchPath": "/path/does/not/exist"}])
async def test_file_watcher_validation_matches_frozen_source(
    config: dict[str, Any],
) -> None:
    executor = build_production_executor_registry().get("file_watcher_trigger")

    assert executor is not None
    result = await executor.execute(config, ExecutionContext())

    assert {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": {},
    } == source({"config": config})


@pytest.mark.asyncio
async def test_file_watcher_created_event_matches_frozen_source(tmp_path: Path) -> None:
    source_directory = tmp_path / "source"
    target_directory = tmp_path / "target"
    source_directory.mkdir()
    target_directory.mkdir()
    source_file = source_directory / "event.txt"
    target_file = target_directory / "event.txt"
    source_result = source(
        {
            "config": {
                "watchPath": str(source_directory),
                "watchType": "created",
                "filePattern": "*.txt",
                "timeout": 3,
                "saveToVariable": "event",
            },
            "createPath": str(source_file),
        }
    )
    executor = build_production_executor_registry().get("file_watcher_trigger")
    assert executor is not None
    context = ExecutionContext()
    task = asyncio.create_task(
        executor.execute(
            {
                "watchPath": str(target_directory),
                "watchType": "created",
                "filePattern": "*.txt",
                "timeout": 3,
                "saveToVariable": "event",
            },
            context,
        )
    )
    await asyncio.sleep(0.1)
    target_file.write_text("created", encoding="utf-8")
    result = await task
    target_result = {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }

    assert _normalized(target_result, target_directory) == _normalized(
        source_result, source_directory
    )


def _normalized(result: dict[str, Any], directory: Path) -> dict[str, Any]:
    encoded = json.dumps(result, ensure_ascii=False).replace(str(directory), "<watch>")
    normalized = json.loads(encoded)
    if isinstance(normalized.get("data"), dict):
        normalized["data"]["timestamp"] = "<timestamp>"
    event = normalized.get("variables", {}).get("event")
    if isinstance(event, dict):
        event["timestamp"] = "<timestamp>"
    return normalized
