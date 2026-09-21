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

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b6_desktop_platform_harness.py")


def _source(payload: dict[str, Any]) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(FROZEN_BACKEND)
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
        env=environment,
    )
    return json.loads(completed.stdout.splitlines()[-1])


class Actions:
    def __init__(self) -> None:
        self.requests: list[tuple[str, Mapping[str, Any], float]] = []

    async def perform(
        self,
        action: str,
        payload: Mapping[str, Any],
        *,
        timeout_seconds: float,
    ) -> DesktopActionResult:
        self.requests.append((action, payload, timeout_seconds))
        return DesktopActionResult(True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module_type", "config"),
    [
        ("set_clipboard", {}),
        ("set_clipboard", {"contentType": "image", "imagePath": ""}),
        ("get_clipboard", {}),
        ("system_notification", {}),
    ],
)
async def test_validation_results_match_frozen_source(
    module_type: str, config: dict[str, Any]
) -> None:
    source = _source({"moduleType": module_type, "config": config})["result"]
    target = await build_production_executor_registry().get(module_type).execute(
        config, ExecutionContext(desktop_actions=Actions())
    )
    assert {
        "success": target.success,
        "message": target.message,
        "data": target.data,
        "error": target.error,
    } == source


@pytest.mark.asyncio
@pytest.mark.parametrize("config", [{}, {"beepCount": -1, "beepInterval": -1}])
async def test_sound_defaults_and_result_match_frozen_source(
    config: dict[str, Any],
) -> None:
    source = _source({"moduleType": "play_sound", "config": config})
    target = await build_production_executor_registry().get("play_sound").execute(
        config, ExecutionContext(desktop_actions=Actions())
    )
    if not config:
        assert source["beeps"] == [[1000, 200]]
    else:
        assert source["beeps"] == []
    assert {
        "success": target.success,
        "message": target.message,
        "data": target.data,
        "error": target.error,
    } == source["result"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module_type", "config", "expected_action"),
    [
        (
            "shutdown_system",
            {"action": "restart", "delay": 9, "force": True},
            (
                "system_control",
                {"operation": "restart", "delay": 9, "force": True},
                60,
            ),
        ),
        ("lock_screen", {}, ("lock_screen", {}, 60)),
    ],
)
async def test_system_control_results_match_frozen_source(
    module_type: str,
    config: dict[str, Any],
    expected_action: tuple[str, Mapping[str, Any], float],
) -> None:
    source = _source({"moduleType": module_type, "config": config})
    actions = Actions()
    target = await build_production_executor_registry().get(module_type).execute(
        config, ExecutionContext(desktop_actions=actions)
    )
    assert {
        "success": target.success,
        "message": target.message,
        "data": target.data,
        "error": target.error,
    } == source["result"]
    assert actions.requests == [expected_action]
    assert source["commands"]
