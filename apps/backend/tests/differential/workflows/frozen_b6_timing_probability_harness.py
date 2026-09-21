# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import random
import sys

from app.executors.base import ExecutionContext
from app.executors.control import ScheduledTaskExecutor
from app.executors.probability import ProbabilityTriggerExecutor


async def run(payload):
    random.seed(payload.get("seed", 1))
    executor = {
        "scheduled_task": ScheduledTaskExecutor,
        "probability_trigger": ProbabilityTriggerExecutor,
    }[payload["moduleType"]]()
    result = await executor.execute(payload.get("config", {}), ExecutionContext())
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "branch": result.branch,
    }


print(json.dumps(asyncio.run(run(json.loads(sys.stdin.read()))), ensure_ascii=False))
