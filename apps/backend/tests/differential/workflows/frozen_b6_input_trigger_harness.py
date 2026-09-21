# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
from types import ModuleType, SimpleNamespace

pynput = ModuleType("pynput")
mouse_module = ModuleType("pynput.mouse")
buttons = SimpleNamespace(left="left", right="right", middle="middle")
mouse_module.Button = buttons
pynput.mouse = mouse_module
sys.modules["pynput"] = pynput
sys.modules["pynput.mouse"] = mouse_module

from app.executors.base import ExecutionContext  # noqa: E402
from app.executors.trigger import (  # noqa: E402
    HotkeyTriggerExecutor,
    MouseTriggerExecutor,
)


async def run(payload):
    node_type = payload["nodeType"]
    if node_type == "hotkey_trigger":
        module = ModuleType("app.services.trigger_manager")

        class Manager:
            def register_hotkey(self, _hotkey, callback):
                asyncio.get_running_loop().call_soon(callback)
                return "trigger"

            def unregister_hotkey(self, _trigger_id):
                return None

        module.trigger_manager = Manager()
        sys.modules["app.services.trigger_manager"] = module
        executor = HotkeyTriggerExecutor()
    else:
        event = payload.get("event", "left_click")

        class Listener:
            def __init__(self, **callbacks):
                self.callbacks = callbacks

            def start(self):
                if event == "left_click":
                    self.callbacks["on_click"](10, 20, buttons.left, False)
                elif event == "scroll_down":
                    self.callbacks["on_scroll"](10, 20, 0, -3)
                elif event == "move":
                    self.callbacks["on_move"](0, 0)
                    self.callbacks["on_move"](30, 40)

            def stop(self):
                return None

        mouse_module.Listener = Listener
        executor = MouseTriggerExecutor()
    context = ExecutionContext()
    result = await executor.execute(payload.get("config", {}), context)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


print(json.dumps(asyncio.run(run(json.loads(sys.stdin.read()))), ensure_ascii=False))
