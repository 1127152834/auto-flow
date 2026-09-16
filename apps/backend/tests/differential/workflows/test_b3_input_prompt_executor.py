from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from autoflow.application.workflows.executors.input_prompt import InputPromptExecutor
from autoflow.domain.workflows.execution import ExecutionContext, InputPromptRequest

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b3_input_prompt_harness.py")


class FakePrompts:
    def __init__(self, response: str | None) -> None:
        self.response = response
        self.requests: list[tuple[InputPromptRequest, float]] = []

    async def request_input(
        self, request: InputPromptRequest, *, timeout_seconds: float
    ) -> str | None:
        self.requests.append((request, timeout_seconds))
        return self.response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "wire_value", "expected"),
    [
        ("single", "原文", "原文"),
        ("number", "2.5", 2.5),
        ("integer", "2", 2),
        ("checkbox", "false", False),
        ("slider_int", "2.9", 2),
        ("slider_float", "2.5", 2.5),
        ("list", " 甲\n\n乙 ", ["甲", "乙"]),
        ("select_multiple", json.dumps(["甲", "乙"]), ["甲", "乙"]),
    ],
)
async def test_input_prompt_converts_source_wire_modes(
    mode: str, wire_value: str, expected: Any
) -> None:
    prompts = FakePrompts(wire_value)
    context = ExecutionContext(variables={"answer": "before"}, input_prompts=prompts)

    result = await InputPromptExecutor().execute(
        {
            "variableName": "answer",
            "inputMode": mode,
            "promptTitle": "输入",
            "promptMessage": "请输入",
            "timeout": 2.5,
        },
        context,
    )

    assert result.success is True
    assert context.variables["answer"] == expected
    assert prompts.requests[0][1] == 2.5


@pytest.mark.asyncio
async def test_input_prompt_preserves_cancelled_value_and_resolves_options() -> None:
    prompts = FakePrompts(None)
    context = ExecutionContext(
        variables={"answer": "before", "options": [{"name": "甲"}, ["乙"]]},
        input_prompts=prompts,
    )

    result = await InputPromptExecutor().execute(
        {
            "variableName": "answer",
            "inputMode": "select_multiple",
            "selectOptions": "{options}",
            "required": "false",
            "timeout": 0,
        },
        context,
    )

    assert result.success is True
    assert result.data == {"cancelled": True, "timeout": False}
    assert context.variables["answer"] == "before"
    request, timeout = prompts.requests[0]
    assert request.select_options == ('{"name": "甲"}', "['乙']")
    assert request.required is False
    assert timeout == 0


@pytest.mark.asyncio
async def test_input_prompt_requires_transport_and_variable_name() -> None:
    missing_name = await InputPromptExecutor().execute({}, ExecutionContext())
    missing_transport = await InputPromptExecutor().execute(
        {"variableName": "answer"}, ExecutionContext()
    )

    assert missing_name.error == "变量名不能为空"
    assert missing_transport.error == "输入请求服务不可用"


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
    ("mode", "response"),
    [
        ("single", "原文"),
        ("password", "secret"),
        ("number", "2.5"),
        ("integer", "2"),
        ("checkbox", "false"),
        ("slider_int", "2.9"),
        ("slider_float", "2.5"),
        ("list", "甲\n乙"),
        ("file", "/tmp/a.txt"),
        ("folder", "/tmp"),
        ("select_single", "甲"),
        ("select_multiple", '["甲","乙"]'),
    ],
)
async def test_input_prompt_result_and_variable_changes_match_frozen_source(
    mode: str, response: str
) -> None:
    payload = {
        "config": {
            "variableName": "answer",
            "inputMode": mode,
            "promptTitle": "输入",
            "promptMessage": "请输入",
            "defaultValue": "默认",
            "timeout": 2.5,
        },
        "variables": {"answer": "before"},
        "response": response,
    }
    prompts = FakePrompts(response)
    context = ExecutionContext(
        variables=payload["variables"].copy(), input_prompts=prompts
    )
    target = await InputPromptExecutor().execute(payload["config"], context)

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
    } == {"result": source["result"], "variables": source["variables"]}
