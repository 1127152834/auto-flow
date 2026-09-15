from __future__ import annotations

import asyncio
import io
import json
import random
import sys
from contextlib import redirect_stdout
from typing import Any
from uuid import UUID

from app.executors import utility_tools
from app.executors.base import ExecutionContext

CLASS_NAMES = (
    "RandomPasswordGeneratorExecutor",
    "URLEncodeDecodeExecutor",
    "MD5EncryptExecutor",
    "SHAEncryptExecutor",
    "TimestampConverterExecutor",
    "RGBToHSVExecutor",
    "RGBToCMYKExecutor",
    "HEXToCMYKExecutor",
    "UUIDGeneratorExecutor",
)
SOURCE_EXECUTORS = {
    executor().module_type: executor
    for executor in (getattr(utility_tools, name) for name in CLASS_NAMES)
}


def _prepare_deterministic_sources(seed: int) -> None:
    generator = random.Random(seed)
    utility_tools.secrets.choice = generator.choice
    utility_tools.uuid.uuid1 = lambda: UUID("12345678-1234-1234-9234-123456789abc")
    utility_tools.uuid.uuid4 = lambda: UUID("12345678-1234-4234-9234-123456789abc")


async def run(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("operation") == "types":
        return {"types": sorted(SOURCE_EXECUTORS)}
    _prepare_deterministic_sources(int(payload.get("seed", 8675309)))
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
