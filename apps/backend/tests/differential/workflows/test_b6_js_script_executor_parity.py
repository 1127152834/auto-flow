from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from autoflow.application.workflows.executors.js_script import JsScriptExecutor
from autoflow.domain.workflows.execution import ExecutionContext, JsScriptResult

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b6_js_script_harness.py")


class ScriptGateway:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    async def request_script(
        self,
        _code: str,
        _variables: Mapping[str, Any],
        *,
        timeout_seconds: float,
    ) -> JsScriptResult:
        assert timeout_seconds == 30
        return JsScriptResult(
            bool(self.response.get("success")),
            result=self.response.get("result"),
            variables=self.response.get("variables"),
            error=self.response.get("error"),
        )


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {
            "success": True,
            "result": {"value": 2},
            "variables": {"count": 2, "notDeclared": 99},
        },
        {"success": False, "error": "脚本错误"},
    ],
)
async def test_js_script_result_and_variable_changes_match_frozen_source(
    response: dict[str, Any],
) -> None:
    payload = {
        "config": {
            "code": "function main(vars){vars.count++;return vars.count}",
            "resultVariable": "answer",
        },
        "variables": {"count": 1},
        "response": response,
    }
    context = ExecutionContext(
        variables=payload["variables"].copy(),
        browser_scripts=ScriptGateway(response),
    )
    target = await JsScriptExecutor().execute(payload["config"], context)

    source = _source(payload)
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
    } == source
