from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from autoflow.application.workflows.executors import input_triggers
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext

ROOT = Path(__file__).resolve().parents[5]
HARNESS = Path(__file__).with_name("frozen_b6_input_trigger_harness.py")


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
async def test_hotkey_trigger_matches_frozen_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Listener:
        def __init__(self, mapping: dict[str, Any]) -> None:
            self.mapping = mapping

        def start(self) -> None:
            next(iter(self.mapping.values()))()

        def stop(self) -> None:
            return None

    monkeypatch.setattr(
        input_triggers, "_keyboard", lambda: SimpleNamespace(GlobalHotKeys=Listener)
    )
    payload = {"nodeType": "hotkey_trigger", "config": {"hotkey": "ctrl+f1"}}
    context = ExecutionContext()
    executor = build_production_executor_registry().get("hotkey_trigger")
    assert executor is not None
    result = await executor.execute(payload["config"], context)
    assert _view(result, context) == source(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize("event", ["left_click", "scroll_down", "move"])
async def test_mouse_trigger_matches_frozen_source(
    monkeypatch: pytest.MonkeyPatch, event: str
) -> None:
    buttons = SimpleNamespace(left="left", right="right", middle="middle")

    class Listener:
        def __init__(self, **callbacks: Any) -> None:
            self.callbacks = callbacks

        def start(self) -> None:
            if event == "left_click":
                self.callbacks["on_click"](10, 20, buttons.left, False)
            elif event == "scroll_down":
                self.callbacks["on_scroll"](10, 20, 0, -3)
            else:
                self.callbacks["on_move"](0, 0)
                self.callbacks["on_move"](30, 40)

        def stop(self) -> None:
            return None

    monkeypatch.setattr(
        input_triggers,
        "_mouse",
        lambda: SimpleNamespace(Button=buttons, Listener=Listener),
    )
    trigger_type = event
    payload = {
        "nodeType": "mouse_trigger",
        "event": event,
        "config": {
            "triggerType": trigger_type,
            "moveDistance": 50,
            "saveToVariable": "mouse",
        },
    }
    context = ExecutionContext()
    executor = build_production_executor_registry().get("mouse_trigger")
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
