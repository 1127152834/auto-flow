import os
import signal
import sys
from collections.abc import Callable
from pathlib import Path
from threading import Event, Thread

from autoflow.bootstrap.parent import watch_parent
from autoflow.infrastructure.process.browser_processes import (
    capture_processes,
    process_birth,
    signal_processes,
)
from autoflow.providers.browser.worker import run_worker

__test__ = False


def test_browser_worker_main() -> int:
    return browser_worker_main(run_worker)


def browser_worker_main(runner: Callable[[Event], int]) -> int:
    # JSONL is UTF-8 on every platform, including Windows legacy pipe locales.
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    job = _windows_kill_on_exit_job()
    stopped = Event()
    watcher_done = Event()

    def parent_exited() -> None:
        if sys.platform == "win32":
            # The current worker owns the kill-on-close Job. Closing this
            # process terminates its descendants without reopening any PID.
            os._exit(1)
        else:
            directory = os.environ.get("CLOAKBROWSER_CACHE_DIR")
            executable = os.environ.get("CLOAKBROWSER_BINARY_PATH")
            owned = capture_processes(os.getpid(), process_birth(os.getpid()),
                                      Path(directory) if directory else None, Path(executable) if executable else None)
            signal_processes(owned, signal.SIGKILL)

    Thread(
        target=watch_parent,
        args=(os.getppid(), watcher_done, parent_exited),
        daemon=True,
    ).start()
    try:
        return runner(stopped)
    finally:
        stopped.set()
        watcher_done.set()
        _ = job


def _windows_kill_on_exit_job():
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("per_process_user_time_limit", ctypes.c_int64),
            ("per_job_user_time_limit", ctypes.c_int64),
            ("limit_flags", wintypes.DWORD),
            ("minimum_working_set_size", ctypes.c_size_t),
            ("maximum_working_set_size", ctypes.c_size_t),
            ("active_process_limit", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority_class", wintypes.DWORD),
            ("scheduling_class", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in (
            "read_operation_count", "write_operation_count", "other_operation_count",
            "read_transfer_count", "write_transfer_count", "other_transfer_count",
        )]

    class ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("basic_limit_information", BasicLimitInformation),
            ("io_info", IoCounters),
            ("process_memory_limit", ctypes.c_size_t),
            ("job_memory_limit", ctypes.c_size_t),
            ("peak_process_memory_used", ctypes.c_size_t),
            ("peak_job_memory_used", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    info = ExtendedLimitInformation()
    info.basic_limit_information.limit_flags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
        error = ctypes.get_last_error()
        kernel.CloseHandle(handle)
        raise ctypes.WinError(error)
    if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        error = ctypes.get_last_error()
        kernel.CloseHandle(handle)
        raise ctypes.WinError(error)
    return handle
