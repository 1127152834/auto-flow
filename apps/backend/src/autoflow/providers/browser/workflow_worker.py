from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from contextlib import nullcontext, redirect_stderr, redirect_stdout, suppress
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
from typing import Any, TextIO

from autoflow.infrastructure.filesystem.workflow_artifacts import WorkflowArtifacts
from autoflow.providers.browser.proxy_relay import BrowserProxyRelay
from autoflow.providers.browser.worker import (
    _boolean,
    _optional_proxy,
    _read_command,
    _required_string,
    _write,
    browser_launch_options,
)
from autoflow.providers.browser.workflow_executor import WorkflowExecutor


def run_worker(stopped: Event, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    try:
        command = _read_command(stdin)
        commands: Queue[dict[str, Any]] = Queue(maxsize=32)
        def read() -> None:
            try:
                for line in stdin:
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        break
                    commands.put_nowait(value)
            finally:
                stopped.set()
        Thread(target=read, daemon=True).start()
        return asyncio.run(_run(command, stopped, stdout, commands))
    except BaseException:  # noqa: BLE001 -- worker stdout never exposes library errors or credentials.
        _write(stdout, {"type": "finished", "state": "failed", "error": {
            "code": "workflow_worker_failed", "message": "工作流执行进程失败",
            "nodeId": None, "path": [],
        }})
        return 1


async def _run(command: dict[str, Any], stopped: Event, stdout: TextIO, commands: Queue[dict[str, Any]] | None = None) -> int:
    executable = Path(_required_string(os.environ, "CLOAKBROWSER_BINARY_PATH"))
    cache = Path(_required_string(os.environ, "CLOAKBROWSER_CACHE_DIR"))
    if not executable.is_absolute() or not executable.is_file() or not cache.is_absolute():
        raise ValueError("Invalid browser paths")
    launch = browser_launch_options(command, headless=_boolean(command, "headless"))
    upstream = _optional_proxy(command)
    relay_context = BrowserProxyRelay(upstream) if upstream is not None else nullcontext()
    context = None
    executor: WorkflowExecutor | None = None

    async def execute() -> dict[str, Any]:
        nonlocal context, executor
        from cloakbrowser import launch_context_async  # type: ignore[import-untyped]

        context = await launch_context_async(**launch)
        executor = WorkflowExecutor(
            context,
            WorkflowArtifacts(Path(command["runsRoot"]), command["runId"]),
            command["variables"], lambda event: _write(stdout, event),
        )
        if command.get('debug') is None:
            return await executor.run(command["document"], command["nodeIds"], command.get("executionPlan") or None)
        await executor.enable_debug(command['debug'])
        async def dispatch() -> None:
            while True:
                try:
                    request = commands.get_nowait() if commands is not None else None
                except Empty:
                    request = None
                if request is not None and executor is not None and executor.debug is not None:
                    await executor.debug.command(request)
                await asyncio.sleep(0.025)
        async def heartbeat() -> None:
            while True:
                _write(stdout, {'type': 'heartbeat'})
                if context is not None and not context.pages:
                    if executor is not None and executor.debug is not None and executor.debug.failure is None:
                        executor.debug.failure = {'code': 'workflow_browser_closed', 'message': '调试浏览器已关闭', 'nodeId': None, 'path': []}
                    stopped.set()
                await asyncio.sleep(2)
        tasks = [asyncio.create_task(dispatch()), asyncio.create_task(heartbeat())]
        try:
            return await executor.run(command["document"], command["nodeIds"], command.get("executionPlan") or None)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def watch_stop() -> None:
        while not stopped.is_set():
            await asyncio.sleep(0.025)

    result: dict[str, Any] = {"state": "cancelled", "error": None}
    try:
        with relay_context as relay:
            launch["proxy"] = {"server": relay.url} if relay is not None else None
            with (
                open(os.devnull, "w", encoding="utf-8") as sink,  # noqa: ASYNC230
                redirect_stdout(sink), redirect_stderr(sink),
            ):
                execution = asyncio.create_task(execute())
                stopping = asyncio.create_task(watch_stop())
                try:
                    done, _ = await asyncio.wait(
                        {execution, stopping}, return_when=asyncio.FIRST_COMPLETED,
                    )
                    if execution in done:
                        result = execution.result()
                    elif executor is not None and executor.debug is not None and executor.debug.failure:
                        result = {'state': 'failed', 'error': executor.debug.failure}
                finally:
                    execution.cancel()
                    stopping.cancel()
                    await asyncio.gather(execution, stopping, return_exceptions=True)
                    if stopped.is_set() and executor is not None and executor.debug is not None:
                        with suppress(OSError):
                            executor.debug.checkpoint('ended')
                    if context is not None:
                        with suppress(BaseException):
                            await context.close()
    finally:
        shutil.rmtree(cache, ignore_errors=True)
    _write(stdout, {"type": "finished", **result})
    return 0 if result["state"] in {"succeeded", "cancelled"} else 1
