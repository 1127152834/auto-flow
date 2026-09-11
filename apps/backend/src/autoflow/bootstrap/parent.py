"""Stop the server when its desktop host disappears, including abrupt host exits."""
import os
import sys
from collections.abc import Callable
from threading import Event


def watch_parent(parent_pid: int, stopped: Event, on_exit: Callable[[], None]) -> None:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x00100000, False, parent_pid)  # SYNCHRONIZE only
        if not handle:
            on_exit()
            return
        try:
            while not stopped.is_set():
                if kernel.WaitForSingleObject(handle, 250) != 258:  # WAIT_TIMEOUT
                    on_exit()
                    return
        finally:
            kernel.CloseHandle(handle)
    else:
        while not stopped.is_set():
            try:
                os.kill(parent_pid, 0)
            except ProcessLookupError:
                on_exit()
                return
            except PermissionError:
                pass  # A live process that we cannot signal is still a live parent.
            stopped.wait(0.25)
