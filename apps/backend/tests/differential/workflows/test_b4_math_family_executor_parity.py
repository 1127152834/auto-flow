from __future__ import annotations

import asyncio
import copy
import importlib
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_worker import _ThreadCancellation

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_math_family_harness.py")

CLASS_NAMES = {
    "math_list_ops": (
        "ListSumExecutor",
        "ListAverageExecutor",
        "ListMaxExecutor",
        "ListMinExecutor",
        "ListSortExecutor",
        "ListUniqueExecutor",
        "ListSliceExecutor",
        "MathRoundExecutor",
        "MathBaseConvertExecutor",
        "MathFloorExecutor",
        "MathModuloExecutor",
        "MathAbsExecutor",
        "MathSqrtExecutor",
        "MathPowerExecutor",
    ),
    "math_advanced": (
        "MathLogExecutor",
        "MathTrigExecutor",
        "MathExpExecutor",
        "MathGcdExecutor",
        "MathLcmExecutor",
        "MathFactorialExecutor",
        "MathPermutationExecutor",
        "MathPercentageExecutor",
        "MathClampExecutor",
        "MathRandomAdvancedExecutor",
    ),
    "statistics": (
        "MedianExecutor",
        "ModeExecutor",
        "VarianceExecutor",
        "StdevExecutor",
        "PercentileExecutor",
        "NormalizeExecutor",
        "StandardizeExecutor",
    ),
}


def _target_executors() -> dict[str, type[Any]]:
    executors: dict[str, type[Any]] = {}
    try:
        for module_name, class_names in CLASS_NAMES.items():
            module = importlib.import_module(
                f"autoflow.application.workflows.executors.{module_name}"
            )
            for class_name in class_names:
                executor = getattr(module, class_name)
                executors[executor().module_type] = executor
    except (ImportError, AttributeError) as error:
        pytest.fail(f"math family production executor is missing: {error}")
    return executors


def _normalize(value: Any) -> Any:
    if isinstance(value, complex):
        return {
            "__type__": "complex",
            "real": _normalize(value.real),
            "imag": _normalize(value.imag),
        }
    if isinstance(value, float) and not math.isfinite(value):
        return {
            "__type__": "float",
            "value": "nan" if math.isnan(value) else ("inf" if value > 0 else "-inf"),
        }
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _source_result(payload: dict[str, Any]) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(FROZEN_BACKEND)
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout.splitlines()[-1])


async def _target_result(payload: dict[str, Any]) -> dict[str, Any]:
    random.seed(payload.get("seed", 8675309))
    context = ExecutionContext(variables=copy.deepcopy(payload.get("variables", {})))
    executor = _target_executors()[payload["type"]]()
    result = await executor.execute(copy.deepcopy(payload["config"]), context)
    return _normalize(
        {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "error": result.error,
            "branch": result.branch,
            "variables": context.variables,
        }
    )


