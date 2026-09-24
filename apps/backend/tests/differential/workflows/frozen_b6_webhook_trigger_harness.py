# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
from types import ModuleType

from app.executors.base import ExecutionContext
from app.executors.trigger import WebhookTriggerExecutor


async def run(payload):
    trigger = payload.get("trigger")
    trigger_manager = None
    if trigger is not None:
        pynput = ModuleType("pynput")
        pynput.keyboard = ModuleType("pynput.keyboard")
        sys.modules["pynput"] = pynput
        sys.modules["pynput.keyboard"] = pynput.keyboard
        from app.services.trigger_manager import trigger_manager

    context = ExecutionContext(variables=payload.get("variables", {}))
    task = asyncio.create_task(
        WebhookTriggerExecutor().execute(payload.get("config", {}), context)
    )
    if trigger is not None:
        assert trigger_manager is not None
        webhook_id = payload["config"]["webhookId"]
        for _ in range(100):
            if webhook_id in trigger_manager.webhooks:
                break
            await asyncio.sleep(0.001)
        trigger_manager.trigger_webhook(webhook_id, trigger["method"], trigger["data"])
    result = await task
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


print(json.dumps(asyncio.run(run(json.loads(sys.stdin.read()))), ensure_ascii=False))
