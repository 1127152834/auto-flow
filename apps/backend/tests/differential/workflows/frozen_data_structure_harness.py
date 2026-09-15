from __future__ import annotations

import asyncio
import io
import json
import sys
from contextlib import redirect_stdout
from typing import Any

from app.executors.base import ExecutionContext
from app.executors.data_structure import (
    DictGetExecutor,
    DictKeysExecutor,
    DictOperationExecutor,
    ListExportExecutor,
    ListGetExecutor,
    ListLengthExecutor,
    ListOperationExecutor,
    RegexExtractExecutor,
    StringCaseExecutor,
    StringConcatExecutor,
    StringJoinExecutor,
    StringReplaceExecutor,
    StringSplitExecutor,
    StringSubstringExecutor,
    StringTrimExecutor,
)

SOURCE_EXECUTORS = {
    executor().module_type: executor
    for executor in (
        ListOperationExecutor,
        ListGetExecutor,
        ListLengthExecutor,
        ListExportExecutor,
        DictOperationExecutor,
        DictGetExecutor,
        DictKeysExecutor,
        RegexExtractExecutor,
        StringReplaceExecutor,
        StringSplitExecutor,
        StringJoinExecutor,
        StringConcatExecutor,
        StringTrimExecutor,
        StringCaseExecutor,
        StringSubstringExecutor,
    )
}


async def run(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("operation") == "types":
        return {"types": sorted(SOURCE_EXECUTORS)}
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await SOURCE_EXECUTORS[payload["type"]]().execute(
        payload["config"], context
    )
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


if __name__ == "__main__":
    output = io.StringIO()
    payload = json.load(sys.stdin)
    with redirect_stdout(output):
        result = asyncio.run(run(payload))
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
