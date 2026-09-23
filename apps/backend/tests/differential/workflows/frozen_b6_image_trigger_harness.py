# mypy: ignore-errors
from __future__ import annotations

import asyncio
import ctypes
import json
import sys
from types import SimpleNamespace

from PIL import Image, ImageGrab

ctypes.windll = SimpleNamespace(
    shcore=SimpleNamespace(SetProcessDpiAwareness=lambda *_args: None),
    user32=SimpleNamespace(
        SetProcessDPIAware=lambda: None,
        GetSystemMetrics=lambda _metric: 0,
    ),
)

from app.executors.base import ExecutionContext
from app.executors.trigger import ImageTriggerExecutor


async def run(payload):
    ImageGrab.grab = lambda **_options: Image.open(payload["screenPath"])
    context = ExecutionContext()
    result = await ImageTriggerExecutor().execute(payload.get("config", {}), context)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


print(json.dumps(asyncio.run(run(json.loads(sys.stdin.read()))), ensure_ascii=False))
