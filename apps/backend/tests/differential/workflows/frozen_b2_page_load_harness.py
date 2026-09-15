from __future__ import annotations

import asyncio
import io
import json
import sys
from contextlib import redirect_stdout
from typing import Any

from app.executors.base import ExecutionContext
from app.executors.basic import PageLoadCompleteExecutor, WaitPageLoadExecutor


class Page:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[list[Any]] = []

    async def wait_for_load_state(self, state: str, *, timeout: float) -> None:
        self.calls.append([state, timeout])
        if self.fail:
            raise TimeoutError("fixture timeout")


class FailingContext(ExecutionContext):
    def set_variable(self, name: str, value: Any) -> None:
        raise RuntimeError("fixture variable write failed")


async def run(case: str) -> dict[str, Any]:
    if case == "missing":
        context = ExecutionContext()
        wait_result = await WaitPageLoadExecutor().execute({}, context)
        status_result = await PageLoadCompleteExecutor().execute({}, context)
        return {"errors": [wait_result.error, status_result.error]}

    fail = case in {"wait_failure", "status_pending"}
    page = Page(fail=fail)
    context_type = (
        FailingContext if case == "status_write_failure" else ExecutionContext
    )
    variables = (
        {}
        if case in {"wait_default", "status_default", "status_write_failure"}
        else {"state": "networkidle", "seconds": 2.5}
    )
    context = context_type(page=page, variables=variables)
    if case.startswith("wait_"):
        config = (
            {}
            if case == "wait_default"
            else {"waitUntil": "{state}", "timeout": "{seconds}"}
        )
        result = await WaitPageLoadExecutor().execute(config, context)
    elif case.startswith("status_"):
        config = (
            {}
            if case in {"status_default", "status_write_failure"}
            else {"checkState": "{state}", "saveToVariable": "{status_name}"}
        )
        result = await PageLoadCompleteExecutor().execute(config, context)
    else:
        raise ValueError(case)

    return {
        "success": result.success,
        "message": result.message,
        "error": result.error,
        "data": result.data,
        "calls": page.calls,
        "variables": context.variables,
    }


if __name__ == "__main__":
    output = io.StringIO()
    with redirect_stdout(output):
        result = asyncio.run(run(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
