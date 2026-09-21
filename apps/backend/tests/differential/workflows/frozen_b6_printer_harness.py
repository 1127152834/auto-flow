# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
from types import SimpleNamespace

mode = SimpleNamespace()
calls = []
sys.modules["win32print"] = SimpleNamespace(
    PRINTER_ENUM_LOCAL=1,
    PRINTER_ENUM_CONNECTIONS=2,
    GetDefaultPrinter=lambda: "Office",
    EnumPrinters=lambda _flags: [(None, None, "Office")],
    OpenPrinter=lambda name: calls.append(["open", name]) or "handle",
    GetPrinter=lambda _handle, _level: {"pDevMode": mode},
    SetPrinter=lambda handle, level, _properties, command: calls.append(
        ["set", handle, level, command]
    ),
    ClosePrinter=lambda handle: calls.append(["close", handle]),
)
sys.modules["win32api"] = SimpleNamespace(
    ShellExecute=lambda *args: calls.append(["print", *args])
)

from app.executors.base import ExecutionContext  # noqa: E402
from app.executors.utility_tools import PrinterCallExecutor  # noqa: E402


async def run(payload):
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await PrinterCallExecutor().execute(payload.get("config", {}), context)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
        "mode": vars(mode),
        "calls": calls,
    }


print(json.dumps(asyncio.run(run(json.loads(sys.stdin.read()))), ensure_ascii=False))
