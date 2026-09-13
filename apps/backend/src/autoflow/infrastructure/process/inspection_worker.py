"""Inspection commands over the existing owned browser-worker transport."""
from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from autoflow.domain.profiles.models import Profile, ProfileBrowserProxy
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import PreparedWorkflow
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


class InspectionWorkerManager(WorkflowWorkerManager):
    def __init__(self, temp_root: Path) -> None:
        command = (sys.executable, "--inspection-worker") if getattr(sys, "frozen", False) else (
            sys.executable, "-m", "autoflow", "--inspection-worker",
        )
        super().__init__(temp_root / "inspection", temp_root, command=command)
        self._process: asyncio.subprocess.Process | None = None
        self._responses: dict[str, asyncio.Future[dict[str, Any]]] = {}

    def _payload(self, run_id: str, prepared: PreparedWorkflow, profile: Profile,
                 proxy: ProfileBrowserProxy | None, license_key: str | None) -> dict[str, Any]:
        payload = super()._payload(run_id, prepared, profile, proxy, license_key)
        for key in ("document", "nodeIds", "variables", "runsRoot", "executionPlan"):
            payload.pop(key)
        return {**payload, "headless": False}

    async def command(self, session_id: str, command: dict[str, Any]) -> dict[str, Any]:
        process = self._process
        if session_id not in self._tasks or process is None or process.stdin is None or process.returncode is not None:
            raise WorkflowError("INSPECTION_UNAVAILABLE", "拾取浏览器尚未就绪或已关闭", 409)
        identifier = uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self._responses[identifier] = future
        try:
            process.stdin.write((json.dumps({**command, "commandId": identifier}, ensure_ascii=False) + "\n").encode())
            await asyncio.wait_for(process.stdin.drain(), 5)
            response = await asyncio.wait_for(asyncio.shield(future), 15)
            if response.get("error"):
                error = response["error"]
                raise WorkflowError(error["code"], error["message"], 422)
            return dict(response["data"])
        except (TimeoutError, BrokenPipeError, ConnectionError):
            raise WorkflowError("INSPECTION_RESPONSE_UNKNOWN", "浏览器响应暂不可用，请重新查询会话", 503) from None
        finally:
            self._responses.pop(identifier, None)
            if not future.done():
                future.cancel()

    async def _exchange(self, process: asyncio.subprocess.Process, payload: dict[str, Any],
                        prepared: PreparedWorkflow,
                        on_event: Callable[[dict[str, Any]], Awaitable[None]]) -> dict[str, Any]:
        assert process.stdin is not None and process.stdout is not None
        self._process = process
        try:
            process.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode())
            async with asyncio.timeout(self._start_timeout):
                await process.stdin.drain()
            timeout = self._start_timeout
            while True:
                async with asyncio.timeout(timeout):
                    raw = await process.stdout.readline()
                if not raw:
                    return {"state": "failed", "error": {"code": "INSPECTION_WORKER_EXITED", "message": "拾取进程意外退出"}}
                event = json.loads(raw)
                if event.get("type") == "finished":
                    return {"state": event["state"], "error": event.get("error")}
                if event.get("type") == "response":
                    future = self._responses.get(event.get("commandId"))
                    if future is not None and not future.done():
                        future.set_result(event)
                elif event.get("type") == "inspection":
                    timeout = 20  # Heartbeat keeps silent browser/driver failures bounded.
                    await on_event(event)
                else:
                    raise ValueError("Invalid inspection event")
        finally:
            self._process = None
            for future in self._responses.values():
                if not future.done():
                    future.set_result({"error": {"code": "INSPECTION_CLOSED", "message": "拾取会话已结束"}})
