# mypy: ignore-errors
from __future__ import annotations

import asyncio
import ctypes
import json
import subprocess
import sys
from types import SimpleNamespace

beeps: list[tuple[int, int]] = []
sys.modules["winsound"] = SimpleNamespace(
    Beep=lambda frequency, duration: beeps.append((frequency, duration))
)

from app.executors.advanced import (
    GetClipboardExecutor,
    LockScreenExecutor,
    SetClipboardExecutor,
    ShutdownSystemExecutor,
)
from app.executors.base import ExecutionContext
from app.executors.basic import (
    PlaySoundExecutor,
    SystemNotificationExecutor,
)


def _result(value):
    return {
        "success": value.success,
        "message": value.message,
        "data": value.data,
        "error": value.error,
    }


async def _run(payload):
    commands = []
    subprocess.run = lambda command, **_options: (
        commands.append(command) or SimpleNamespace(returncode=0, stderr="")
    )
    ctypes.windll = SimpleNamespace(
        user32=SimpleNamespace(LockWorkStation=lambda: commands.append("lock_screen"))
    )
    executors = {
        "set_clipboard": SetClipboardExecutor,
        "get_clipboard": GetClipboardExecutor,
        "play_sound": PlaySoundExecutor,
        "system_notification": SystemNotificationExecutor,
        "shutdown_system": ShutdownSystemExecutor,
        "lock_screen": LockScreenExecutor,
    }
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await executors[payload["moduleType"]]().execute(
        payload.get("config", {}), context
    )
    return {"result": _result(result), "variables": context.variables, "beeps": beeps, "commands": commands}


payload = json.loads(sys.stdin.read())
print(json.dumps(asyncio.run(_run(payload)), ensure_ascii=False))
