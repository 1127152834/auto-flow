# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys

from app.executors.allure import (
    AllureAddAttachmentExecutor,
    AllureAddStepExecutor,
    AllureGenerateReportExecutor,
    AllureInitExecutor,
    AllureStartTestExecutor,
    AllureStopTestExecutor,
)
from app.executors.base import ExecutionContext

EXECUTORS = {
    executor().module_type: executor
    for executor in (
        AllureInitExecutor,
        AllureStartTestExecutor,
        AllureAddStepExecutor,
        AllureAddAttachmentExecutor,
        AllureStopTestExecutor,
        AllureGenerateReportExecutor,
    )
}


async def run(payload):
    context = ExecutionContext(variables=payload.get("variables", {}))
    results = []
    for item in payload["steps"]:
        result = await EXECUTORS[item["moduleType"]]().execute(
            item.get("config", {}), context
        )
        data = result.data
        if item["moduleType"] == "allure_init" and data:
            data = {"suite_id": "<uuid>"}
        results.append(
            {
                "success": result.success,
                "message": result.message,
                "data": data,
                "error": result.error,
            }
        )
    return results


print(json.dumps(asyncio.run(run(json.loads(sys.stdin.read()))), ensure_ascii=False))
