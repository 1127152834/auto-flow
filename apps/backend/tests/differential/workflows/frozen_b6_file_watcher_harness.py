# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import ModuleType

pynput = ModuleType("pynput")
pynput.keyboard = ModuleType("pynput.keyboard")
sys.modules["pynput"] = pynput
sys.modules["pynput.keyboard"] = pynput.keyboard

from app.executors.base import ExecutionContext
from app.executors.trigger import FileWatcherTriggerExecutor


async def run(payload):
    context = ExecutionContext()
    task = asyncio.create_task(
        FileWatcherTriggerExecutor().execute(payload.get("config", {}), context)
    )
    create_path = payload.get("createPath")
    if create_path:
        await asyncio.sleep(0.1)
        Path(create_path).write_text("created", encoding="utf-8")
    result = await task
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


print(json.dumps(asyncio.run(run(json.loads(sys.stdin.read()))), ensure_ascii=False))
