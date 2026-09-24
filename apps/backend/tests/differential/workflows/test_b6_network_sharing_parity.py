from __future__ import annotations

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
from autoflow.domain.workflows.execution import DesktopActionResult, ExecutionContext

ROOT = Path(__file__).resolve().parents[5]
HARNESS = Path(__file__).with_name("frozen_b6_network_sharing_harness.py")


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


class Actions:
    async def perform(
        self,
        action: str,
        payload: Mapping[str, Any],
        *,
        timeout_seconds: float,
    ) -> DesktopActionResult:
        del action, timeout_seconds
        port = int(payload.get("port", 0))
        return DesktopActionResult(
            True,
            {
                "success": True,
                "url": f"http://192.0.2.1:{port}",
                "ip": "192.0.2.1",
                "port": port,
            },
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module_type", "config"),
    [
        ("stop_share", {"port": 8123}),
        ("start_screen_share", {"port": 9001, "fps": 99, "quality": 1, "scale": 2}),
        ("stop_screen_share", {"port": 9001}),
    ],
)
async def test_network_share_results_match_frozen_source(
    module_type: str, config: dict[str, Any]
) -> None:
    context = ExecutionContext(desktop_actions=Actions())
    executor = build_production_executor_registry().get(module_type)
    assert executor is not None
    result = await executor.execute(config, context)
    target = {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }
    assert target == source({"moduleType": module_type, "config": config})


@pytest.mark.asyncio
@pytest.mark.parametrize("module_type", ["share_file", "share_folder"])
async def test_file_share_results_match_frozen_source(
    module_type: str, tmp_path: Path
) -> None:
    path = tmp_path / ("shared.txt" if module_type == "share_file" else "shared")
    path.write_text("abc", encoding="utf-8") if module_type == "share_file" else path.mkdir()
    key = "filePath" if module_type == "share_file" else "folderPath"
    config = {key: str(path), "port": 8123, "allowWrite": False}
    context = ExecutionContext(desktop_actions=Actions())
    executor = build_production_executor_registry().get(module_type)
    assert executor is not None
    result = await executor.execute(config, context)
    target = {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }
    assert target == source({"moduleType": module_type, "config": config})
