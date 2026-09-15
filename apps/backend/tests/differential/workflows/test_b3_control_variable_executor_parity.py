from __future__ import annotations

import asyncio
import importlib
import json
import random
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from autoflow.domain.workflows.execution import (
    BinaryOutputSnapshot,
    ExecutionContext,
    WorkflowClock,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b3_control_variable_harness.py")

CLASS_NAMES = (
    "ConditionExecutor",
    "LoopExecutor",
    "ForeachExecutor",
    "InfiniteLoopExecutor",
    "ForeachDictExecutor",
    "BreakLoopExecutor",
    "ContinueLoopExecutor",
    "SetVariableExecutor",
    "IncrementDecrementExecutor",
    "JsonParseExecutor",
    "Base64Executor",
    "RandomNumberExecutor",
    "GetTimeExecutor",
    "WaitExecutor",
    "StopWorkflowExecutor",
    "AssertCheckpointExecutor",
)

EXPECTED_TYPES = {
    "condition",
    "loop",
    "foreach",
    "infinite_loop",
    "foreach_dict",
    "break_loop",
    "continue_loop",
    "set_variable",
    "increment_decrement",
    "json_parse",
    "base64",
    "random_number",
    "get_time",
    "wait",
    "stop_workflow",
    "assert_checkpoint",
}


class _Locator:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state

    @property
    def first(self) -> _Locator:
        return self

    async def count(self) -> int:
        return self.state.get("count", 1)

    async def is_visible(self) -> bool:
        return self.state.get("visible", True)

    async def inner_text(self) -> str:
        return self.state.get("text", "")

    async def wait_for(self, **_options: Any) -> None:
        return None


class _Page:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state

    def locator(self, _selector: str) -> _Locator:
        return _Locator(self.state)

    async def wait_for_load_state(self, _state: str, **_options: Any) -> None:
        return None


class _Browser:
    def __init__(self, state: dict[str, Any]) -> None:
        self.page = _Page(state)

    def active_page(self) -> _Page:
        return self.page


class _Artifacts:
    async def read_binary_output(
        self, *, output_path: str, max_bytes: int
    ) -> BinaryOutputSnapshot:
        path = Path(output_path)
        if not path.exists():
            return BinaryOutputSnapshot(content=None, identity="missing")
        content = path.read_bytes()
        if len(content) > max_bytes:
            raise ValueError("文件过大")
        return BinaryOutputSnapshot(content=content, identity="test")

    async def write_binary_output(
        self,
        *,
        output_path: str,
        content: bytes,
        mime_type: str,
        expected_identity: str | None = None,
    ) -> str:
        del mime_type, expected_identity
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)


def _target_executors() -> dict[str, type[Any]]:
    try:
        module = importlib.import_module(
            "autoflow.application.workflows.executors.control_variable"
        )
        classes = [getattr(module, name) for name in CLASS_NAMES]
    except (ImportError, AttributeError) as error:
        pytest.fail(f"B3 control/variable executors have not been migrated: {error}")
    return {executor().module_type: executor for executor in classes}


def _source(payload: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
        env={"PYTHONPATH": str(FROZEN_BACKEND)},
    )
    return json.loads(completed.stdout.splitlines()[-1])


def _result(result: Any) -> dict[str, Any]:
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "branch": result.branch,
        "skipped": result.skipped,
    }


async def _target(payload: dict[str, Any]) -> dict[str, Any]:
    context = ExecutionContext(
        variables=payload.get("variables", {}).copy(),
        loop_stack=payload.get("loop_stack", []).copy(),
        browser=_Browser(payload["page"]) if "page" in payload else None,  # type: ignore[arg-type]
        artifacts=_Artifacts(),  # type: ignore[arg-type]
    )
    random.seed(payload.get("seed", 0))
    executor = _target_executors()[payload["type"]]()
    result = await executor.execute(payload["config"], context)
    snapshot = {
        "result": _result(result),
        "variables": context.variables,
        "loop_stack": context.loop_stack,
    }
    return json.loads(json.dumps(snapshot, ensure_ascii=False))


