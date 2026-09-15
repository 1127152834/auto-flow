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

from app.executors.base import ExecutionContext
from app.executors.network_monitor import (
    NetworkMonitorStartExecutor,
    NetworkMonitorStopExecutor,
    NetworkMonitorWaitExecutor,
)


class FakePage:
    def __init__(self) -> None:
        self.listeners: dict[str, list[Any]] = {}

    def on(self, name: str, listener: Any) -> None:
        self.listeners.setdefault(name, []).append(listener)

    def remove_listener(self, name: str, listener: Any) -> None:
        self.listeners.get(name, []).remove(listener)

    def emit_request(self, url: str, resource_type: str = "fetch") -> None:
        request = SimpleNamespace(
            url=url,
            method="GET",
            resource_type=resource_type,
            headers={"accept": "application/json"},
        )
        for listener in list(self.listeners.get("request", [])):
            listener(request)


def result_payload(result: Any) -> dict[str, Any]:
    return {
        "success": result.success,
        "message": result.message,
        "error": result.error,
        "data": result.data,
    }


async def run(payload: dict[str, Any]) -> dict[str, Any]:
    page = FakePage()
    context = ExecutionContext(page=page)
    if payload["operation"] == "errors":
        return {
            "start": result_payload(
                await NetworkMonitorStartExecutor().execute({"monitorId": ""}, context)
            ),
            "wait": result_payload(
                await NetworkMonitorWaitExecutor().execute(
                    {"monitorId": "default", "urlPattern": ""}, context
                )
            ),
            "stop": result_payload(
                await NetworkMonitorStopExecutor().execute(
                    {"monitorId": "missing"}, context
                )
            ),
        }
    started = await NetworkMonitorStartExecutor().execute(
        {"monitorId": "orders", "filterType": "api", "urlPattern": "/api/"},
        context,
    )
    page.emit_request("https://local.test/api/orders")
    page.emit_request("https://local.test/logo.png", "image")
    waited = await NetworkMonitorWaitExecutor().execute(
        {
            "monitorId": "orders",
            "urlPattern": "orders",
            "timeout": 1,
            "captureMode": "first",
            "variableName": "request",
        },
        context,
    )
    stopped = await NetworkMonitorStopExecutor().execute(
        {"monitorId": "orders", "variableName": "allRequests"}, context
    )
    for value in context.variables.values():
        requests = value if isinstance(value, list) else [value]
        for request in requests:
            if isinstance(request, dict):
                request.pop("timestamp", None)
    for result in (waited, stopped):
        requests = result.data.get("requests", []) if result.data else []
        for request in requests:
            request.pop("timestamp", None)
    return {
        "started": result_payload(started),
        "waited": result_payload(waited),
        "stopped": result_payload(stopped),
        "variables": context.variables,
    }


if __name__ == "__main__":
    output = io.StringIO()
    with redirect_stdout(output):
        result = asyncio.run(run(json.load(sys.stdin)))
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
