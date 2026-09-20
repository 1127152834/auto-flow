from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from autoflow.application.workflows.executors.type_utils import (
    parse_search_region,
    to_bool,
    to_float,
    to_int,
)
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.domain.workflows.variables import VariableManager

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference/WebRPA/backend"


def _frozen_resolve(variables: dict[str, Any], value: Any) -> Any:
    script = """
import json, sys
from app.executors.base import ExecutionContext
payload = json.load(sys.stdin)
result = ExecutionContext(variables=payload['variables']).resolve_value(payload['value'])
json.dump(result, sys.stdout, ensure_ascii=False)
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(FROZEN_BACKEND)
    process = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", script],
        input=json.dumps({"variables": variables, "value": value}, ensure_ascii=False),
        text=True, encoding="utf-8",
        capture_output=True,
        env=env,
        check=True,
    )
    return json.loads(process.stdout.splitlines()[-1])


@pytest.mark.parametrize(
    "value",
    [
        "你好，{name}",
        "${data[0][value]}",
        "{data[{index}][value]}",
        "空值={empty}",
        "{missing}",
        {"selector": "#{name}", "values": ["{data[1][value]}", "${enabled}"]},
    ],
)
def test_execution_context_resolution_matches_frozen_webrpa(value: Any) -> None:
    variables = {
        "name": "目标",
        "data": [{"value": 3}, {"value": 5}],
        "index": 0,
        "empty": None,
        "enabled": True,
    }
    context = ExecutionContext(variables=variables)

    assert context.resolve_value(value) == _frozen_resolve(variables, value)


def test_execution_context_get_variable_accepts_both_reference_forms() -> None:
    context = ExecutionContext(variables={"name": "WebRPA"})

    assert context.get_variable("{name}") == "WebRPA"
    assert context.get_variable("${name}") == "WebRPA"
    assert context.get_variable("missing", "默认") == "默认"


def test_variable_manager_scope_and_safe_numeric_expression_match_source() -> None:
    manager = VariableManager()
    manager.set("count", 2)
    manager.set("name", "外层")
    manager.push_scope()
    manager.set("name", "内层", scope="local")

    assert manager.get_all() == {"count": 2, "name": "内层"}
    assert manager.evaluate_expression("{count} * (3 + 1)") == 8
    assert manager.evaluate_expression("__import__('os')") == "__import__('os')"

    manager.pop_scope()
    assert manager.get("name") == "外层"


def test_credential_resolution_uses_injected_port_and_preserves_missing_reference() -> None:
    class Credentials:
        def get_field(self, name: str, field: str) -> Any | None:
            return {("登录", "用户名"): "user@example.test"}.get((name, field))

    context = ExecutionContext(variables={}, credentials=Credentials())

    assert context.resolve_value("{{凭据:登录.用户名}}") == "user@example.test"
    assert context.resolve_value("{{cred:登录.密码}}") == "{{cred:登录.密码}}"


@pytest.mark.parametrize(
    "converter,value,default,expected",
    [
        (to_int, "{number}", 9, 3),
        (to_int, "", 9, 9),
        (to_float, "{decimal}", 9.0, 2.5),
        (to_float, "bad", 9.0, 9.0),
        (to_bool, "{enabled}", False, True),
        (to_bool, "", True, True),
        (to_bool, "disabled", True, False),
    ],
)
def test_executor_type_conversion_keeps_frozen_argument_and_default_semantics(
    converter: Any, value: Any, default: Any, expected: Any
) -> None:
    context = ExecutionContext(
        variables={"number": "3.8", "decimal": "2.5", "enabled": "enabled"}
    )

    assert converter(value, default, context) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ({"x": 10, "y": 20, "x2": 2, "y2": 5}, (2, 5, 8, 15)),
        ({"x": 2, "y": 5, "width": 8, "height": 15}, (2, 5, 8, 15)),
        ({}, (0, 0, 0, 0)),
    ],
)
def test_search_region_parity(
    value: dict[str, Any], expected: tuple[int, int, int, int]
) -> None:
    assert parse_search_region(value) == expected
