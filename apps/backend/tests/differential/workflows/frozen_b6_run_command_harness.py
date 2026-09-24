# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys

from app.executors.advanced import RunCommandExecutor
from app.executors.base import ExecutionContext


def _result(value):
    return {
        "success": value.success,
        "message": value.message,
        "data": value.data,
        "error": value.error,
        "branch": value.branch,
        "skipped": value.skipped,
    }


async def _run(payload):
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await RunCommandExecutor().execute(payload["config"], context)
    return {"result": _result(result), "variables": context.variables}


payload = json.loads(sys.stdin.read())
print(json.dumps(asyncio.run(_run(payload)), ensure_ascii=False))
