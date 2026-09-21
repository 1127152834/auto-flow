# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
from types import SimpleNamespace

beeps: list[tuple[int, int]] = []
sys.modules["winsound"] = SimpleNamespace(
    Beep=lambda frequency, duration: beeps.append((frequency, duration))
)

from app.executors.advanced import GetClipboardExecutor, SetClipboardExecutor
from app.executors.base import ExecutionContext
from app.executors.basic import PlaySoundExecutor, SystemNotificationExecutor


def _result(value):
    return {
        "success": value.success,
        "message": value.message,
        "data": value.data,
        "error": value.error,
    }


async def _run(payload):
    executors = {
        "set_clipboard": SetClipboardExecutor,
        "get_clipboard": GetClipboardExecutor,
        "play_sound": PlaySoundExecutor,
        "system_notification": SystemNotificationExecutor,
    }
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await executors[payload["moduleType"]]().execute(
        payload.get("config", {}), context
    )
    return {"result": _result(result), "variables": context.variables, "beeps": beeps}


payload = json.loads(sys.stdin.read())
print(json.dumps(asyncio.run(_run(payload)), ensure_ascii=False))
