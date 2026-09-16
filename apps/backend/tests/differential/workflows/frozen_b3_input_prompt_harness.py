# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
import types

from app.executors.base import ExecutionContext
from app.executors.basic import InputPromptExecutor


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
    response = payload.get("response")
    captured = []

    def request_input_prompt_sync(**values):
        captured.append(values)
        return response

    main = types.ModuleType("app.main")
    main.request_input_prompt_sync = request_input_prompt_sync
    sys.modules["app.main"] = main
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await InputPromptExecutor().execute(payload["config"], context)
    return {"result": _result(result), "variables": context.variables, "requests": captured}


payload = json.loads(sys.stdin.read())
print(json.dumps(asyncio.run(_run(payload)), ensure_ascii=False))
