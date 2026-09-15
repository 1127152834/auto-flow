# mypy: ignore-errors
# Imports execute only against the frozen WebRPA PYTHONPATH.
from __future__ import annotations

import asyncio
import io
import json
import sys
from contextlib import redirect_stdout
from types import SimpleNamespace
from typing import Any

from app.executors.advanced import NetworkCaptureExecutor
from app.executors.base import ExecutionContext


class FakePage:
    def __init__(self, requests: list[dict[str, str]]) -> None:
        self._requests = requests
        self.listeners: dict[str, list[Any]] = {}

    def on(self, name: str, listener: Any) -> None:
        self.listeners.setdefault(name, []).append(listener)
        if name == "request":
            for request in self._requests:
                listener(SimpleNamespace(**request))

    def remove_listener(self, name: str, listener: Any) -> None:
        self.listeners.get(name, []).remove(listener)


def result_payload(result: Any) -> dict[str, Any]:
    return {
        "success": result.success,
        "message": result.message,
        "error": result.error,
        "data": result.data,
    }


async def run(payload: dict[str, Any]) -> dict[str, Any]:
    page = FakePage(payload.get("requests", [])) if payload.get("page", True) else None
    context = ExecutionContext(page=page)
    result = await NetworkCaptureExecutor().execute(payload["config"], context)
    return {
        "result": result_payload(result),
        "variables": context.variables,
        "listener_count": len(page.listeners.get("request", [])) if page else 0,
    }


if __name__ == "__main__":
    output = io.StringIO()
    with redirect_stdout(output):
        result = asyncio.run(run(json.load(sys.stdin)))
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
