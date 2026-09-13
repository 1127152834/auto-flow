from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import nullcontext, redirect_stderr, redirect_stdout, suppress
from queue import Empty, Queue
from threading import Event, Thread
from typing import Any, TextIO

from autoflow.providers.browser.inspection import BrowserInspection
from autoflow.providers.browser.inspection_script import PICKER_SCRIPT
from autoflow.providers.browser.proxy_relay import BrowserProxyRelay
from autoflow.providers.browser.worker import (
    _optional_proxy,
    _read_command,
    _write,
    browser_launch_options,
)
from autoflow.providers.browser.workflow_locator import NodeFailure


def run_worker(stopped: Event, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    command = _read_command(stdin)
    recording = command.get("recording", False)
    commands: Queue[dict[str, Any]] = Queue(maxsize=32)

    def read() -> None:
        try:
            for line in stdin:
                value = json.loads(line)
                if not isinstance(value, dict):
                    break
                commands.put_nowait(value)
        except Exception:  # noqa: BLE001 -- malformed control channel ends this worker.
            stopped.set()
        finally:
            stopped.set()

    Thread(target=read, daemon=True).start()
    return asyncio.run(_run(command, stopped, commands, stdout, recording=recording))


async def _run(command: dict[str, Any], stopped: Event, commands: Queue[dict[str, Any]], stdout: TextIO, *, recording: bool = False) -> int:
    context = None
    result: dict[str, Any] = {'state': 'succeeded', 'error': None}
    launch = browser_launch_options(command, headless=False)
    upstream = _optional_proxy(command)
    relay_context = BrowserProxyRelay(upstream) if upstream is not None else nullcontext()

    async def execute() -> None:
        nonlocal context
        from cloakbrowser import launch_context_async  # type: ignore[import-untyped]

        context = await launch_context_async(**launch)
        await context.add_init_script(PICKER_SCRIPT)
        from autoflow.providers.browser.recording import BrowserRecording
        inspection = BrowserRecording(context) if recording else BrowserInspection(context)
        if isinstance(inspection, BrowserRecording):
            await inspection.initialize()

        page = await context.new_page()
        inspection.target = next(key for key, value in inspection.pages.items() if value is page)

        async def heartbeat() -> None:
            while not stopped.is_set():
                snapshot = await inspection.snapshot()
                _write(stdout, {'type': 'inspection', **snapshot})
                if not snapshot['pages']:
                    stopped.set()
                    return
                await asyncio.sleep(0.25)

        async def dispatch() -> None:
            while not stopped.is_set():
                try:
                    request = commands.get_nowait()
                except Empty:
                    await asyncio.sleep(0.025)
                    continue
                try:
                    data = await inspection.command(request)
                    response = {'data': data}
                    if request['action'] == 'ack':
                        continue
                except NodeFailure as error:
                    response = {'error': {'code': error.code, 'message': error.message}}
                except Exception:  # noqa: BLE001 -- normalize browser failures at the process boundary.
                    response = {'error': {'code': 'INSPECTION_OPERATION_FAILED', 'message': '拾取操作超时或页面已变化'}}
                _write(stdout, {'type': 'response', 'commandId': request.get('commandId'), **response})

        tasks = [asyncio.create_task(heartbeat()), asyncio.create_task(dispatch())]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def watch_stop() -> None:
        while not stopped.is_set():
            await asyncio.sleep(0.025)

    try:
        with relay_context as relay:
            launch['proxy'] = {'server': relay.url} if relay is not None else None
            with open(os.devnull, 'w') as sink, redirect_stdout(sink), redirect_stderr(sink):  # noqa: ASYNC230
                task, watch = asyncio.create_task(execute()), asyncio.create_task(watch_stop())
                try:
                    done, _ = await asyncio.wait({task, watch}, return_when=asyncio.FIRST_COMPLETED)
                    if task in done:
                        task.result()
                finally:
                    task.cancel()
                    watch.cancel()
                    await asyncio.gather(task, watch, return_exceptions=True)
                    if context is not None:
                        with suppress(BaseException):
                            await context.close()
    except Exception:  # noqa: BLE001 -- normalize browser failures at the process boundary.
        result = {'state': 'failed', 'error': {'code': 'INSPECTION_WORKER_FAILED', 'message': '拾取浏览器启动或连接失败'}}
    _write(stdout, {'type': 'finished', **result})
    return 0 if result['state'] == 'succeeded' else 1
