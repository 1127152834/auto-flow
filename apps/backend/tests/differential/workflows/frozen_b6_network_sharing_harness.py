# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
from types import SimpleNamespace


def start_file_share(path, port, share_type, name, allow_write=True):
    return {
        "success": True,
        "url": f"http://192.0.2.1:{port}",
        "ip": "192.0.2.1",
        "port": port,
    }


def stop_file_share(port):
    return {"success": True, "port": port}


def start_screen_share(port, fps, quality, scale):
    return {
        "success": True,
        "url": f"http://192.0.2.1:{port}",
        "ip": "192.0.2.1",
        "port": port,
    }


def stop_screen_share(port):
    return {"success": True, "port": port}


sys.modules["app.services.file_share"] = SimpleNamespace(
    start_file_share=start_file_share,
    stop_file_share=stop_file_share,
    get_local_ip=lambda: "192.0.2.1",
)
sys.modules["app.services.screen_share"] = SimpleNamespace(
    start_screen_share=start_screen_share,
    stop_screen_share=stop_screen_share,
    get_local_ip=lambda: "192.0.2.1",
)

from app.executors.advanced import (
    ShareFileExecutor,
    ShareFolderExecutor,
    StopShareExecutor,
)
from app.executors.base import ExecutionContext
from app.executors.screen_share import (
    StartScreenShareExecutor,
    StopScreenShareExecutor,
)


async def run(payload):
    executors = {
        "share_file": ShareFileExecutor,
        "share_folder": ShareFolderExecutor,
        "stop_share": StopShareExecutor,
        "start_screen_share": StartScreenShareExecutor,
        "stop_screen_share": StopScreenShareExecutor,
    }
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await executors[payload["moduleType"]]().execute(
        payload.get("config", {}), context
    )
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


print(json.dumps(asyncio.run(run(json.loads(sys.stdin.read()))), ensure_ascii=False))
