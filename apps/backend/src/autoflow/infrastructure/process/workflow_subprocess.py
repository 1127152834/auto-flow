"""Terminate a node-owned subprocess tree without signalling the enclosing worker."""
from __future__ import annotations

import asyncio
import os
import signal
import sys

from .project_browser_processes import (
    capture_processes,
    living_processes,
    process_birth,
)
from .project_test_browser_worker import force_process_tree


async def terminate_subprocess(process: asyncio.subprocess.Process) -> None:
    if sys.platform == "win32":
        await force_process_tree(process, 3)
        return
    birth = process_birth(process.pid)
    if birth is None and process.returncode is None:
        raise RuntimeError("子进程身份尚未确认，无法清理")
    owned = await asyncio.to_thread(capture_processes, process.pid, birth, None, None)
    # Nodes share the worker group. Kill verified PIDs, never that entire group.
    for pid, (_, started) in owned.items():
        if process_birth(pid) == started:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    await asyncio.wait_for(process.wait(), 3)
    async with asyncio.timeout(3):
        while await asyncio.to_thread(living_processes, owned):
            await asyncio.sleep(.01)


def workflow_environment(environment: dict[str, str]) -> dict[str, str]:
    """Worker scripts do not need the sidecar's HTTP or host authority."""
    return {key: value for key, value in environment.items()
            if key not in {"AUTOFLOW_INSTANCE_TOKEN", "AUTOFLOW_HOST_TOKEN"}}
