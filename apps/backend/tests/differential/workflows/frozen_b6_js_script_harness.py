# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
import types

from app.executors.base import ExecutionContext
from app.executors.basic import JsScriptExecutor


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
    def request_js_script_sync(**_values):
        return payload["response"]

    main = types.ModuleType("app.main")
    main.request_js_script_sync = request_js_script_sync
    sys.modules["app.main"] = main
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await JsScriptExecutor().execute(payload["config"], context)
    return {"result": _result(result), "variables": context.variables}


payload = json.loads(sys.stdin.read())
print(json.dumps(asyncio.run(_run(payload)), ensure_ascii=False))
