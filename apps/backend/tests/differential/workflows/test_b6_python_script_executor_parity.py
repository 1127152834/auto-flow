from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from autoflow.application.workflows.executors.python_script import (
    PythonScriptExecutor,
)
from autoflow.domain.workflows.execution import ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b6_python_script_harness.py")


def _source(payload: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
        env={"PYTHONPATH": str(FROZEN_BACKEND)},
    )
    return json.loads(completed.stdout.splitlines()[-1])


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, str) and "Traceback (most recent call last)" in value:
        return re.sub(r'File "[^"]+\.py", line \d+', 'File "<script>", line N', value)
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "script",
    [
        'print("hello")\nvars.count += 1\nreturn vars.count',
        'raise ValueError("bad-script")',
    ],
)
async def test_python_content_matches_frozen_source(script: str) -> None:
    payload: dict[str, Any] = {
        "config": {
            "scriptMode": "content",
            "scriptContent": script,
            "useBuiltinPython": False,
            "timeout": 5,
            "resultVariable": "answer",
            "stdoutVariable": "stdout",
            "stderrVariable": "stderr",
            "returnCodeVariable": "code",
        },
        "variables": {"count": 1},
    }
    target_config = dict(payload["config"])
    target_config["pythonPath"] = sys.executable
    context = ExecutionContext(variables={"count": 1})
    target = await PythonScriptExecutor().execute(target_config, context)

    assert _normalize({
        "result": {
            "success": target.success,
            "message": target.message,
            "data": target.data,
            "error": target.error,
            "branch": target.branch,
            "skipped": target.skipped,
        },
        "variables": context.variables,
    }) == _normalize(_source(payload))
