# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
import types
from typing import Any


class SmartScraperGraph:
    def __init__(self, *, prompt, source, config):
        self.prompt = prompt

    def run(self):
        if "selector" in self.prompt:
            return {"selector": "#login", "description": "登录按钮", "confidence": 96}
        return {"items": ["一", "二"]}


graphs = types.ModuleType("scrapegraphai.graphs")
graphs.SmartScraperGraph = SmartScraperGraph
package = types.ModuleType("scrapegraphai")
package.graphs = graphs
sys.modules["scrapegraphai"] = package
sys.modules["scrapegraphai.graphs"] = graphs

from app.executors.ai_scraper import AIElementSelectorExecutor, AISmartScraperExecutor
from app.executors.base import ExecutionContext


async def run(payload: dict[str, Any]) -> dict[str, Any]:
    context = ExecutionContext(variables={})
    executor = (
        AISmartScraperExecutor()
        if payload["type"] == "ai_smart_scraper"
        else AIElementSelectorExecutor()
    )
    result = await executor.execute(payload["config"], context)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run(json.load(sys.stdin))), ensure_ascii=False))
