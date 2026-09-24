# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys

from app.executors.base import ExecutionContext
from app.executors.trigger import ElementChangeTriggerExecutor


class Locator:
    @property
    def first(self):
        return self

    async def wait_for(self, **_options):
        return None


class Page:
    def __init__(self, result):
        self.result = result

    def locator(self, _selector):
        return Locator()

    async def evaluate(self, _expression, _argument=None):
        return self.result


async def run(payload):
    context = ExecutionContext(
        browser_context=object(), page=Page(payload.get("observer", {}))
    )
    result = await ElementChangeTriggerExecutor().execute(
        payload.get("config", {}), context
    )
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


print(json.dumps(asyncio.run(run(json.loads(sys.stdin.read()))), ensure_ascii=False))
