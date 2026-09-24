from __future__ import annotations

import sys


def inspection_worker_command() -> tuple[str, ...]:
    if getattr(sys, "frozen", False):
        return (sys.executable, "--inspection-worker")
    return (sys.executable, "-m", "autoflow", "--inspection-worker")
