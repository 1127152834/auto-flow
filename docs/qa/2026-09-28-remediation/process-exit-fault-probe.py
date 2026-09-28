"""Real SIGKILL after reading process birth; no fake API responses."""
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
    original_birth = processes.process_birth
    evidence = {}
    try:
        assert child.stdout.readline() == b"READY\n"
        birth = processes.process_birth(child.pid)
        assert birth is not None

        def terminate_after_identity_read(pid):
            observed_birth = original_birth(pid)
            if pid == child.pid and "stateAfterSignal" not in evidence:
                assert observed_birth == birth
                os.kill(pid, signal.SIGKILL)
                deadline = time.monotonic() + 1
                state = process_state(pid)
                while not state.startswith("Z") and state and time.monotonic() < deadline:
                    time.sleep(0.01)
                    state = process_state(pid)
                evidence.update({"stateAfterSignal": state or "gone",
                                 "existsAfterSignal": processes._process_exists(pid),
                                 "birthAfterSignal": original_birth(pid),
                                 "nativeArgumentsAvailable": processes._native_arguments(pid) is not None})
            return observed_birth

        processes.process_birth = terminate_after_identity_read
        try:
            owned = processes.capture_processes(
                child.pid, birth, directory, None, strict_ownership=True,
            )
            evidence["capture"] = {"status": "returned", "ownedCount": len(owned)}
        except RuntimeError as error:
            evidence["capture"] = {"status": "raised", "error": str(error)}
    finally:
        processes.process_birth = original_birth
        child.wait(timeout=12)
        if child.stdout is not None:
            child.stdout.close()
        evidence["childReaped"] = child.returncode is not None
        evidence["childReturnCode"] = child.returncode
print(json.dumps(evidence, indent=2))
if "--expect-cleanup" in sys.argv:
    assert evidence["capture"]["status"] == "returned", evidence["capture"]
    assert evidence["capture"]["ownedCount"] == 1, evidence["capture"]
    assert evidence["childReaped"] and evidence["childReturnCode"] == -signal.SIGKILL
