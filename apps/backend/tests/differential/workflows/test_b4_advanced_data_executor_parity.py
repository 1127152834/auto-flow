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
FROZEN_HARNESS = Path(__file__).with_name("frozen_advanced_data_harness.py")

CLASS_NAMES = {
    "list_advanced": (
        "ListReverseExecutor",
        "ListFindExecutor",
        "ListCountExecutor",
        "ListFilterExecutor",
        "ListMapExecutor",
        "ListMergeExecutor",
        "ListFlattenExecutor",
        "ListChunkExecutor",
        "ListRemoveEmptyExecutor",
        "ListIntersectionExecutor",
        "ListUnionExecutor",
        "ListDifferenceExecutor",
        "ListCartesianProductExecutor",
        "ListShuffleExecutor",
        "ListSampleExecutor",
    ),
    "dict_advanced": (
        "DictMergeExecutor",
        "DictFilterExecutor",
        "DictMapValuesExecutor",
        "DictInvertExecutor",
        "DictSortExecutor",
        "DictDeepCopyExecutor",
        "DictGetPathExecutor",
        "DictFlattenExecutor",
    ),
    "string_convert": (
        "CsvParseExecutor",
        "CsvGenerateExecutor",
        "ListToStringAdvancedExecutor",
    ),
}

APPROVED_SOURCE_TYPES = {
    "list_reverse",
    "list_find",
    "list_count",
    "list_filter",
    "list_map",
    "list_merge",
    "list_flatten",
    "list_chunk",
    "list_remove_empty",
    "list_intersection",
    "list_union",
    "list_difference",
    "list_cartesian_product",
    "list_shuffle",
    "list_sample",
    "dict_merge",
    "dict_filter",
    "dict_map_values",
    "dict_invert",
    "dict_sort",
    "dict_deep_copy",
    "dict_get_path",
    "dict_flatten",
    "csv_parse",
    "csv_generate",
    "list_to_string_advanced",
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
        pytest.fail(f"advanced data production executor is missing: {error}")
    return executors


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


async def _target_result(payload: dict[str, Any]) -> dict[str, Any]:
    random.seed(payload.get("seed", 8675309))
    context = ExecutionContext(
        variables=json.loads(
            json.dumps(payload.get("variables", {}), ensure_ascii=False)
        )
    )
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


CASES: list[dict[str, Any]] = [
    {
        "type": "csv_parse",
        "config": {"csvContent": "name,age\nAda,36\nLinus,55", "resultVariable": "out"},
    },
    {
        "type": "csv_parse",
        "config": {
            "csvString": "a;b\n1;2",
            "delimiter": ";",
            "hasHeader": "false",
            "resultVariable": "out",
        },
    },
    {
        "type": "csv_parse",
        "variables": {"content": 'name,note\nAda,"x,y"', "sep": ",", "header": True},
        "config": {
            "csvContent": "{content}",
            "delimiter": "{sep}",
            "hasHeader": "{header}",
            "resultVariable": "out",
        },
    },
    {
        "type": "csv_parse",
        "config": {"csvContent": "only,header", "resultVariable": "out"},
    },
    {
        "type": "csv_parse",
        "config": {"csvContent": "a,b,c\n1,2\n3,4,5,6", "resultVariable": "out"},
    },
    {
        "type": "csv_parse",
        "config": {
            "csvString": "",
            "csvContent": "a,b\n1,2",
            "resultVariable": "out",
        },
    },
    {"type": "csv_parse", "config": {"csvContent": "\n", "resultVariable": "out"}},
    {"type": "csv_parse", "config": {"csvContent": "a,b"}},
    {
        "type": "csv_parse",
        "config": {"csvContent": "a,b", "delimiter": "::", "resultVariable": "out"},
    },
    {"type": "csv_parse", "config": {"csvContent": 123, "resultVariable": "out"}},
    {
        "type": "csv_generate",
        "variables": {
            "rows": [{"name": "Ada", "age": 36}, {"name": "Linus", "age": 55}]
        },
        "config": {"dataVariable": "rows", "resultVariable": "out"},
    },
    {
        "type": "csv_generate",
        "variables": {"rows": [{"a": 1, "b": None}, {"a": 2, "b": "x,y", "c": 3}]},
        "config": {
            "listVariable": "rows",
            "includeHeader": "false",
            "resultVariable": "out",
        },
    },
    {
        "type": "csv_generate",
        "variables": {"rows": [["a", "b"], [1, 2]]},
        "config": {"dataVariable": "{name}", "delimiter": ";", "resultVariable": "out"},
    },
    {
        "type": "csv_generate",
        "variables": {"name": "rows", "rows": ["a", 2, None]},
        "config": {"dataVariable": "{name}", "resultVariable": "out"},
    },
    {
        "type": "csv_generate",
        "variables": {"old": ["old"], "new": ["new"]},
        "config": {
            "listVariable": "old",
            "dataVariable": "new",
            "resultVariable": "out",
        },
    },
    {
        "type": "csv_generate",
        "variables": {"rows": [{"a": 1}, "bad"]},
        "config": {"dataVariable": "rows", "resultVariable": "out"},
    },
    {"type": "csv_generate", "config": {"dataVariable": "", "resultVariable": "out"}},
    {
        "type": "csv_generate",
        "config": {"dataVariable": "missing", "resultVariable": "out"},
    },
    {
        "type": "csv_generate",
        "variables": {"rows": "not-a-list"},
        "config": {"dataVariable": "rows", "resultVariable": "out"},
    },
    {
        "type": "csv_generate",
        "variables": {"rows": []},
        "config": {"dataVariable": "rows", "resultVariable": "out"},
    },
    {
        "type": "csv_generate",
        "variables": {"rows": [1]},
        "config": {"dataVariable": "rows"},
    },
    {
        "type": "csv_generate",
        "variables": {"rows": [1]},
        "config": {"dataVariable": "rows", "delimiter": "::", "resultVariable": "out"},
    },
    {
        "type": "list_to_string_advanced",
        "variables": {"items": ["a", 2, True]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_to_string_advanced",
        "variables": {"items": ["a", "b"]},
        "config": {
            "listVariable": "items",
            "formatTemplate": "{index}/{index1}:{item}",
            "separator": "|",
            "prefix": "[",
            "suffix": "]",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_to_string_advanced",
        "variables": {
            "name": "items",
            "items": [1, 2],
            "template": "#{index1}={item}",
            "sep": ";",
            "left": "<",
            "right": ">",
        },
        "config": {
            "listVariable": "{name}",
            "formatTemplate": "{template}",
            "separator": "{sep}",
            "prefix": "{left}",
            "suffix": "{right}",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_to_string_advanced",
        "variables": {"items": []},
        "config": {
            "listVariable": "items",
            "prefix": "<",
            "suffix": ">",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_to_string_advanced",
        "variables": {"items": ["{index}", "{index1}"]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_to_string_advanced",
        "config": {"listVariable": "", "resultVariable": "out"},
    },
    {
        "type": "list_to_string_advanced",
        "config": {"listVariable": "missing", "resultVariable": "out"},
    },
    {
        "type": "list_to_string_advanced",
        "variables": {"items": "not-a-list"},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_to_string_advanced",
        "variables": {"items": [1]},
        "config": {"listVariable": "items"},
    },
    {
        "type": "list_to_string_advanced",
        "variables": {"items": [1]},
        "config": {
            "listVariable": "items",
            "formatTemplate": 123,
            "resultVariable": "out",
        },
    },
    {
        "type": "list_to_string_advanced",
        "variables": {"items": [1, 2]},
        "config": {"listVariable": "items", "separator": 3, "resultVariable": "out"},
    },
]

CASES += [
    {
        "type": "list_reverse",
        "variables": {"items": [1, "a", None]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_reverse",
        "variables": {"items": "bad"},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_find",
        "variables": {"items": [1, "a", "a"]},
        "config": {
            "listVariable": "items",
            "searchValue": "a",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_find",
        "variables": {"items": [1, 2]},
        "config": {"listVariable": "items", "searchValue": 3, "resultVariable": "out"},
    },
    {
        "type": "list_count",
        "variables": {"items": [1, True, 1, "1"]},
        "config": {"listVariable": "items", "searchValue": 1, "resultVariable": "out"},
    },
    {
        "type": "list_filter",
        "variables": {"items": [1, 2, 3, 4]},
        "config": {
            "listVariable": "items",
            "condition": "x % 2 == 0",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_filter",
        "variables": {"items": ["alpha", "beta", 3]},
        "config": {
            "listVariable": "items",
            "condition": "x.startswith('a')",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_filter",
        "variables": {"items": [1]},
        "config": {
            "listVariable": "items",
            "condition": "x.__class__",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_filter",
        "variables": {"items": [1]},
        "config": {
            "listVariable": "items",
            "condition": "1 / 0",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_filter",
        "variables": {"items": [1, 2, "3", 4]},
        "config": {
            "listVariable": "items",
            "filterType": "greater",
            "compareValue": 2,
            "resultVariable": "out",
        },
    },
    {
        "type": "list_filter",
        "variables": {"items": ["ab", "bc", 2]},
        "config": {
            "listVariable": "items",
            "filterType": "contains",
            "compareValue": "b",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_filter",
        "variables": {"items": [1]},
        "config": {
            "listVariable": "items",
            "filterType": "less",
            "compareValue": "bad",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_map",
        "variables": {"items": [1, 2, 3]},
        "config": {
            "listVariable": "items",
            "expression": "x * 2 + 1",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_map",
        "variables": {"items": [-1.25, 2.36]},
        "config": {
            "listVariable": "items",
            "expression": "round(abs(x), 1)",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_map",
        "variables": {"items": [" a ", "b"]},
        "config": {
            "listVariable": "items",
            "expression": "x.strip().upper()",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_map",
        "variables": {"items": [1]},
        "config": {
            "listVariable": "items",
            "expression": "open('x')",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_map",
        "variables": {"items": [0]},
        "config": {
            "listVariable": "items",
            "expression": "1 / x",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_map",
        "variables": {"items": [2, "3", "bad"]},
        "config": {
            "listVariable": "items",
            "operation": "power",
            "operand": 2,
            "resultVariable": "out",
        },
    },
    {
        "type": "list_map",
        "variables": {"items": [-1]},
        "config": {
            "listVariable": "items",
            "operation": "power",
            "operand": 0.5,
            "resultVariable": "out",
        },
    },
    {
        "type": "list_map",
        "variables": {"items": [1]},
        "config": {
            "listVariable": "items",
            "expression": "float('nan')",
            "resultVariable": "out",
        },
    },
    {
        "type": "list_map",
        "variables": {"items": [2, "3"]},
        "config": {
            "listVariable": "items",
            "operation": "divide",
            "operand": 0,
            "resultVariable": "out",
        },
    },
    {
        "type": "list_map",
        "variables": {"items": [2]},
        "config": {"listVariable": "items", "operand": "bad", "resultVariable": "out"},
    },
    {
        "type": "list_merge",
        "variables": {"a": [1], "b": [2, 3]},
        "config": {"list1": "a", "list2": "b", "resultVariable": "out"},
    },
    {
        "type": "list_merge",
        "variables": {"a": [1], "b": "bad", "c": [3]},
        "config": {"listVariables": "a, b, missing, c", "resultVariable": "out"},
    },
    {
        "type": "list_flatten",
        "variables": {"items": [1, [2, [3, [4]]]]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_flatten",
        "variables": {"items": [1, [2, [3]]]},
        "config": {"listVariable": "items", "depth": 1, "resultVariable": "out"},
    },
    {
        "type": "list_flatten",
        "variables": {"items": [1]},
        "config": {"listVariable": "items", "depth": "bad", "resultVariable": "out"},
    },
    {
        "type": "list_chunk",
        "variables": {"items": [1, 2, 3, 4, 5]},
        "config": {"listVariable": "items", "chunkSize": 2, "resultVariable": "out"},
    },
    {
        "type": "list_chunk",
        "variables": {"items": [1]},
        "config": {"listVariable": "items", "chunkSize": 0, "resultVariable": "out"},
    },
    {
        "type": "list_remove_empty",
        "variables": {"items": [None, "", [], {}, 0, False, "x"]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_intersection",
        "variables": {"a": [1, 2, 3], "b": [2, 3, 4]},
        "config": {"list1": "a", "list2": "b", "resultVariable": "out"},
    },
    {
        "type": "list_union",
        "variables": {"a": [1, 2], "b": [2, 3]},
        "config": {"list1Variable": "a", "list2Variable": "b", "resultVariable": "out"},
    },
    {
        "type": "list_difference",
        "variables": {"a": [1, 2, 3], "b": [2]},
        "config": {"list1": "a", "list2": "b", "resultVariable": "out"},
    },
    {
        "type": "list_intersection",
        "variables": {"a": [[1]], "b": [[1]]},
        "config": {"list1": "a", "list2": "b", "resultVariable": "out"},
    },
    {
        "type": "list_cartesian_product",
        "variables": {"a": [1, 2], "b": ["x", "y"]},
        "config": {"list1": "a", "list2": "b", "resultVariable": "out"},
    },
    {
        "type": "list_cartesian_product",
        "variables": {"a": [1]},
        "config": {"listVariables": "a,missing", "resultVariable": "out"},
    },
    {
        "type": "list_shuffle",
        "seed": 17,
        "variables": {"items": [1, 2, 3, 4, 5]},
        "config": {"listVariable": "items", "resultVariable": "out"},
    },
    {
        "type": "list_sample",
        "seed": 17,
        "variables": {"items": [1, 2, 3, 4, 5]},
        "config": {"listVariable": "items", "sampleSize": 3, "resultVariable": "out"},
    },
    {
        "type": "list_sample",
        "variables": {"items": [1, 2]},
        "config": {"listVariable": "items", "sampleCount": 3, "resultVariable": "out"},
    },
    {
        "type": "dict_merge",
        "variables": {"a": {"x": 1, "same": 1}, "b": {"y": 2, "same": 2}},
        "config": {"dict1": "a", "dict2": "b", "resultVariable": "out"},
    },
    {
        "type": "dict_merge",
        "variables": {"a": {"x": 1}, "b": "bad", "c": {"z": 3}},
        "config": {"dictVariables": "a,b,c", "resultVariable": "out"},
    },
    {
        "type": "dict_filter",
        "variables": {"data": {"a": 1, "b": 2, "c": 3}},
        "config": {
            "dictVariable": "data",
            "condition": "v >= 2 and k != 'c'",
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_filter",
        "variables": {"data": {"a": 1}},
        "config": {
            "dictVariable": "data",
            "condition": "v.__class__",
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_filter",
        "variables": {"data": {"a": 1}},
        "config": {
            "dictVariable": "data",
            "condition": "1 / 0",
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_filter",
        "variables": {"data": {"a": 1, "b": 2, "c": 3}},
        "config": {
            "dictVariable": "data",
            "filterKeys": "a, c",
            "filterMode": "include",
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_filter",
        "variables": {"data": {"a": 1, "b": 2}},
        "config": {
            "dictVariable": "data",
            "filterKeys": "a",
            "filterMode": "exclude",
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_map_values",
        "variables": {"data": {"a": 1, "b": 2}},
        "config": {
            "dictVariable": "data",
            "expression": "v * 2",
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_map_values",
        "variables": {"data": {"a": 1}},
        "config": {
            "dictVariable": "data",
            "expression": "float('inf')",
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_map_values",
        "variables": {"data": {"a": 1, "b": 2}},
        "config": {
            "dictVariable": "data",
            "expression": "v * 2 if k == 'a' else v + 1",
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_map_values",
        "variables": {"data": {"a": 1}},
        "config": {
            "dictVariable": "data",
            "expression": "unknown",
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_map_values",
        "variables": {"data": {"a": 0}},
        "config": {
            "dictVariable": "data",
            "expression": "1 / v",
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_map_values",
        "variables": {"data": {"a": 2, "b": "3", "c": "bad"}},
        "config": {
            "dictVariable": "data",
            "operation": "add",
            "operand": 2,
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_map_values",
        "variables": {"data": {"a": 2}},
        "config": {
            "dictVariable": "data",
            "operation": "divide",
            "operand": 0,
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_invert",
        "variables": {"data": {"a": 1, "b": 1, "c": [2]}},
        "config": {"dictVariable": "data", "resultVariable": "out"},
    },
    {
        "type": "dict_sort",
        "variables": {"data": {"c": 1, "a": 3, "b": 2}},
        "config": {
            "dictVariable": "data",
            "sortBy": "key",
            "order": "desc",
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_sort",
        "variables": {"data": {"c": 1, "a": 3, "b": 2}},
        "config": {
            "dictVariable": "data",
            "sortBy": "value",
            "sortOrder": "asc",
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_sort",
        "variables": {"data": {"a": 1, "b": "2"}},
        "config": {"dictVariable": "data", "sortBy": "value", "resultVariable": "out"},
    },
    {
        "type": "dict_deep_copy",
        "variables": {"data": {"a": [1, {"b": 2}]}},
        "config": {"dictVariable": "data", "resultVariable": "out"},
    },
    {
        "type": "dict_get_path",
        "variables": {"data": {"a": {"b": {"c": 3}}}},
        "config": {"dictVariable": "data", "path": "a.b.c", "resultVariable": "out"},
    },
    {
        "type": "dict_get_path",
        "variables": {"data": {"a": {}}},
        "config": {
            "dictVariable": "data",
            "path": "a.missing",
            "defaultValue": 9,
            "resultVariable": "out",
        },
    },
    {
        "type": "dict_flatten",
        "variables": {"data": {"a": {"b": 1, "c": {"d": 2}}, "e": 3}},
        "config": {"dictVariable": "data", "resultVariable": "out"},
    },
    {
        "type": "dict_flatten",
        "variables": {"data": {"a": {"b": 1}}},
        "config": {"dictVariable": "data", "separator": "/", "resultVariable": "out"},
    },
]


@pytest.mark.parametrize(
    "payload",
    CASES,
    ids=[f"{case['type']}-{index}" for index, case in enumerate(CASES)],
)
def test_advanced_data_matches_frozen_webrpa(payload: dict[str, Any]) -> None:
    assert asyncio.run(_target_result(payload)) == _source_result(payload)


def test_frozen_source_file_has_all_approved_module_types() -> None:
    assert set(_source_result({"operation": "types"})["types"]) == APPROVED_SOURCE_TYPES


def test_target_file_has_all_approved_module_types() -> None:
    assert set(_target_executors()) == APPROVED_SOURCE_TYPES


@pytest.mark.parametrize("module_type", sorted(APPROVED_SOURCE_TYPES))
def test_advanced_data_never_requires_a_browser(module_type: str) -> None:
    assert _target_executors()[module_type]().requires_browser is False


@pytest.mark.parametrize(
    ("module_type", "variables", "config"),
    [
        (
            "csv_parse",
            {},
            {
                "csvContent": "a,b\n"
                + "\n".join(f"{i},{i + 1}" for i in range(10_000)),
                "resultVariable": "out",
            },
        ),
        (
            "csv_generate",
            {"items": [[i, i + 1] for i in range(10_000)]},
            {"dataVariable": "items", "resultVariable": "out"},
        ),
        (
            "list_to_string_advanced",
            {"items": list(range(10_000))},
            {"listVariable": "items", "resultVariable": "out"},
        ),
        (
            "list_filter",
            {"items": list(range(10_000))},
            {
                "listVariable": "items",
                "condition": "x % 2 == 0",
                "resultVariable": "out",
            },
        ),
        (
            "list_map",
            {"items": list(range(10_000))},
            {
                "listVariable": "items",
                "expression": "x * 2",
                "resultVariable": "out",
            },
        ),
        (
            "list_flatten",
            {"items": list(range(10_000))},
            {"listVariable": "items", "resultVariable": "out"},
        ),
        (
            "list_cartesian_product",
            {"left": list(range(200)), "right": list(range(200))},
            {"list1": "left", "list2": "right", "resultVariable": "out"},
        ),
        (
            "dict_filter",
            {"items": {str(index): index for index in range(10_000)}},
            {
                "dictVariable": "items",
                "condition": "v % 2 == 0",
                "resultVariable": "out",
            },
        ),
        (
            "dict_map_values",
            {"items": {str(index): index for index in range(10_000)}},
            {
                "dictVariable": "items",
                "expression": "v * 2",
                "resultVariable": "out",
            },
        ),
        (
            "dict_flatten",
            {"items": {str(index): index for index in range(10_000)}},
            {"dictVariable": "items", "resultVariable": "out"},
        ),
    ],
)
def test_large_advanced_data_operation_yields_and_cancels_before_writing_result(
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


def test_cartesian_product_rejects_unbounded_materialization() -> None:
    context = ExecutionContext(
        variables={"left": list(range(317)), "right": list(range(317))}
    )

    result = asyncio.run(
        _target_executors()["list_cartesian_product"]().execute(
            {"list1": "left", "list2": "right", "resultVariable": "out"},
            context,
        )
    )

    assert result.success is False
    assert result.error == "笛卡尔积规模超过工作流安全限制"
    assert "out" not in context.variables


def test_cartesian_product_allows_the_100000_item_boundary() -> None:
    context = ExecutionContext(
        variables={"left": list(range(100)), "right": list(range(1_000))}
    )

    result = asyncio.run(
        _target_executors()["list_cartesian_product"]().execute(
            {"list1": "left", "list2": "right", "resultVariable": "out"},
            context,
        )
    )

    assert result.success is True
    assert len(result.data) == 100_000
    assert context.variables["out"] is result.data


def test_list_flatten_rejects_cycles() -> None:
    cyclic: list[Any] = []
    cyclic.append(cyclic)
    context = ExecutionContext(variables={"items": cyclic})

    result = asyncio.run(
        _target_executors()["list_flatten"]().execute(
            {"listVariable": "items", "resultVariable": "out"}, context
        )
    )

    assert result.success is False
    assert result.error == "扁平化失败: 列表包含循环引用"
    assert "out" not in context.variables


def test_list_flatten_rejects_excessive_depth() -> None:
    nested: list[Any] = [0]
    for _ in range(257):
        nested = [nested]
    context = ExecutionContext(variables={"items": nested})

    result = asyncio.run(
        _target_executors()["list_flatten"]().execute(
            {"listVariable": "items", "resultVariable": "out"}, context
        )
    )

    assert result.success is False
    assert result.error == "扁平化失败: 列表嵌套超过工作流安全限制"
    assert "out" not in context.variables


def test_list_flatten_allows_the_256_level_boundary() -> None:
    nested: list[Any] = [0]
    for _ in range(256):
        nested = [nested]
    context = ExecutionContext(variables={"items": nested})

    result = asyncio.run(
        _target_executors()["list_flatten"]().execute(
            {"listVariable": "items", "resultVariable": "out"}, context
        )
    )

    assert result.success is True
    assert result.data == [0]


def test_dict_flatten_rejects_cycles() -> None:
    cyclic: dict[str, Any] = {}
    cyclic["self"] = cyclic
    context = ExecutionContext(variables={"items": cyclic})

    result = asyncio.run(
        _target_executors()["dict_flatten"]().execute(
            {"dictVariable": "items", "resultVariable": "out"}, context
        )
    )

    assert result.success is False
    assert result.error == "扁平化失败: 字典包含循环引用"
    assert "out" not in context.variables


def test_dict_flatten_rejects_excessive_depth() -> None:
    nested: dict[str, Any] = {"value": 0}
    for _ in range(257):
        nested = {"nested": nested}
    context = ExecutionContext(variables={"items": nested})

    result = asyncio.run(
        _target_executors()["dict_flatten"]().execute(
            {"dictVariable": "items", "resultVariable": "out"}, context
        )
    )

    assert result.success is False
    assert result.error == "扁平化失败: 字典嵌套超过工作流安全限制"
    assert "out" not in context.variables


def test_dict_flatten_allows_the_256_level_boundary() -> None:
    nested: dict[str, Any] = {"value": 0}
    for _ in range(256):
        nested = {"nested": nested}
    context = ExecutionContext(variables={"items": nested})

    result = asyncio.run(
        _target_executors()["dict_flatten"]().execute(
            {"dictVariable": "items", "separator": "/", "resultVariable": "out"},
            context,
        )
    )

    assert result.success is True
    assert len(result.data) == 1


def test_complex_result_is_normalized_only_at_the_test_transport() -> None:
    context = ExecutionContext(variables={"items": [-1]})

    result = asyncio.run(
        _target_executors()["list_map"]().execute(
            {
                "listVariable": "items",
                "operation": "power",
                "operand": 0.5,
                "resultVariable": "out",
            },
            context,
        )
    )

    assert isinstance(result.data[0], complex)
    assert isinstance(context.variables["out"][0], complex)


def test_non_finite_result_is_normalized_only_at_the_test_transport() -> None:
    context = ExecutionContext(variables={"items": [1]})

    result = asyncio.run(
        _target_executors()["list_map"]().execute(
            {
                "listVariable": "items",
                "expression": "float('nan')",
                "resultVariable": "out",
            },
            context,
        )
    )

    assert math.isnan(result.data[0])
    assert math.isnan(context.variables["out"][0])


@pytest.mark.parametrize(
    ("module_type", "variables", "config", "expected_error"),
    [
        (
            "list_map",
            {"items": [1]},
            {
                "listVariable": "items",
                "expression": "'x' * 50000000",
                "resultVariable": "out",
            },
            "映射表达式不合法: 表达式文本结果超过工作流安全限制",
        ),
        (
            "dict_map_values",
            {"items": {"a": 1}},
            {
                "dictVariable": "items",
                "expression": "[v] * 100001",
                "resultVariable": "out",
            },
            "映射表达式不合法: 表达式集合结果超过工作流安全限制",
        ),
    ],
)
def test_safe_expression_rejects_unbounded_materialization(
    module_type: str,
    variables: dict[str, Any],
    config: dict[str, Any],
    expected_error: str,
) -> None:
    context = ExecutionContext(variables=variables)

    result = asyncio.run(_target_executors()[module_type]().execute(config, context))

    assert result.success is False
    assert result.error == expected_error
    assert "out" not in context.variables


class _CancelOnThirdCheck:
    @property
    def cancelled(self) -> bool:
        return False

    def __init__(self) -> None:
        self.calls = 0

    def raise_if_cancelled(self) -> None:
        self.calls += 1
        if self.calls >= 3:
            raise asyncio.CancelledError


@pytest.mark.parametrize(
    ("module_type", "variables", "config"),
    [
        (
            "list_union",
            {"left": list(range(1_000)), "right": list(range(500, 1_500))},
            {"list1": "left", "list2": "right", "resultVariable": "out"},
        ),
        (
            "list_shuffle",
            {"items": list(range(1_000))},
            {"listVariable": "items", "resultVariable": "out"},
        ),
        (
            "dict_sort",
            {"items": {str(index): index for index in range(1_000)}},
            {"dictVariable": "items", "resultVariable": "out"},
        ),
        (
            "dict_deep_copy",
            {"items": {str(index): [index] for index in range(1_000)}},
            {"dictVariable": "items", "resultVariable": "out"},
        ),
    ],
)
def test_bulk_operations_recheck_cancellation_before_committing_result(
    module_type: str,
    variables: dict[str, Any],
    config: dict[str, Any],
) -> None:
    token = _CancelOnThirdCheck()
    context = ExecutionContext(variables=variables, cancellation=token)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_target_executors()[module_type]().execute(config, context))

    assert "out" not in context.variables


@pytest.mark.parametrize(
    ("module_type", "variables", "config", "expected_error"),
    [
        (
            "list_filter",
            {"items": [1, 2]},
            {
                "listVariable": "items",
                "filterType": "unknown",
                "resultVariable": "out",
            },
            "不支持的过滤类型: unknown",
        ),
        (
            "list_map",
            {"items": [1, 2]},
            {
                "listVariable": "items",
                "operation": "unknown",
                "resultVariable": "out",
            },
            "不支持的映射操作: unknown",
        ),
        (
            "dict_filter",
            {"items": {"a": 1}},
            {
                "dictVariable": "items",
                "filterMode": "unknown",
                "resultVariable": "out",
            },
            "不支持的过滤模式: unknown",
        ),
        (
            "dict_map_values",
            {"items": {"a": 1}},
            {
                "dictVariable": "items",
                "operation": "unknown",
                "resultVariable": "out",
            },
            "不支持的映射操作: unknown",
        ),
        (
            "dict_sort",
            {"items": {"a": 1}},
            {
                "dictVariable": "items",
                "sortBy": "unknown",
                "resultVariable": "out",
            },
            "不支持的排序字段: unknown",
        ),
        (
            "dict_sort",
            {"items": {"a": 1}},
            {
                "dictVariable": "items",
                "order": "unknown",
                "resultVariable": "out",
            },
            "不支持的排序顺序: unknown",
        ),
    ],
)
def test_unknown_advanced_data_enum_is_rejected(
    module_type: str,
    variables: dict[str, Any],
    config: dict[str, Any],
    expected_error: str,
) -> None:
    context = ExecutionContext(variables=variables)

    result = asyncio.run(_target_executors()[module_type]().execute(config, context))

    assert result.success is False
    assert result.error == expected_error
    assert "out" not in context.variables


class _CredentialReader:
    def get_field(self, name: str, field_name: str) -> str:
        assert (name, field_name) == ("prod", "password")
        return "S3CRET-should-not-log"


@pytest.mark.parametrize(
    ("module_type", "variables", "config", "expected_prefix"),
    [
        (
            "list_map",
            {"items": [1]},
            {
                "listVariable": "items",
                "expression": "int('{{cred:prod.password}}')",
                "resultVariable": "out",
            },
            "映射表达式求值失败",
        ),
        (
            "list_filter",
            {"items": [1]},
            {
                "listVariable": "items",
                "condition": "{{cred:prod.password}} > 0",
                "resultVariable": "out",
            },
            "过滤条件不合法",
        ),
        (
            "dict_map_values",
            {"items": {"a": 1}},
            {
                "dictVariable": "items",
                "expression": "int('{{cred:prod.password}}')",
                "resultVariable": "out",
            },
            "映射表达式求值失败",
        ),
    ],
)
def test_expression_failure_does_not_expose_resolved_credential(
    module_type: str,
    variables: dict[str, Any],
    config: dict[str, Any],
    expected_prefix: str,
) -> None:
    context = ExecutionContext(variables=variables, credentials=_CredentialReader())

    result = asyncio.run(_target_executors()[module_type]().execute(config, context))

    assert result.success is False
    assert result.error == expected_prefix
    assert "S3CRET" not in result.error
    assert "out" not in context.variables


@pytest.mark.parametrize(
    ("module_type", "variables", "config", "expected_error"),
    [
        (
            "list_union",
            {"left": list(range(50_001)), "right": list(range(50_000))},
            {"list1": "left", "list2": "right", "resultVariable": "out"},
            "列表规模超过工作流安全限制",
        ),
        (
            "dict_sort",
            {"items": {str(index): index for index in range(100_001)}},
            {"dictVariable": "items", "resultVariable": "out"},
            "字典规模超过工作流安全限制",
        ),
        (
            "list_to_string_advanced",
            {"items": ["x" * 524_288, "y" * 524_289]},
            {"listVariable": "items", "separator": "", "resultVariable": "out"},
            "转换结果超过工作流安全限制",
        ),
    ],
)
def test_bulk_advanced_data_rejects_unbounded_input_or_output(
    module_type: str,
    variables: dict[str, Any],
    config: dict[str, Any],
    expected_error: str,
) -> None:
    context = ExecutionContext(variables=variables)

    result = asyncio.run(_target_executors()[module_type]().execute(config, context))

    assert result.success is False
    assert result.error == expected_error
    assert "out" not in context.variables
