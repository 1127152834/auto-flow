"""Fake artemis_bridge.py. Behaviour chosen by FAKE_MODE (ok, garbage, crash, hang, child, noread, grandchild)."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def emit(obj: object) -> None:
    print(json.dumps(obj), flush=True)


mode = os.environ.get("FAKE_MODE", "ok")
if sys.argv[1] == "helper-status":
    if mode == "hang":
        time.sleep(60)
    emit({"type": "helper", "installed": os.environ.get("FAKE_HELPER") == "1"})
    sys.exit(0)
if sys.argv[1] == "helper-install":
    if mode == "crash":
        print("helper boom", file=sys.stderr)
        sys.exit(3)
    emit({"type": "helper", "installed": True})
    sys.exit(0)

if mode == "noread":
    time.sleep(60)
instruction = sys.stdin.buffer.read().decode("utf-8")
if out := os.environ.get("FAKE_ENV_OUT"):
    Path(out).write_text(
        json.dumps({"env": dict(os.environ), "argv": sys.argv, "stdin": instruction}), encoding="utf-8"
    )
if mode == "crash":
    print("fatal: key=" + os.environ["AUTOFLOW_MODEL_SECRET"], file=sys.stderr)
    sys.exit(2)
if mode in ("hang", "child"):
    if mode == "child":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        Path(os.environ["FAKE_PID_FILE"]).write_text(str(child.pid))
    emit({"type": "step", "index": 1, "summary": "wait"})
    time.sleep(60)
emit({"type": "step", "index": 1, "summary": "a", "screenshot": "step-001.png"})
if mode == "garbage":
    print("not json", flush=True)
    print('{"type": "step", "ind', flush=True)
    print('{"no_type": 1}', flush=True)
    print("[1, 2]", flush=True)
if mode == "grandchild":
    gc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])  # inherits stdout/stderr
    Path(os.environ["FAKE_PID_FILE"]).write_text(str(gc.pid))
emit({"type": "step", "index": 2, "summary": "b"})
emit({"type": "result", "succeeded": True, "error": None, "traceId": "t", "artifacts": []})
