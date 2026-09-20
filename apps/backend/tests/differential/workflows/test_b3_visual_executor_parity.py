from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

from autoflow.application.workflows.executors.visual import GroupExecutor, NoteExecutor
from autoflow.domain.workflows.execution import ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b3_visual_harness.py")


@pytest.mark.parametrize(
    ("module_type", "executor_type"),
    [("group", GroupExecutor), ("note", NoteExecutor)],
)
def test_visual_noop_executor_matches_frozen(
    module_type: str, executor_type: type[GroupExecutor | NoteExecutor]
) -> None:
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", str(FROZEN_HARNESS)],
        input=json.dumps({"type": module_type}),
        text=True, encoding="utf-8",
        capture_output=True,
        check=True,
        env={"PYTHONPATH": str(FROZEN_BACKEND)},
    )
    source = json.loads(completed.stdout.splitlines()[-1])
    result = asyncio.run(executor_type().execute({}, ExecutionContext()))

    assert {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
    } == source
