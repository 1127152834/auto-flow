from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from autoflow.application.workflows.executors import input_triggers
from autoflow.application.workflows.executors.input_triggers import (
    Direction,
    _Gesture,
    normalize_hotkey,
)
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext


def test_hotkey_normalization_matches_frozen_source() -> None:
    assert normalize_hotkey("ctrl+Shift+F1") == "<ctrl>+<shift>+<f1>"
    assert normalize_hotkey("escape+page_down+a") == "<esc>+<pagedown>+a"
    assert normalize_hotkey("unknown") == "<unknown>"


@pytest.mark.asyncio
async def test_hotkey_listener_triggers_and_is_stopped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    class Listener:
        def __init__(self, mapping: dict[str, Any]) -> None:
            seen["mapping"] = mapping

        def start(self) -> None:
            next(iter(seen["mapping"].values()))()

        def stop(self) -> None:
            seen["stopped"] = True

    monkeypatch.setattr(
        input_triggers, "_keyboard", lambda: SimpleNamespace(GlobalHotKeys=Listener)
    )
    executor = build_production_executor_registry().get("hotkey_trigger")
    assert executor is not None
    result = await executor.execute(
        {"hotkey": "ctrl+shift+f1", "timeout": 1}, ExecutionContext()
    )

    assert result.success is True
    assert result.message == "热键已触发: ctrl+shift+f1"
    assert list(seen["mapping"]) == ["<ctrl>+<shift>+<f1>"]
    assert seen["stopped"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("trigger_type", "invoke", "expected"),
    [
        (
            "left_click",
            lambda callbacks, buttons: callbacks["on_click"](
                10, 20, buttons.left, False
            ),
            {"x": 10, "y": 20, "button": "left"},
        ),
        (
            "scroll_down",
            lambda callbacks, _buttons: callbacks["on_scroll"](10, 20, 0, -3),
            {"x": 10, "y": 20, "direction": "down", "delta": 3},
        ),
        (
            "move",
            lambda callbacks, _buttons: (
                callbacks["on_move"](0, 0),
                callbacks["on_move"](30, 40),
            ),
            {"x": 30, "y": 40, "start_x": 0, "start_y": 0, "distance": 50},
        ),
    ],
)
async def test_mouse_event_branches(
    monkeypatch: pytest.MonkeyPatch,
    trigger_type: str,
    invoke: Any,
    expected: dict[str, Any],
) -> None:
    buttons = SimpleNamespace(left="left", right="right", middle="middle")
    seen: dict[str, Any] = {}

    class Listener:
        def __init__(self, **callbacks: Any) -> None:
            seen["callbacks"] = callbacks

        def start(self) -> None:
            invoke(seen["callbacks"], buttons)

        def stop(self) -> None:
            seen["stopped"] = True

    monkeypatch.setattr(
        input_triggers,
        "_mouse",
        lambda: SimpleNamespace(Button=buttons, Listener=Listener),
    )
    executor = build_production_executor_registry().get("mouse_trigger")
    assert executor is not None
    result = await executor.execute(
        {
            "triggerType": trigger_type,
            "moveDistance": 50,
            "timeout": 1,
            "saveToVariable": "mouse",
        },
        ExecutionContext(),
    )

    assert result.success is True
    assert result.data == expected
    assert seen["stopped"] is True


def test_gesture_recognizes_frozen_eight_directions_and_deduplicates() -> None:
    gesture = _Gesture(lambda *_args: None, min_distance=10, timeout=2)
    assert gesture.recognize([(0, 0), (20, 0), (40, 0), (40, 20)]) == [
        Direction.RIGHT,
        Direction.DOWN,
    ]
    assert gesture.direction((0, 0), (20, -20)) is Direction.UP_RIGHT


@pytest.mark.asyncio
async def test_mouse_gesture_branch_matches_pattern_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buttons = SimpleNamespace(left="left", right="right", middle="middle")
    seen: dict[str, Any] = {}

    class Listener:
        def __init__(self, **callbacks: Any) -> None:
            self.callbacks = callbacks

        def start(self) -> None:
            self.callbacks["on_click"](0, 0, buttons.left, True)
            self.callbacks["on_move"](60, 0)
            self.callbacks["on_click"](60, 0, buttons.left, False)

        def stop(self) -> None:
            seen["stopped"] = True

    monkeypatch.setattr(
        input_triggers,
        "_mouse",
        lambda: SimpleNamespace(Button=buttons, Listener=Listener),
    )
    executor = build_production_executor_registry().get("mouse_trigger")
    assert executor is not None
    context = ExecutionContext()
    result = await executor.execute(
        {
            "triggerType": "left_gesture",
            "gesturePattern": "right",
            "minGestureDistance": 50,
            "timeout": 1,
            "saveToVariable": "gesture",
        },
        context,
    )

    assert result.success is True
    assert result.data == {
        "gesture": "left_right",
        "directions": ["right"],
        "pattern": "right",
    }
    assert context.variables["gesture"] == result.data
    assert seen["stopped"] is True
