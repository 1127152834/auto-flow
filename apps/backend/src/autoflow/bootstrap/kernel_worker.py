import os
from threading import Event, Thread

from autoflow.bootstrap.parent import watch_parent
from autoflow.providers.kernel.worker import run_worker


def kernel_worker_main() -> int:
    stopped = Event()
    Thread(
        target=watch_parent,
        args=(os.getppid(), stopped, lambda: os._exit(1)),
        daemon=True,
    ).start()
    try:
        return run_worker()
    finally:
        stopped.set()