CASES = [
    {
        "type": "condition",
        "config": {"leftValue": "10", "operator": ">", "rightValue": "2"},
    },
    {
        "type": "condition",
        "config": {
            "conditionType": "logic",
            "logicOperator": "and",
            "condition1": "{yes}",
            "condition2": "{items}",
        },
        "variables": {"yes": "true", "items": [1]},
    },
    {
        "type": "condition",
        "config": {"leftValue": "x", "operator": "?", "rightValue": "y"},
    },
    {
        "type": "condition",
        "config": {"conditionType": "element_visible", "leftValue": "#item"},
        "page": {"count": 1, "visible": False},
    },
    {"type": "loop", "config": {"loopCount": "3", "indexVariable": "i"}},
    {
        "type": "loop",
        "config": {
            "loopType": "range",
            "startValue": 5,
            "endValue": 1,
            "step": -2,
            "indexVariable": "i",
        },
    },
    {
        "type": "foreach",
        "config": {
            "listVariable": "items",
            "itemVariable": "entry",
            "indexVariable": "i",
        },
        "variables": {"items": ["a", "b"]},
    },
    {"type": "foreach", "config": {"dataSource": "value"}, "variables": {"value": 7}},
    {"type": "infinite_loop", "config": {}},
    {
        "type": "foreach_dict",
        "config": {"dictVariable": "record", "keyVariable": "k", "valueVariable": "v"},
        "variables": {"record": {"a": 1, "b": 2}},
    },
    {
        "type": "foreach_dict",
        "config": {"dictVariable": "record"},
        "variables": {"record": []},
    },
    {"type": "break_loop", "config": {}},
    {"type": "break_loop", "config": {}, "loop_stack": [{"type": "count"}]},
    {"type": "continue_loop", "config": {}, "loop_stack": [{"type": "count"}]},
    {
        "type": "set_variable",
        "config": {"variableName": "answer", "variableValue": "{x} * 2 + 1"},
        "variables": {"x": 4},
    },
    {"type": "set_variable", "config": {"variableValue": "1"}},
    {
        "type": "increment_decrement",
        "config": {"variableName": "n", "operation": "decrement", "step": "1.5"},
        "variables": {"n": "4.5"},
    },
    {"type": "increment_decrement", "config": {"variableName": "n", "step": "bad"}},
    {
        "type": "json_parse",
        "config": {
            "sourceVariable": "payload",
            "jsonPath": "$.items[1].name",
            "variableName": "name",
            "columnName": "col",
        },
        "variables": {"payload": '{"items":[{"name":"a"},{"name":"b"}]}'},
    },
    {"type": "json_parse", "config": {"sourceVariable": "missing", "jsonPath": "$.x"}},
    {
        "type": "base64",
        "config": {
            "operation": "encode",
            "inputText": "你好",
            "variableName": "encoded",
        },
    },
    {
        "type": "base64",
        "config": {
            "operation": "decode",
            "inputBase64": "data:text/plain;base64,aGVsbG8=",
            "variableName": "decoded",
        },
    },
    {"type": "base64", "config": {"operation": "unknown"}},
    {
        "type": "random_number",
        "config": {
            "variableName": "pick",
            "randomType": "integer",
            "minValue": 7,
            "maxValue": 7,
        },
    },
    {"type": "random_number", "config": {"randomType": "integer"}},
    {"type": "get_time", "config": {}},
    {"type": "wait", "config": {"duration": 0}},
    {"type": "wait", "config": {"waitType": "unknown"}},
    {
        "type": "wait",
        "config": {"waitType": "selector", "selector": "#item", "state": "hidden"},
        "page": {},
    },
    {"type": "wait", "config": {"waitType": "navigation"}, "page": {}},
    {"type": "stop_workflow", "config": {"stopReason": "done"}},
    {
        "type": "assert_checkpoint",
        "config": {
            "checkType": "variable",
            "actualValue": "{n}",
            "operator": ">=",
            "expectedValue": "1,000",
            "variableName": "passed",
        },
        "variables": {"n": 1200},
    },
    {
        "type": "assert_checkpoint",
        "config": {
            "checkType": "expression",
            "expression": "0",
            "onFail": "continue",
            "message": "must be truthy",
        },
    },
    {"type": "assert_checkpoint", "config": {"checkType": "unknown"}},
    {
        "type": "assert_checkpoint",
        "config": {
            "checkType": "element",
            "selector": "#item",
            "elementCheck": "text_contains",
            "expectedText": "target",
        },
        "page": {"text": "the target value"},
    },
]


