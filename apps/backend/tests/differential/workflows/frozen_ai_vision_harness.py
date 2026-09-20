# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import httpx
from app.executors.ai import AIVisionExecutor
from app.executors.base import ExecutionContext


class _Response:
    status_code = 200
    text = ""

    def json(self):
        return {
            "choices": [{"message": {"content": "识别结果"}}],
            "usage": {"total_tokens": 4},
        }


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
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await AIVisionExecutor().execute(payload["config"], context)
    return {
        "success": result.success,
        "message": result.message,
        "response": result.data.get("response"),
        "image_source": result.data.get("image_source"),
        "error": result.error,
        "variables": context.variables,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run(json.load(sys.stdin))), ensure_ascii=False))
