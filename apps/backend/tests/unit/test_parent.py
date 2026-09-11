import subprocess
import sys
from threading import Event, Thread

from autoflow.bootstrap.parent import watch_parent


def test_sidecar_observes_parent_exit():
    parent = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    stopped, exited = Event(), Event()
    watcher = Thread(target=watch_parent, args=(parent.pid, stopped, exited.set), daemon=True)
    watcher.start()
    try:
        assert not exited.wait(0.1)
        parent.terminate()
        parent.wait(timeout=5)
        assert exited.wait(5)
    finally:
        stopped.set()
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        watcher.join(timeout=2)
