# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys

from app.executors.base import ExecutionContext
from app.executors.trigger import ApiTriggerExecutor


async def run(payload):
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await ApiTriggerExecutor().execute(payload.get("config", {}), context)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


print(json.dumps(asyncio.run(run(json.loads(sys.stdin.read()))), ensure_ascii=False))
