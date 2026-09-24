# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
from types import ModuleType

from app.executors.base import ExecutionContext
from app.executors.trigger import EmailTriggerExecutor


async def run(payload):
    trigger_module = ModuleType("app.services.trigger_manager")

    class TriggerManager:
        def register_email_monitor(self, *_args):
            asyncio.get_running_loop().call_soon(_args[-1], payload.get("email", {}))
            return "monitor"

        def unregister_email_monitor(self, _monitor_id):
            return None

    trigger_module.trigger_manager = TriggerManager()
    sys.modules["app.services.trigger_manager"] = trigger_module
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await EmailTriggerExecutor().execute(payload.get("config", {}), context)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


print(json.dumps(asyncio.run(run(json.loads(sys.stdin.read()))), ensure_ascii=False))
