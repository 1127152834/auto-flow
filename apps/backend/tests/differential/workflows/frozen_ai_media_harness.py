# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
from types import SimpleNamespace
from typing import Any

from app.executors.ai_media import AIGenerateImageExecutor, AIGenerateVideoExecutor
from app.executors.base import ExecutionContext


class _Response:
    status_code = 200
    text = ""

    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    def json(self) -> dict[str, Any]:
        return self._body


class _Client:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url: str, **_kwargs):
        if url.endswith("/images/generations"):
            return _Response({"data": [{"url": "https://media.example/image.png"}]})
        return _Response({"video_url": "https://media.example/video.mp4"})


async def run(payload: dict[str, Any]) -> dict[str, Any]:
    sys.modules["httpx"] = SimpleNamespace(AsyncClient=lambda **_kwargs: _Client())
    executor = (
        AIGenerateImageExecutor()
        if payload["type"] == "ai_generate_image"
        else AIGenerateVideoExecutor()
    )
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await executor.execute(payload["config"], context)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run(json.load(sys.stdin))), ensure_ascii=False))