VALID_CASES: list[dict[str, Any]] = [
    {
        "type": "list_sum",
        "variables": {"items": [1, "2.5", -3]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_average",
        "variables": {"items": [1, 2, 6]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_max",
        "variables": {"items": [1, "9.5", -2]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_min",
        "variables": {"items": [1, "-9.5", 2]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_sort",
        "variables": {"items": [3, 1, 2]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_unique",
        "variables": {"items": [1, 1, "1", {"a": 1}, {"a": 1}]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_slice",
        "variables": {"items": [0, 1, 2, 3]},
        "config": {
            "listVariable": "items",
            "startIndex": 1,
            "endIndex": 3,
            "resultVariable": "out",
        },
    },
    {
        "type": "math_round",
        "config": {"value": "2.5", "decimals": 0, "resultVariable": "out"},
    },
    {
        "type": "math_base_convert",
        "config": {
            "value": "FF",
            "fromBase": 16,
            "toBase": 10,
            "resultVariable": "out",
        },
    },
    {"type": "math_floor", "config": {"value": "-1.2", "resultVariable": "out"}},
    {
        "type": "math_modulo",
        "config": {"dividend": -7, "divisor": 3, "resultVariable": "out"},
    },
    {"type": "math_abs", "config": {"value": -3.5, "resultVariable": "out"}},
    {"type": "math_sqrt", "config": {"value": 81, "root": 2, "resultVariable": "out"}},
    {
        "type": "math_power",
        "config": {"base": 2, "exponent": 10, "resultVariable": "out"},
    },
    {"type": "math_log", "config": {"value": 8, "base": "2", "resultVariable": "out"}},
    {
        "type": "math_trig",
        "config": {
            "value": 30,
            "function": "sin",
            "unit": "degree",
            "resultVariable": "out",
        },
    },
    {"type": "math_exp", "config": {"value": 2, "resultVariable": "out"}},
    {
        "type": "math_gcd",
        "config": {"value1": 12, "value2": 18, "resultVariable": "out"},
    },
    {
        "type": "math_lcm",
        "config": {"value1": 12, "value2": 18, "resultVariable": "out"},
    },
    {"type": "math_factorial", "config": {"value": 5, "resultVariable": "out"}},
    {
        "type": "math_permutation",
        "config": {"n": 5, "r": 2, "calcType": "permutation", "resultVariable": "out"},
    },
    {
        "type": "math_percentage",
        "config": {
            "operation": "increase",
            "value1": 100,
            "value2": 15,
            "resultVariable": "out",
        },
    },
    {
        "type": "math_clamp",
        "config": {"value": 12, "min": 0, "max": 10, "resultVariable": "out"},
    },
    {
        "type": "math_random_advanced",
        "seed": 17,
        "config": {"type": "uniform", "min": 1, "max": 2, "resultVariable": "out"},
    },
    {
        "type": "stat_median",
        "variables": {"items": [1, 9, 3]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "stat_mode",
        "variables": {"items": [1, 2, 2, 3]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "stat_variance",
        "variables": {"items": [1, 2, 3]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "stat_stdev",
        "variables": {"items": [1, 2, 3]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "stat_percentile",
        "variables": {"items": [1, 2, 3, 4]},
        "config": {"listVariable": "items", "percentile": 50, "resultVariable": "out"},
    },
    {
        "type": "stat_normalize",
        "variables": {"items": [2, 4, 6]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "stat_standardize",
        "variables": {"items": [2, 4, 6]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
]


BRANCH_CASES: list[dict[str, Any]] = [
    {
        "type": "list_sum",
        "variables": {"items": []},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_sum",
        "variables": {"items": [1, "bad"]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_average",
        "variables": {"items": [True, False]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_max",
        "variables": {"items": "bad"},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_min",
        "config": {"listVariable": "missing", "resultVariable": "out"},
    },
    {
        "type": "list_sort",
        "variables": {"items": [3, 1, 2]},
        "config": {
            "listVariable": "items",
            "sortOrder": "desc",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_sort",
        "variables": {"items": [1, "2"]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_unique",
        "variables": {"items": [{"a": 1}, "{'a': 1}"]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_slice",
        "variables": {"items": [0, 1, 2, 3]},
        "config": {"listVariable": "items", "startIndex": -2, "resultVariable": "out"},
    },
    {
        "type": "list_slice",
        "variables": {"items": [0, 1]},
        "config": {
            "listVariable": "items",
            "startIndex": "bad",
            "resultVariable": "out",
        },
    },
    {
        "type": "math_round",
        "config": {"numberValue": 3.14159, "decimals": 2, "resultVariable": "out"},
    },
    {"type": "math_round", "config": {"value": "bad", "resultVariable": "out"}},
    {
        "type": "math_base_convert",
        "config": {"value": -10, "fromBase": 10, "toBase": 2, "resultVariable": "out"},
    },
    {
        "type": "math_base_convert",
        "config": {"value": 35, "fromBase": 10, "toBase": 36, "resultVariable": "out"},
    },
    {
        "type": "math_base_convert",
        "config": {"value": 0, "fromBase": 10, "toBase": 3, "resultVariable": "out"},
    },
    {
        "type": "math_base_convert",
        "config": {"value": 10, "fromBase": 1, "toBase": 10, "resultVariable": "out"},
    },
    {
        "type": "math_base_convert",
        "config": {"value": "Z", "fromBase": 10, "toBase": 16, "resultVariable": "out"},
    },
    {"type": "math_floor", "config": {"numberValue": "bad", "resultVariable": "out"}},
    {
        "type": "math_modulo",
        "config": {"dividend": 1, "divisor": 0, "resultVariable": "out"},
    },
    {
        "type": "math_modulo",
        "config": {"dividend": "bad", "divisor": 2, "resultVariable": "out"},
    },
    {"type": "math_abs", "config": {"value": float("-inf"), "resultVariable": "out"}},
    {"type": "math_sqrt", "config": {"value": -8, "root": 2, "resultVariable": "out"}},
    {"type": "math_sqrt", "config": {"value": -8, "root": 3, "resultVariable": "out"}},
    {"type": "math_sqrt", "config": {"value": 8, "root": 0, "resultVariable": "out"}},
    {
        "type": "math_power",
        "config": {"base": -1, "exponent": 0.5, "resultVariable": "out"},
    },
    {
        "type": "math_power",
        "config": {"base": 10, "exponent": 10000, "resultVariable": "out"},
    },
    {
        "type": "math_log",
        "config": {"value": math.e, "base": "e", "resultVariable": "out"},
    },
    {
        "type": "math_log",
        "config": {"numberValue": 100, "logType": "log10", "resultVariable": "out"},
    },
    {
        "type": "math_log",
        "config": {
            "value": 8,
            "base": "custom",
            "customBase": 2,
            "resultVariable": "out",
        },
    },
    {
        "type": "math_log",
        "config": {
            "value": 8,
            "base": "custom",
            "customBase": 1,
            "resultVariable": "out",
        },
    },
    {"type": "math_log", "config": {"value": 0, "resultVariable": "out"}},
    {
        "type": "math_log",
        "config": {"value": 8, "logType": "bad", "resultVariable": "out"},
    },
    {
        "type": "math_trig",
        "config": {
            "value": math.pi,
            "function": "cos",
            "unit": "radian",
            "resultVariable": "out",
        },
    },
    {
        "type": "math_trig",
        "config": {
            "value": 45,
            "function": "tan",
            "unit": "degree",
            "resultVariable": "out",
        },
    },
    {
        "type": "math_trig",
        "config": {
            "value": 0.5,
            "function": "asin",
            "unit": "degree",
            "resultVariable": "out",
        },
    },
    {
        "type": "math_trig",
        "config": {
            "value": 0.5,
            "function": "acos",
            "unit": "radian",
            "resultVariable": "out",
        },
    },
    {
        "type": "math_trig",
        "config": {
            "value": 1,
            "function": "atan",
            "unit": "degree",
            "resultVariable": "out",
        },
    },
    {
        "type": "math_trig",
        "config": {"value": 2, "function": "asin", "resultVariable": "out"},
    },
    {
        "type": "math_trig",
        "config": {"value": 1, "function": "bad", "resultVariable": "out"},
    },
    {"type": "math_exp", "config": {"value": 10000, "resultVariable": "out"}},
    {"type": "math_exp", "config": {"value": "bad", "resultVariable": "out"}},
    {"type": "math_gcd", "config": {"numbers": "12,18,30", "resultVariable": "out"}},
    {"type": "math_gcd", "config": {"numbers": [7.9, 14.2], "resultVariable": "out"}},
    {"type": "math_gcd", "config": {"numbers": "5", "resultVariable": "out"}},
    {"type": "math_lcm", "config": {"numbers": "4,6,8", "resultVariable": "out"}},
    {"type": "math_lcm", "config": {"numbers": "0,0", "resultVariable": "out"}},
    {"type": "math_factorial", "config": {"value": 5.9, "resultVariable": "out"}},
    {"type": "math_factorial", "config": {"value": -1, "resultVariable": "out"}},
    {"type": "math_factorial", "config": {"value": 171, "resultVariable": "out"}},
    {
        "type": "math_permutation",
        "config": {"n": 5, "r": 2, "calcType": "combination", "resultVariable": "out"},
    },
    {"type": "math_permutation", "config": {"n": 2, "r": 3, "resultVariable": "out"}},
    {"type": "math_permutation", "config": {"n": -1, "r": 0, "resultVariable": "out"}},
    {
        "type": "math_permutation",
        "config": {"n": 4, "r": 2, "calcType": "bad", "resultVariable": "out"},
    },
    {
        "type": "math_percentage",
        "config": {
            "calcType": "percent_of",
            "value1": 25,
            "value2": 80,
            "resultVariable": "out",
        },
    },
    {
        "type": "math_percentage",
        "config": {
            "calcType": "what_percent",
            "value1": 25,
            "value2": 50,
            "resultVariable": "out",
        },
    },
    {
        "type": "math_percentage",
        "config": {
            "calcType": "percent_change",
            "value1": 120,
            "value2": 100,
            "resultVariable": "out",
        },
    },
    {
        "type": "math_percentage",
        "config": {
            "operation": "of",
            "value1": 10,
            "value2": 40,
            "resultVariable": "out",
        },
    },
    {
        "type": "math_percentage",
        "config": {
            "operation": "decrease",
            "value1": 100,
            "value2": 20,
            "resultVariable": "out",
        },
    },
    {
        "type": "math_percentage",
        "config": {
            "operation": "of",
            "value1": 1,
            "value2": 0,
            "resultVariable": "out",
        },
    },
    {
        "type": "math_clamp",
        "config": {"value": -2, "min": "0", "resultVariable": "out"},
    },
    {"type": "math_clamp", "config": {"value": 9, "max": "5", "resultVariable": "out"}},
    {
        "type": "math_clamp",
        "config": {"value": 2, "min": 3, "max": 1, "resultVariable": "out"},
    },
    {
        "type": "math_random_advanced",
        "seed": 19,
        "config": {
            "randomType": "int",
            "minValue": 1,
            "maxValue": 3,
            "count": 3,
            "resultVariable": "out",
        },
    },
    {
        "type": "math_random_advanced",
        "seed": 23,
        "config": {
            "randomType": "gauss",
            "mean": 10,
            "stddev": 2,
            "decimals": 2,
            "count": 2,
            "resultVariable": "out",
        },
    },
    {
        "type": "math_random_advanced",
        "seed": 29,
        "config": {
            "type": "exponential",
            "lambda": 2,
            "count": 2,
            "resultVariable": "out",
        },
    },
    {"type": "math_random_advanced", "config": {"count": 0, "resultVariable": "out"}},
    {
        "type": "math_random_advanced",
        "config": {"count": 10001, "resultVariable": "out"},
    },
    {
        "type": "math_random_advanced",
        "config": {"type": "normal", "stddev": -1, "resultVariable": "out"},
    },
    {
        "type": "math_random_advanced",
        "config": {"type": "exponential", "lambda": 0, "resultVariable": "out"},
    },
    {
        "type": "math_random_advanced",
        "config": {"type": "bad", "resultVariable": "out"},
    },
    {
        "type": "stat_median",
        "variables": {"items": ["1", 2, True, "bad"]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "stat_median",
        "variables": {"items": ["1"]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "stat_mode",
        "variables": {"items": [1, 2, 1, 2]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "stat_mode",
        "variables": {"items": [[1], [1]]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "stat_variance",
        "variables": {"items": [1]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "stat_variance",
        "variables": {"items": [1, "2"]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "stat_stdev",
        "variables": {"items": [5, 5, 5]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "stat_percentile",
        "variables": {"items": [1, 2, 3]},
        "config": {"listVariable": "items", "percentile": 0, "resultVariable": "out"},
    },
    {
        "type": "stat_percentile",
        "variables": {"items": [1, 2, 3]},
        "config": {"listVariable": "items", "percentile": 100, "resultVariable": "out"},
    },
    {
        "type": "stat_percentile",
        "variables": {"items": [1, 2, 3, 4]},
        "config": {
            "listVariable": "items",
            "percentile": 25.9,
            "resultVariable": "out",
        },
    },
    {
        "type": "stat_percentile",
        "variables": {"items": [1]},
        "config": {"listVariable": "items", "percentile": 50, "resultVariable": "out"},
    },
    {
        "type": "stat_percentile",
        "variables": {"items": [1, 2]},
        "config": {"listVariable": "items", "percentile": 101, "resultVariable": "out"},
    },
    {
        "type": "stat_normalize",
        "variables": {"items": [5, 5]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "stat_normalize",
        "variables": {"items": [1, 2, 3]},
        "config": {
            "listVariable": "items",
            "method": "custom",
            "newMin": 10,
            "newMax": -10,
            "resultVariable": "out",
        },
    },
    {
        "type": "stat_normalize",
        "variables": {"items": [1, 2]},
        "config": {
            "listVariable": "items",
            "method": "custom",
            "newMin": "bad",
            "resultVariable": "out",
        },
    },
    {
        "type": "stat_standardize",
        "variables": {"items": [5, 5, 5]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "stat_standardize",
        "variables": {"items": [1, "2"]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
]


def _without_result_variable(case: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(case)
    payload["config"].pop("resultVariable", None)
    return payload


def _without_required_input(case: dict[str, Any]) -> dict[str, Any]:
    return {"type": case["type"], "config": {"resultVariable": "out"}}


CASES = (
    VALID_CASES
    + [_without_result_variable(case) for case in VALID_CASES]
    + [_without_required_input(case) for case in VALID_CASES]
    + BRANCH_CASES
)

APPROVED_SOURCE_TYPES = {
    "list_sum",
    "list_average",
    "list_max",
    "list_min",
    "list_sort",
    "list_unique",
    "list_slice",
    "math_round",
    "math_base_convert",
    "math_floor",
    "math_modulo",
    "math_abs",
    "math_sqrt",
    "math_power",
    "math_log",
    "math_trig",
    "math_exp",
    "math_gcd",
    "math_lcm",
    "math_factorial",
    "math_permutation",
    "math_percentage",
    "math_clamp",
    "math_random_advanced",
    "stat_median",
    "stat_mode",
    "stat_variance",
    "stat_stdev",
    "stat_percentile",
    "stat_normalize",
    "stat_standardize",
}


@pytest.mark.parametrize(
    "payload",
    CASES,
    ids=[f"{case['type']}-{index}" for index, case in enumerate(CASES)],
)
def test_math_family_matches_frozen_webrpa(payload: dict[str, Any]) -> None:
    assert asyncio.run(_target_result(payload)) == _source_result(payload)


def test_frozen_source_files_have_all_approved_module_types() -> None:
    assert set(_source_result({"operation": "types"})["types"]) == APPROVED_SOURCE_TYPES


def test_target_files_have_all_approved_module_types() -> None:
    assert set(_target_executors()) == APPROVED_SOURCE_TYPES


@pytest.mark.parametrize("module_type", sorted(APPROVED_SOURCE_TYPES))
def test_math_family_never_requires_a_browser(module_type: str) -> None:
    assert _target_executors()[module_type]().requires_browser is False


@pytest.mark.parametrize(
    ("module_type", "variables", "config"),
    [
        (
            "list_sum",
            {"items": list(range(10_000))},
            {"listVariable": "items", "resultVariable": "out"},
        ),
        (
            "stat_normalize",
            {"items": list(range(10_000))},
            {"listVariable": "items", "resultVariable": "out"},
        ),
        (
            "math_random_advanced",
            {},
            {"count": 10_000, "resultVariable": "out"},
        ),
    ],
)
def test_large_math_operations_yield_and_cancel_before_writing_result(
    module_type: str,
    variables: dict[str, Any],
    config: dict[str, Any],
) -> None:
    async def cancel_operation() -> dict[str, Any]:
        stopped = Event()
        context = ExecutionContext(
            variables=variables,
            cancellation=_ThreadCancellation(stopped),
        )
        task = asyncio.create_task(
            _target_executors()[module_type]().execute(config, context)
        )
        await asyncio.sleep(0)
        stopped.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        return context.variables

    assert "out" not in asyncio.run(cancel_operation())


@pytest.mark.parametrize("calc_type", ["permutation", "combination"])
def test_permutation_rejects_unbounded_synchronous_work(calc_type: str) -> None:
    context = ExecutionContext()

    result = asyncio.run(
        _target_executors()["math_permutation"]().execute(
            {
                "n": 100_000,
                "r": 50_000,
                "calcType": calc_type,
                "resultVariable": "out",
            },
            context,
        )
    )

    assert result.success is False
    assert result.error == "计算规模超过工作流安全限制"
    assert "out" not in context.variables


def test_permutation_allows_a_result_at_the_4000_digit_boundary() -> None:
    context = ExecutionContext()

    result = asyncio.run(
        _target_executors()["math_permutation"]().execute(
            {
                "n": 1464,
                "r": 1460,
                "calcType": "permutation",
                "resultVariable": "out",
            },
            context,
        )
    )

    assert result.success is True
    assert len(str(result.data)) == 4_000
    assert context.variables["out"] == result.data


def test_complex_result_is_normalized_only_at_the_test_transport() -> None:
    context = ExecutionContext()
    result = asyncio.run(
        _target_executors()["math_power"]().execute(
            {"base": -1, "exponent": 0.5, "resultVariable": "out"}, context
        )
    )

    assert isinstance(result.data, complex)
    assert isinstance(context.variables["out"], complex)


def test_non_finite_result_is_normalized_only_at_the_test_transport() -> None:
    context = ExecutionContext()
    result = asyncio.run(
        _target_executors()["math_abs"]().execute(
            {"value": float("nan"), "resultVariable": "out"}, context
        )
    )

    assert math.isnan(result.data)
    assert math.isnan(context.variables["out"])
