# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import app.executors.advanced_vision_act as source
import httpx
from app.executors.base import ExecutionContext


class _Response:
    status_code = 200
    text = ""

    def json(self):
        return {"choices": [{"message": {"content": '{"found":true,"x":500,"y":250}'}}]}


class _Client:
    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, _url, **_kwargs):
        return _Response()


async def run(payload: dict[str, Any]) -> dict[str, Any]:
    httpx.AsyncClient = _Client
    source._grab_screen_b64 = lambda: ("UEFHRQ==", 1200, 800)
    context = ExecutionContext(variables={})
    result = await source.AIVisionActExecutor().execute(payload["config"], context)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run(json.load(sys.stdin))), ensure_ascii=False))
