"""Terminate a node-owned subprocess tree without signalling the enclosing worker."""
from __future__ import annotations

import asyncio
import os
import shlex
import signal
import sys

from .project_browser_processes import (
    capture_processes,
    living_processes,
    process_birth,
)
from .project_test_browser_worker import force_process_tree


def split_script_arguments(arguments: str) -> list[str]:
    """POSIX quoting on Unix; native double-quote/backslash rules on Windows."""
    if "\x00" in arguments:
        raise ValueError("脚本参数不能包含 NUL 字符")
    if not arguments.strip():
        return []
    if sys.platform != "win32":
        return shlex.split(arguments, posix=True)
    import ctypes
    from ctypes import wintypes

    shell = ctypes.WinDLL("shell32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    parse = shell.CommandLineToArgvW
    parse.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(wintypes.LPWSTR)
    kernel.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel.LocalFree.restype = wintypes.HLOCAL
    count = ctypes.c_int()
    # argv[0] has different Windows parsing rules; consume a fixed dummy name.
    argv = parse("autoflow-python " + arguments, ctypes.byref(count))
    if not argv:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return [argv[index] for index in range(1, count.value)]
    finally:
        kernel.LocalFree(argv)


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
