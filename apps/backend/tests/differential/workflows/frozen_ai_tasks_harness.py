# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import app.executors.ai_tasks as source
from app.executors.base import ExecutionContext

EXECUTORS = {
    executor().module_type: executor
    for executor in (
        source.AIExtractExecutor,
        source.AIClassifyExecutor,
        source.AISummarizeExecutor,
        source.AITranslateExecutor,
        source.AISentimentExecutor,
        source.AINormalizeExecutor,
        source.AIDedupSemanticExecutor,
        source.AIRouteExecutor,
    )
}


async def _fixture_chat(config, _context, _system_prompt, _user_prompt):
    return True, config["_fixtureResponse"], ""


async def run(payload: dict[str, Any]) -> dict[str, Any]:
    source._chat_with_fallback = _fixture_chat
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await EXECUTORS[payload["type"]]().execute(payload["config"], context)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run(json.load(sys.stdin))), ensure_ascii=False))
