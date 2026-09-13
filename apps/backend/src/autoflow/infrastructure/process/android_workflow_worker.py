import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from typing import Any

from autoflow.domain.android.ports import AndroidError
from autoflow.domain.workflows.run_validation import PreparedWorkflow
from autoflow.infrastructure.process.test_browser_worker import _wait_for_spawn


class AndroidWorkflowWorker:
    def __init__(self) -> None:
        self.tasks: dict[str, asyncio.Task[dict[str, Any]]] = {}

    async def execute(self, run_id: str, prepared: PreparedWorkflow,
                      on_event: Callable[[dict[str, Any]], Awaitable[None]],
                      command: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
        task = asyncio.create_task(self._execute(prepared, on_event, command))
        self.tasks[run_id] = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                self.tasks.pop(run_id, None)

    async def stop(self, run_id: str) -> None:
        task = self.tasks.get(run_id)
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self.tasks.pop(run_id, None)

    async def _execute(self, prepared: PreparedWorkflow,
                       on_event: Callable[[dict[str, Any]], Awaitable[None]],
                       command: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
        args = [sys.executable, "--android-workflow-worker"] if getattr(sys, "frozen", False) else [sys.executable, "-m", "autoflow", "--android-workflow-worker"]
        spawn = asyncio.create_task(asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=65536))
        try:
            process = await asyncio.shield(spawn)
        except asyncio.CancelledError:
            process = await _wait_for_spawn(spawn)
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
        assert process.stdin is not None and process.stdout is not None
        events: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)

        async def read() -> None:
            assert process.stdout is not None
            while True:
                line = await asyncio.wait_for(process.stdout.readline(), 15)
                if not line:
                    raise AndroidError("ANDROID_WORKER_LOST", "安卓执行进程已断开", 503)
                event = json.loads(line)
                if event.get("type") != "heartbeat":
                    await events.put(event)

        async def connected(awaitable: Awaitable[Any]) -> Any:
            action = asyncio.ensure_future(awaitable)
            try:
                done, _ = await asyncio.wait({action, reader}, return_when=asyncio.FIRST_COMPLETED)
                if action in done:
                    return action.result()
                return reader.result()
            finally:
                if not action.done():
                    action.cancel()
                    await asyncio.gather(action, return_exceptions=True)

        reader = asyncio.create_task(read())
        try:
            payload = {"document": prepared.document, "nodeIds": prepared.node_ids, "variables": prepared.variables}
            encoded = (json.dumps(payload, ensure_ascii=False) + "\n").encode()
            if len(encoded) > 65536:
                raise AndroidError("ANDROID_WORKER_PAYLOAD", "安卓执行快照超过 64 KiB", 422)
            process.stdin.write(encoded)
            await process.stdin.drain()
            while True:
                event = await connected(events.get())
                if event["type"] == "finished":
                    return {"state": event["state"], "error": event.get("error")}
                if event["type"] == "android_command":
                    response = await connected(command(event))
                    process.stdin.write((json.dumps({"requestId": event["requestId"], **response}) + "\n").encode())
                    await process.stdin.drain()
                elif event["type"] in {"ready", "node_started", "node_succeeded", "node_failed"}:
                    await on_event(event)
                else:
                    raise AndroidError("ANDROID_WORKER_PROTOCOL", "无效的安卓执行事件", 502)
        finally:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 5)
                except TimeoutError:
                    process.kill()
                    await process.wait()
