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
    from autoflow.infrastructure.process.windows_job import create_worker_job
    return create_worker_job()
