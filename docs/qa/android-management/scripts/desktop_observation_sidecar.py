"""Real sidecar with opt-in timings/counters only; never substitutes responses."""
import asyncio
import json
import os
import time
from pathlib import Path

from autoflow.providers.android.mac_runtime import MacAndroidRuntime
from fastapi import FastAPI

log_path = Path(os.environ['AUTOFLOW_QA_OBSERVATION_LOG'])
original_call = FastAPI.__call__
original_inspect = MacAndroidRuntime.inspect
preview_inflight = 0


def record(event):
    with log_path.open('a') as stream:
        stream.write(json.dumps({'time': time.time(), **event}) + '\n')


async def call(self, scope, receive, send):
    global preview_inflight
    path = scope.get('path', '')
    measured = scope['type'] == 'http' and path.startswith('/api/v1/android')
    preview = measured and path.endswith('/preview')
    if preview:
        preview_inflight += 1
    started = time.monotonic()
    try:
        return await original_call(self, scope, receive, send)
    finally:
        if measured:
            record({'kind': 'http', 'path': path, 'method': scope.get('method'), 'durationMs': (time.monotonic() - started) * 1000, 'previewInflight': preview_inflight if preview else None})
        if preview:
            preview_inflight -= 1


async def inspect(self, device):
    started = time.monotonic()
    try:
        return await original_inspect(self, device)
    finally:
        record({'kind': 'inspect', 'deviceId': device['deviceId'], 'durationMs': (time.monotonic() - started) * 1000, 'task': asyncio.current_task().get_name()})


if __name__ == '__main__':
    from autoflow.__main__ import main

    FastAPI.__call__ = call
    MacAndroidRuntime.inspect = inspect
    main()
