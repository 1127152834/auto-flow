"""Global input triggers migrated from WebRPA@5ccb900e.

Sources: backend/app/executors/trigger.py and
backend/app/services/{trigger_manager,mouse_gesture_service}.py.
License: LICENSE.WebRPA.
"""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_float, to_int


def _keyboard() -> Any:
    from pynput import keyboard  # type: ignore[import-untyped]

    return keyboard


def _mouse() -> Any:
    from pynput import mouse  # type: ignore[import-untyped]

    return mouse


def normalize_hotkey(hotkey: str) -> str:
    special = {
        "ctrl",
        "alt",
        "shift",
        "cmd",
        "win",
        "esc",
        "escape",
        "tab",
        "capslock",
        "caps_lock",
        "enter",
        "return",
        "backspace",
        "delete",
        "del",
        "insert",
        "home",
        "end",
        "pageup",
        "page_up",
        "pagedown",
        "page_down",
        "up",
        "down",
        "left",
        "right",
        "space",
        "numlock",
        "num_lock",
        "scroll_lock",
        "print_screen",
        "pause",
    }
    aliases = {
        "escape": "esc",
        "return": "enter",
        "del": "delete",
        "caps_lock": "capslock",
        "page_up": "pageup",
        "page_down": "pagedown",
        "num_lock": "numlock",
    }
    result = []
    for raw in hotkey.lower().split("+"):
        key = raw.strip()
        if key.startswith("f") and len(key) <= 3 and key[1:].isdigit():
            result.append(f"<{key}>")
        elif key in special:
            result.append(f"<{aliases.get(key, key)}>")
        elif len(key) == 1:
            result.append(key)
        else:
            result.append(f"<{key}>")
    return "+".join(result)


class HotkeyTriggerExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "hotkey_trigger"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        hotkey = context.resolve_value(config.get("hotkey", ""))
        timeout = to_int(config.get("timeout", 0), 0, context)
        if not hotkey:
            return ModuleResult(success=False, error="热键不能为空")
        event = asyncio.Event()
        loop = asyncio.get_running_loop()
        listener = None
        try:
            listener = _keyboard().GlobalHotKeys(
                {
                    normalize_hotkey(str(hotkey)): lambda: loop.call_soon_threadsafe(
                        event.set
                    )
                }
            )
            listener.start()
            if not context.node_uses_sensitive_values:
                await _progress(context, f"⌨️ 热键监听已启动: {hotkey}")
            await _progress(context, "💡 请按下热键以继续执行工作流")
            try:
                await asyncio.wait_for(
                    event.wait(), timeout
                ) if timeout > 0 else await event.wait()
            except TimeoutError:
                return ModuleResult(success=False, error=f"热键等待超时（{timeout}秒）")
            return ModuleResult(success=True, message=f"热键已触发: {hotkey}")
        except ImportError:
            return ModuleResult(
                success=False, error="热键触发器初始化失败，请检查系统配置"
            )
        except Exception as error:  # noqa: BLE001 - OS listener errors become node errors.
            return ModuleResult(success=False, error=f"热键触发器失败: {error}")
        finally:
            if listener is not None:
                try:
                    listener.stop()
                except Exception:  # noqa: BLE001,S110 - cleanup is best effort.
                    pass


