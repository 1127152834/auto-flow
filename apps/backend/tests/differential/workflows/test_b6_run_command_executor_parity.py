from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from autoflow.application.workflows.executors.run_command import RunCommandExecutor
from autoflow.domain.workflows.execution import ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b6_run_command_harness.py")


def _source(payload: dict[str, Any], fake_bin: Path) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(FROZEN_BACKEND)
    environment["PATH"] = os.pathsep.join((str(fake_bin), environment.get("PATH", "")))
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
        env=environment,
    )
    return json.loads(completed.stdout.splitlines()[-1])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command",
    ["printf hello", "printf boom >&2; exit 7"],
)
async def test_posix_cmd_adaptation_matches_frozen_cmd_semantics(
    tmp_path: Path, command: str
) -> None:
    fake_cmd = tmp_path / "cmd"
    fake_cmd.write_text(
        '#!/bin/sh\n[ "$1" = /c ] && shift\nexec /bin/sh -c "$1"\n',
        encoding="utf-8",
    )
    fake_cmd.chmod(0o755)
    payload: dict[str, Any] = {
        "config": {
            "command": command,
            "shell": "cmd",
            "timeout": 5,
            "variableName": "output",
        },
        "variables": {},
    }
    context = ExecutionContext()
    target = await RunCommandExecutor().execute(payload["config"], context)

    assert {
        "result": {
            "success": target.success,
            "message": target.message,
            "data": target.data,
            "error": target.error,
            "branch": target.branch,
            "skipped": target.skipped,
        },
        "variables": context.variables,
    } == _source(payload, tmp_path)
