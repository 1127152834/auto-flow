# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys

from app.executors.base import ExecutionContext
from app.executors.basic import GroupExecutor
from app.executors.note import NoteExecutor

EXECUTORS = {
    executor().module_type: executor for executor in (GroupExecutor, NoteExecutor)
}


async def _run(module_type: str) -> dict[str, object]:
    result = await EXECUTORS[module_type]().execute({}, ExecutionContext())
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
    }


def main() -> None:
    payload = json.loads(sys.stdin.read())
    print(json.dumps(asyncio.run(_run(payload["type"])), ensure_ascii=False))


if __name__ == "__main__":
    main()
