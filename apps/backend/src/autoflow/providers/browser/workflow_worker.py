from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from threading import Event, Thread
from typing import Any, TextIO

from .workflow_session import launch_workflow_session


def run_workflow_worker(
    stopped: Event, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout
) -> int:
    try:
        command = _read_command(stdin)
        Thread(target=_watch_stdin, args=(stdin, stopped), daemon=True).start()
        return asyncio.run(_run(command, stopped, stdout))
    except BaseException:  # noqa: BLE001 -- secrets and browser details stay isolated.
        _write(stdout, {"type": "error", "error": "Workflow worker failed"})
        return 1


async def _run(command: dict[str, Any], stopped: Event, stdout: TextIO) -> int:
    executable = Path(_required_environment("CLOAKBROWSER_BINARY_PATH"))
    cache = Path(_required_environment("CLOAKBROWSER_CACHE_DIR"))
    if not executable.is_absolute() or not executable.is_file() or not cache.is_absolute():
        raise ValueError("workflow worker paths are invalid")
    run_id = _required_string(command, "runId")
    profile_id = _required_string(command, "profileId")
    async with launch_workflow_session(command):
        _write(stdout, {"type": "ready", "runId": run_id, "profileId": profile_id})
        while not stopped.is_set():
            await asyncio.sleep(0.05)
    return 0


def _read_command(stdin: TextIO) -> dict[str, Any]:
    raw = stdin.readline()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError("workflow worker command must be an object")
    return value


def _watch_stdin(stdin: TextIO, stopped: Event) -> None:
    stdin.read()
    stopped.set()


def _required_string(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{key} must be a string")
    return value


def _required_environment(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise TypeError(f"{key} must be a string")
    return value


def _write(stdout: TextIO, event: dict[str, object]) -> None:
    stdout.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    stdout.flush()