class Direction(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    UP_LEFT = "up_left"
    UP_RIGHT = "up_right"
    DOWN_LEFT = "down_left"
    DOWN_RIGHT = "down_right"


@dataclass(slots=True)
class _Gesture:
    callback: Callable[[str, list[Direction]], None]
    min_distance: int
    timeout: float
    points: list[tuple[float, float]] = field(default_factory=list)
    started_at: float = 0
    button: Any = None

    def click(self, x: float, y: float, button: Any, pressed: bool) -> None:
        if pressed:
            self.button = button
            self.points = [(x, y)]
            self.started_at = time.monotonic()
            return
        if button != self.button:
            return
        self.points.append((x, y))
        directions = self.recognize(self.points)
        if directions:
            self.callback(self.name(button, directions), directions)
        self.button = None
        self.points = []

    def move(self, x: float, y: float) -> None:
        if self.button is None:
            return
        if time.monotonic() - self.started_at > self.timeout:
            self.button = None
            self.points = []
        elif len(self.points) < 5000:
            self.points.append((x, y))

    def recognize(self, points: list[tuple[float, float]]) -> list[Direction]:
        simplified = [points[0]]
        for point in points[1:]:
            if math.dist(point, simplified[-1]) >= self.min_distance:
                simplified.append(point)
        result: list[Direction] = []
        for start, end in zip(simplified, simplified[1:], strict=False):
            direction = self.direction(start, end)
            if direction is not None and (not result or direction != result[-1]):
                result.append(direction)
        return result

    def direction(
        self, start: tuple[float, float], end: tuple[float, float]
    ) -> Direction | None:
        dx, dy = end[0] - start[0], end[1] - start[1]
        if math.hypot(dx, dy) < self.min_distance:
            return None
        angle = math.degrees(math.atan2(dy, dx))
        if -22.5 <= angle < 22.5:
            return Direction.RIGHT
        if 22.5 <= angle < 67.5:
            return Direction.DOWN_RIGHT
        if 67.5 <= angle < 112.5:
            return Direction.DOWN
        if 112.5 <= angle < 157.5:
            return Direction.DOWN_LEFT
        if angle >= 157.5 or angle < -157.5:
            return Direction.LEFT
        if -157.5 <= angle < -112.5:
            return Direction.UP_LEFT
        if -112.5 <= angle < -67.5:
            return Direction.UP
        return Direction.UP_RIGHT

    @staticmethod
    def name(button: Any, directions: list[Direction]) -> str:
        mouse = _mouse()
        prefix = ""
        if button == mouse.Button.left:
            prefix = "left_"
        elif button == mouse.Button.right:
            prefix = "right_"
        elif button == mouse.Button.middle:
            prefix = "middle_"
        return prefix + "_".join(direction.value for direction in directions)


class MouseTriggerExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "mouse_trigger"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        trigger_type = str(
            context.resolve_value(config.get("triggerType", "left_click"))
        )
        gesture_pattern = str(context.resolve_value(config.get("gesturePattern", "")))
        move_distance = to_int(config.get("moveDistance", 100), 100, context)
        min_gesture_distance = to_int(config.get("minGestureDistance", 50), 50, context)
        gesture_timeout = to_float(config.get("gestureTimeout", 2), 2, context)
        timeout = to_int(config.get("timeout", 0), 0, context)
        variable_name = str(config.get("saveToVariable", "mouse_event"))
        if trigger_type in {
            "left_gesture",
            "right_gesture",
            "middle_gesture",
            "custom_gesture",
        }:
            return await self._gesture(
                trigger_type,
                gesture_pattern,
                min_gesture_distance,
                gesture_timeout,
                timeout,
                variable_name,
                context,
            )
        return await self._event(
            trigger_type, move_distance, timeout, variable_name, context
        )

    async def _event(
        self,
        trigger_type: str,
        move_distance: int,
        timeout: int,
        variable_name: str,
        context: ExecutionContext,
    ) -> ModuleResult:
        event = asyncio.Event()
        loop = asyncio.get_running_loop()
        mouse_data: dict[str, Any] = {}
        start: tuple[float, float] | None = None
        mouse: Any = None
        listener = None

        def complete(data: dict[str, Any]) -> None:
            nonlocal mouse_data
            mouse_data = data
            loop.call_soon_threadsafe(event.set)

        def click(x: float, y: float, button: Any, pressed: bool) -> None:
            if pressed:
                return
            buttons = {
                "left_click": (mouse.Button.left, "left"),
                "right_click": (mouse.Button.right, "right"),
                "middle_click": (mouse.Button.middle, "middle"),
            }
            expected = buttons.get(trigger_type)
            if expected and button == expected[0]:
                complete({"x": x, "y": y, "button": expected[1]})

        def scroll(x: float, y: float, _dx: float, dy: float) -> None:
            if trigger_type == "scroll_up" and dy > 0:
                complete({"x": x, "y": y, "direction": "up", "delta": dy})
            elif trigger_type == "scroll_down" and dy < 0:
                complete({"x": x, "y": y, "direction": "down", "delta": abs(dy)})

        def move(x: float, y: float) -> None:
            nonlocal start
            if trigger_type != "move":
                return
            if start is None:
                start = (x, y)
            elif math.dist(start, (x, y)) >= move_distance:
                complete(
                    {
                        "x": x,
                        "y": y,
                        "start_x": start[0],
                        "start_y": start[1],
                        "distance": int(math.dist(start, (x, y))),
                    }
                )

        labels = {
            "left_click": "左键点击",
            "right_click": "右键点击",
            "middle_click": "中键点击",
            "scroll_up": "向上滚动",
            "scroll_down": "向下滚动",
            "move": f"移动超过{move_distance}像素",
        }
        try:
            mouse = _mouse()
            listener = mouse.Listener(on_click=click, on_scroll=scroll, on_move=move)
            listener.start()
            _log(context, "🖱️ 鼠标触发器已启动")
            _log(context, f"📌 触发条件: {labels.get(trigger_type, trigger_type)}")
            try:
                await asyncio.wait_for(
                    event.wait(), timeout
                ) if timeout > 0 else await event.wait()
            except TimeoutError:
                return ModuleResult(
                    success=False, error=f"鼠标触发器超时（{timeout}秒）"
                )
            if variable_name and mouse_data:
                context.set_variable(variable_name, mouse_data)
            return ModuleResult(
                success=True,
                message=f"鼠标触发器已触发: {labels.get(trigger_type, trigger_type)}",
                data=mouse_data,
            )
        except ImportError:
            return ModuleResult(
                success=False, error="鼠标触发器初始化失败，请检查系统配置"
            )
        except Exception as error:  # noqa: BLE001 - OS listener errors become node errors.
            return ModuleResult(success=False, error=f"鼠标触发器失败: {error}")
        finally:
            if listener is not None:
                try:
                    listener.stop()
                except Exception:  # noqa: BLE001,S110 - cleanup is best effort.
                    pass

    async def _gesture(
        self,
        trigger_type: str,
        pattern: str,
        min_distance: int,
        gesture_timeout: float,
        timeout: int,
        variable_name: str,
        context: ExecutionContext,
    ) -> ModuleResult:
        event = asyncio.Event()
        loop = asyncio.get_running_loop()
        gesture_data: dict[str, Any] = {}
        expected = [
            Direction(value)
            for value in pattern.split("_")
            if value in {"up", "down", "left", "right"}
        ]

        def complete(name: str, directions: list[Direction]) -> None:
            nonlocal gesture_data
            prefix = trigger_type.removesuffix("gesture")
            if trigger_type != "custom_gesture" and not name.startswith(prefix):
                return
            if expected and directions != expected:
                return
            gesture_data = {
                "gesture": name,
                "directions": [direction.value for direction in directions],
                "pattern": pattern,
            }
            loop.call_soon_threadsafe(event.set)

        listener = None
        try:
            mouse = _mouse()
            recognizer = _Gesture(complete, min_distance, gesture_timeout)
            listener = mouse.Listener(
                on_click=recognizer.click, on_move=recognizer.move
            )
            listener.start()
            _log(context, "🖱️ 鼠标手势触发器已启动")
            _log(context, f"📌 触发条件: {trigger_type}: {pattern or '任意'}")
            try:
                await asyncio.wait_for(
                    event.wait(), timeout
                ) if timeout > 0 else await event.wait()
            except TimeoutError:
                return ModuleResult(
                    success=False, error=f"鼠标手势触发器超时（{timeout}秒）"
                )
            if variable_name and gesture_data:
                context.set_variable(variable_name, gesture_data)
            return ModuleResult(
                success=True,
                message=f"鼠标手势触发器已触发: {gesture_data.get('gesture', '')}",
                data=gesture_data,
            )
        except ImportError:
            return ModuleResult(
                success=False, error="鼠标触发器初始化失败，请检查系统配置"
            )
        except Exception as error:  # noqa: BLE001 - OS listener errors become node errors.
            return ModuleResult(success=False, error=f"鼠标触发器失败: {error}")
        finally:
            if listener is not None:
                try:
                    listener.stop()
                except Exception:  # noqa: BLE001,S110 - cleanup is best effort.
                    pass


def _log(context: ExecutionContext, message: str) -> None:
    context.log_records.append(
        {
            "timestamp": context.clock.now().isoformat(),
            "level": "info",
            "message": message,
            "duration": 0,
            "nodeId": context.current_node_id or "",
        }
    )


async def _progress(context: ExecutionContext, message: str) -> None:
    _log(context, message)
    await context.send_progress(message)


INPUT_TRIGGER_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    HotkeyTriggerExecutor,
    MouseTriggerExecutor,
)