@pytest.mark.parametrize("payload", CASES, ids=lambda case: case["type"])
def test_control_and_variable_results_match_frozen(payload: dict[str, Any]) -> None:
    source = _source(payload)
    target = asyncio.run(_target(payload))

    assert target == {key: source[key] for key in target}


def test_source_and_target_cover_the_approved_family() -> None:
    assert set(_source({"operation": "types"})["types"]) == EXPECTED_TYPES
    assert set(_target_executors()) == EXPECTED_TYPES


def test_base64_file_modes_match_frozen(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.txt"
    source_file.write_text("你好 file", encoding="utf-8")
    encode_payload = {
        "type": "base64",
        "config": {
            "operation": "file_to_base64",
            "filePath": str(source_file),
            "variableName": "encoded",
        },
    }
    assert asyncio.run(_target(encode_payload)) == {
        key: value for key, value in _source(encode_payload).items() if key != "signals"
    }

    output_directory = tmp_path / "decoded"
    decode_payload = {
        "type": "base64",
        "config": {
            "operation": "base64_to_file",
            "inputBase64": "aGVsbG8=",
            "outputPath": str(output_directory),
            "fileName": "out.txt",
            "variableName": "saved",
        },
    }
    assert asyncio.run(_target(decode_payload)) == {
        key: value for key, value in _source(decode_payload).items() if key != "signals"
    }
    assert (output_directory / "out.txt").read_bytes() == b"hello"


@pytest.mark.parametrize(
    ("time_format", "custom_format"),
    [
        ("datetime", ""),
        ("date", ""),
        ("time", ""),
        ("timestamp", ""),
        ("custom", "%d/%m/%Y"),
        ("iso8601", ""),
        ("iso8601_utc", ""),
    ],
)
def test_get_time_uses_the_execution_clock_with_frozen_formats(
    time_format: str, custom_format: str
) -> None:
    fixed = datetime(2026, 9, 16, 12, 34, 56, tzinfo=UTC)
    local_now = fixed.astimezone().replace(tzinfo=None)
    expected: dict[str, object] = {
        "datetime": local_now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": local_now.strftime("%Y-%m-%d"),
        "time": local_now.strftime("%H:%M:%S"),
        "timestamp": int(local_now.timestamp() * 1000),
        "custom": local_now.strftime(custom_format),
        "iso8601": local_now.isoformat(),
        "iso8601_utc": local_now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }
    context = ExecutionContext(clock=WorkflowClock(now=lambda: fixed))
    executor = _target_executors()["get_time"]()

    result = asyncio.run(
        executor.execute(
            {
                "timeFormat": time_format,
                "customFormat": custom_format,
                "variableName": "now",
            },
            context,
        )
    )

    assert result.success is True
    assert result.data == {"value": expected[time_format]}
    assert context.variables["now"] == expected[time_format]


def test_frozen_control_signals_document_the_runtime_interface_gap() -> None:
    assert (
        _source({"type": "break_loop", "config": {}, "loop_stack": [{}]})["signals"][
            "break"
        ]
        is True
    )
    assert (
        _source({"type": "continue_loop", "config": {}, "loop_stack": [{}]})["signals"][
            "continue"
        ]
        is True
    )
    assert _source({"type": "stop_workflow", "config": {"stopReason": "done"}})[
        "signals"
    ] == {
        "break": False,
        "continue": False,
        "stop": True,
        "reason": "done",
    }


@pytest.mark.parametrize(
    ("module_type", "attribute", "expected"),
    [
        ("break_loop", "should_break", True),
        ("continue_loop", "should_continue", True),
        ("stop_workflow", "stop_workflow", True),
    ],
)
def test_control_executor_applies_the_frozen_runtime_signal(
    module_type: str, attribute: str, expected: bool
) -> None:
    context = ExecutionContext(loop_stack=[{}])

    asyncio.run(
        _target_executors()[module_type]().execute(
            {"stopReason": "done"} if module_type == "stop_workflow" else {},
            context,
        )
    )

    assert getattr(context, attribute) is expected
    if module_type == "stop_workflow":
        assert context.stop_reason == "done"
