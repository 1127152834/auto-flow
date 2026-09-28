"""Real SIGKILL at the native ownership-read boundary; no fake API responses."""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from autoflow.infrastructure.process import project_browser_processes as processes


def process_state(pid):
    return subprocess.run(
        ["ps", "-p", str(pid), "-o", "stat="],
        text=True, capture_output=True, check=False,
    ).stdout.strip()


with tempfile.TemporaryDirectory(prefix="autoflow-process-fault-") as raw:
    directory = Path(raw).resolve()
    child = subprocess.Popen(
        [sys.executable, "-c", 'import time; print("READY", flush=True); time.sleep(10)',
         "--project-workflow-worker"],
        env={**os.environ, "CLOAKBROWSER_CACHE_DIR": str(directory)},
        start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    original = processes._native_arguments
    evidence = {}
    try:
        assert child.stdout.readline() == b"READY\n"
        birth = processes.process_birth(child.pid)
        assert birth is not None

        def terminate_before_read(pid):
            if pid == child.pid:
                assert processes.process_birth(pid) == birth
                os.kill(pid, signal.SIGKILL)
                deadline = time.monotonic() + 1
                state = process_state(pid)
                while not state.startswith("Z") and state and time.monotonic() < deadline:
                    time.sleep(0.01)
                    state = process_state(pid)
                evidence.update({"stateAfterSignal": state or "gone",
                                 "existsAfterSignal": processes._process_exists(pid),
                                 "birthAfterSignal": processes.process_birth(pid)})
            result = original(pid)
            if pid == child.pid:
                evidence["nativeArgumentsAvailable"] = result is not None
            return result

        processes._native_arguments = terminate_before_read
        try:
            owned = processes.capture_processes(
                child.pid, birth, directory, None, strict_ownership=True,
            )
            evidence["capture"] = {"status": "returned", "ownedCount": len(owned)}
        except RuntimeError as error:
            evidence["capture"] = {"status": "raised", "error": str(error)}
    finally:
        processes._native_arguments = original
        child.wait(timeout=12)
        if child.stdout is not None:
            child.stdout.close()
        evidence["childReaped"] = child.returncode is not None
        evidence["childReturnCode"] = child.returncode
print(json.dumps(evidence, indent=2))
