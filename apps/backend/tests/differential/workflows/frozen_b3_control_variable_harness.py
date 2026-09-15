# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import random
import sys
from typing import Any

from app.executors.advanced import Base64Executor, JsonParseExecutor
from app.executors.advanced_assert import AssertCheckpointExecutor
from app.executors.base import ExecutionContext
from app.executors.basic import RandomNumberExecutor, SetVariableExecutor, WaitExecutor
from app.executors.basic_variable import GetTimeExecutor, IncrementDecrementExecutor
from app.executors.control import (
    BreakLoopExecutor,
    ConditionExecutor,
    ContinueLoopExecutor,
    ForeachExecutor,
    LoopExecutor,
)
from app.executors.control_extended import (
    ForeachDictExecutor,
    InfiniteLoopExecutor,
    StopWorkflowExecutor,
)

EXECUTORS = {
    executor().module_type: executor
    for executor in (
        ConditionExecutor,
        LoopExecutor,
        ForeachExecutor,
        InfiniteLoopExecutor,
        ForeachDictExecutor,
        BreakLoopExecutor,
        ContinueLoopExecutor,
        SetVariableExecutor,
        IncrementDecrementExecutor,
        JsonParseExecutor,
        Base64Executor,
        RandomNumberExecutor,
        GetTimeExecutor,
        WaitExecutor,
        StopWorkflowExecutor,
        AssertCheckpointExecutor,
    )
}


class _Locator:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state

    @property
    def first(self) -> _Locator:
        return self

    async def count(self) -> int:
        return self.state.get("count", 1)

    async def is_visible(self) -> bool:
        return self.state.get("visible", True)

    async def inner_text(self) -> str:
        return self.state.get("text", "")

    async def wait_for(self, **_options: Any) -> None:
        return None


class _Page:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state

    def locator(self, _selector: str) -> _Locator:
        return _Locator(self.state)

    async def wait_for_load_state(self, _state: str) -> None:
        return None


def _result(result: Any) -> dict[str, Any]:
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "branch": result.branch,
        "skipped": result.skipped,
    }


async def _run(payload: dict[str, Any]) -> dict[str, Any]:
    context = ExecutionContext(variables=payload.get("variables", {}))
    context.loop_stack = payload.get("loop_stack", [])
    if "page" in payload:
        context.page = _Page(payload["page"])
    random.seed(payload.get("seed", 0))
    result = await EXECUTORS[payload["type"]]().execute(payload["config"], context)
    return {
        "result": _result(result),
        "variables": context.variables,
        "loop_stack": context.loop_stack,
        "signals": {
            "break": context.should_break,
            "continue": context.should_continue,
            "stop": context.stop_workflow,
            "reason": context.stop_reason,
        },
    }


def main() -> None:
    payload = json.loads(sys.stdin.read())
    if payload.get("operation") == "types":
        print(json.dumps({"types": sorted(EXECUTORS)}, ensure_ascii=False))
        return
    print(json.dumps(asyncio.run(_run(payload)), ensure_ascii=False))


if __name__ == "__main__":
    main()
