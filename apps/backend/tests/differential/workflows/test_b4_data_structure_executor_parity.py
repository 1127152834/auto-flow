from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from autoflow.application.workflows.executors.data_structure import (
    DictGetExecutor,
    DictKeysExecutor,
    DictOperationExecutor,
    ListExportExecutor,
    ListGetExecutor,
    ListLengthExecutor,
    ListOperationExecutor,
    RegexExtractExecutor,
    StringCaseExecutor,
    StringConcatExecutor,
    StringJoinExecutor,
    StringReplaceExecutor,
    StringSplitExecutor,
    StringSubstringExecutor,
    StringTrimExecutor,
)
from autoflow.domain.workflows.execution import ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_data_structure_harness.py")

EXECUTORS = {
    executor().module_type: executor
    for executor in (
        ListOperationExecutor,
        ListGetExecutor,
        ListLengthExecutor,
        ListExportExecutor,
        DictOperationExecutor,
        DictGetExecutor,
        DictKeysExecutor,
        RegexExtractExecutor,
        StringReplaceExecutor,
        StringSplitExecutor,
        StringJoinExecutor,
        StringConcatExecutor,
        StringTrimExecutor,
        StringCaseExecutor,
        StringSubstringExecutor,
    )
}


def _source_result(payload: dict[str, Any]) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(FROZEN_BACKEND)
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", str(FROZEN_HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        check=True,
        capture_output=True,
        text=True, encoding="utf-8",
        env=env,
    )
    return json.loads(completed.stdout.splitlines()[-1])


async def _target_result(
    payload: dict[str, Any], artifacts: Any = None
) -> dict[str, Any]:
    context = ExecutionContext(
        variables=json.loads(
            json.dumps(payload.get("variables", {}), ensure_ascii=False)
        ),
        artifacts=artifacts,
    )
    result = await EXECUTORS[payload["type"]]().execute(payload["config"], context)
    return json.loads(
        json.dumps(
            {
                "success": result.success,
                "message": result.message,
                "data": result.data,
                "error": result.error,
                "variables": context.variables,
            },
            ensure_ascii=False,
        )
    )


CASES: list[dict[str, Any]] = [
    {
        "type": "list_operation",
        "variables": {"items": [1]},
        "config": {"listVariable": "items", "listAction": "append", "listValue": 2},
    },
    {
        "type": "list_operation",
        "variables": {"items": [1, 3]},
        "config": {
            "listVariable": "items",
            "listAction": "insert",
            "listValue": 2,
            "listIndex": 1,
        },
    },
    {
        "type": "list_operation",
        "variables": {"items": [1, 2, 2]},
        "config": {"listVariable": "items", "listAction": "remove", "listValue": 2},
    },
    {
        "type": "list_operation",
        "variables": {"items": [1]},
        "config": {"listVariable": "items", "listAction": "remove", "listValue": 9},
    },
    {
        "type": "list_operation",
        "variables": {"items": ["a", "b"]},
        "config": {
            "listVariable": "items",
            "listAction": "pop",
            "listIndex": -1,
            "resultVariable": "popped",
        },
    },
    {
        "type": "list_operation",
        "variables": {"items": []},
        "config": {"listVariable": "items", "listAction": "pop", "listIndex": 0},
    },
    {
        "type": "list_operation",
        "variables": {"items": [1]},
        "config": {"listVariable": "items", "listAction": "pop", "listIndex": 2},
    },
    {
        "type": "list_operation",
        "variables": {"items": [3, 1, 2]},
        "config": {"listVariable": "items", "listAction": "sort"},
    },
    {
        "type": "list_operation",
        "variables": {"items": [1, "a"]},
        "config": {"listVariable": "items", "listAction": "sort"},
    },
    {
        "type": "list_operation",
        "variables": {"items": [1, 2]},
        "config": {"listVariable": "items", "listAction": "reverse"},
    },
    {
        "type": "list_operation",
        "variables": {"items": [1]},
        "config": {"listVariable": "items", "listAction": "clear"},
    },
    {
        "type": "list_operation",
        "config": {
            "listVariable": "created",
            "listAction": "append",
            "listValue": "新建",
        },
    },
    {
        "type": "list_operation",
        "config": {"listVariable": "items", "listAction": "unknown"},
    },
    {
        "type": "list_operation",
        "variables": {"items": "bad"},
        "config": {"listVariable": "items"},
    },
    {
        "type": "list_get",
        "variables": {"items": ["a", "b"]},
        "config": {"listVariable": "items", "listIndex": -1, "variableName": "out"},
    },
    {
        "type": "list_get",
        "variables": {"items": ["a"]},
        "config": {"listVariable": "items", "listIndex": "bad", "variableName": "out"},
    },
    {
        "type": "list_get",
        "variables": {"items": []},
        "config": {"listVariable": "items", "listIndex": 0, "variableName": "out"},
    },
    {
        "type": "list_get",
        "variables": {"items": ["a"]},
        "config": {"listVariable": "items", "listIndex": 1, "variableName": "out"},
    },
    {
        "type": "list_get",
        "config": {"listVariable": "missing", "listIndex": 0, "variableName": "out"},
    },
    {
        "type": "list_length",
        "variables": {"items": [1, 2]},
        "config": {"listVariable": "items", "variableName": "length"},
    },
    {
        "type": "list_length",
        "variables": {"items": "bad"},
        "config": {"listVariable": "items", "variableName": "length"},
    },
    {
        "type": "dict_operation",
        "variables": {"data": {"a": 1}},
        "config": {
            "dictVariable": "data",
            "dictAction": "set",
            "dictKey": "b",
            "dictValue": 2,
        },
    },
    {
        "type": "dict_operation",
        "variables": {"data": {"a": 1}},
        "config": {"dictVariable": "data", "dictAction": "delete", "dictKey": "a"},
    },
    {
        "type": "dict_operation",
        "variables": {"data": {"a": 1}},
        "config": {
            "dictVariable": "data",
            "dictAction": "delete",
            "dictKey": "missing",
        },
    },
    {
        "type": "dict_operation",
        "variables": {"data": {"a": 1}},
        "config": {"dictVariable": "data", "dictAction": "clear"},
    },
    {
        "type": "dict_operation",
        "config": {
            "dictVariable": "created",
            "dictAction": "set",
            "dictKey": "a",
            "dictValue": 1,
        },
    },
    {
        "type": "dict_operation",
        "config": {"dictVariable": "data", "dictAction": "set", "dictKey": ""},
    },
    {
        "type": "dict_operation",
        "variables": {"data": []},
        "config": {"dictVariable": "data"},
    },
    {
        "type": "dict_get",
        "variables": {"data": {"a": 0}},
        "config": {
            "dictVariable": "data",
            "dictKey": "a",
            "defaultValue": 9,
            "variableName": "out",
        },
    },
    {
        "type": "dict_get",
        "variables": {"data": {}},
        "config": {
            "dictVariable": "data",
            "dictKey": "a",
            "defaultValue": 0,
            "variableName": "out",
        },
    },
    {
        "type": "dict_get",
        "variables": {"data": {}},
        "config": {
            "dictVariable": "data",
            "dictKey": "a",
            "defaultValue": "默认",
            "variableName": "out",
        },
    },
    {
        "type": "dict_get",
        "config": {"dictVariable": "missing", "dictKey": "a", "variableName": "out"},
    },
    {
        "type": "dict_keys",
        "variables": {"data": {"a": 1, "b": 2}},
        "config": {"dictVariable": "data", "keyType": "keys", "variableName": "out"},
    },
    {
        "type": "dict_keys",
        "variables": {"data": {"a": 1, "b": 2}},
        "config": {"dictVariable": "data", "keyType": "values", "variableName": "out"},
    },
    {
        "type": "dict_keys",
        "variables": {"data": {"a": 1, "b": 2}},
        "config": {"dictVariable": "data", "keyType": "items", "variableName": "out"},
    },
    {
        "type": "dict_keys",
        "variables": {"data": {}},
        "config": {"dictVariable": "data", "keyType": "unknown", "variableName": "out"},
    },
    {
        "type": "regex_extract",
        "config": {
            "inputText": "订单A-12与a-34",
            "pattern": "a-\\d+",
            "extractMode": "first",
            "ignoreCase": True,
            "variableName": "out",
        },
    },
    {
        "type": "regex_extract",
        "config": {
            "inputText": "A1 B22",
            "pattern": "\\d+",
            "extractMode": "all",
            "variableName": "out",
        },
    },
    {
        "type": "regex_extract",
        "config": {
            "inputText": "张三:18",
            "pattern": "(\\w+):(\\d+)",
            "extractMode": "groups",
            "variableName": "out",
        },
    },
    {
        "type": "regex_extract",
        "config": {
            "inputText": "none",
            "pattern": "(\\d+)",
            "extractMode": "groups",
            "variableName": "out",
        },
    },
    {
        "type": "regex_extract",
        "config": {
            "inputText": "text",
            "pattern": "x",
            "extractMode": "unknown",
            "variableName": "out",
        },
    },
    {
        "type": "regex_extract",
        "config": {"inputText": "text", "pattern": "(", "variableName": "out"},
    },
    {
        "type": "regex_extract",
        "config": {"inputText": "", "pattern": "x", "variableName": "out"},
    },
    {
        "type": "string_replace",
        "config": {
            "inputText": "甲甲乙",
            "searchValue": "甲",
            "replaceValue": "中",
            "replaceAll": True,
            "variableName": "out",
        },
    },
    {
        "type": "string_replace",
        "config": {
            "inputText": "a1 a2",
            "replaceMode": "regex",
            "searchValue": "a\\d",
            "replaceValue": "x",
            "replaceAll": False,
            "variableName": "out",
        },
    },
    {
        "type": "string_replace",
        "config": {
            "inputText": "abc",
            "replaceMode": "regex",
            "searchValue": "(",
            "replaceValue": "x",
            "variableName": "out",
        },
    },
    {
        "type": "string_replace",
        "config": {
            "inputText": "abc",
            "searchValue": "",
            "replaceValue": "x",
            "variableName": "out",
        },
    },
    {
        "type": "string_split",
        "config": {
            "inputText": "甲\\n乙\\n丙",
            "separator": "\\n",
            "maxSplit": 1,
            "variableName": "out",
        },
    },
    {
        "type": "string_split",
        "config": {"inputText": "a\tb\tc", "separator": "\\t", "variableName": "out"},
    },
    {
        "type": "string_split",
        "config": {"inputText": "  a  b ", "separator": "", "variableName": "out"},
    },
    {
        "type": "string_split",
        "variables": {"limit": "2"},
        "config": {
            "inputText": "a,b,c,d",
            "separator": ",",
            "maxSplit": "{limit}",
            "variableName": "out",
        },
    },
    {"type": "string_split", "config": {"inputText": "", "variableName": "out"}},
    {
        "type": "string_join",
        "variables": {"items": ["甲", 2, False]},
        "config": {"listVariable": "{items}", "separator": "|", "variableName": "out"},
    },
    {
        "type": "string_join",
        "variables": {"items": "不是列表"},
        "config": {"listVariable": "items", "separator": ",", "variableName": "out"},
    },
    {
        "type": "string_join",
        "config": {"listVariable": "missing", "variableName": "out"},
    },
    {
        "type": "string_concat",
        "variables": {"left": "前"},
        "config": {"string1": "{left}", "string2": "后", "variableName": "out"},
    },
    {
        "type": "string_concat",
        "config": {"string1": None, "string2": 0, "variableName": "out"},
    },
    {
        "type": "string_concat",
        "config": {"string1": "a", "string2": "b", "variableName": ""},
    },
    {
        "type": "string_trim",
        "config": {"inputText": "  甲 乙  ", "trimMode": "both", "variableName": "out"},
    },
    {
        "type": "string_trim",
        "config": {"inputText": "  甲  ", "trimMode": "start", "variableName": "out"},
    },
    {
        "type": "string_trim",
        "config": {"inputText": "  甲  ", "trimMode": "end", "variableName": "out"},
    },
    {
        "type": "string_trim",
        "config": {"inputText": " 甲\n 乙 ", "trimMode": "all", "variableName": "out"},
    },
    {
        "type": "string_trim",
        "config": {"inputText": "甲", "trimMode": "middle", "variableName": "out"},
    },
    {
        "type": "string_case",
        "config": {"inputText": "ab中", "caseMode": "upper", "variableName": "out"},
    },
    {
        "type": "string_case",
        "config": {"inputText": "AB中", "caseMode": "lower", "variableName": "out"},
    },
    {
        "type": "string_case",
        "config": {
            "inputText": "hELLO WORLD",
            "caseMode": "capitalize",
            "variableName": "out",
        },
    },
    {
        "type": "string_case",
        "config": {
            "inputText": "hello world",
            "caseMode": "title",
            "variableName": "out",
        },
    },
    {
        "type": "string_case",
        "config": {"inputText": "a", "caseMode": "swap", "variableName": "out"},
    },
    {
        "type": "string_substring",
        "config": {
            "inputText": "零一二三四",
            "startIndex": 1,
            "endIndex": 4,
            "variableName": "out",
        },
    },
    {
        "type": "string_substring",
        "config": {
            "inputText": "零一二三",
            "startIndex": -2,
            "endIndex": "",
            "variableName": "out",
        },
    },
    {
        "type": "string_substring",
        "variables": {"start": 2},
        "config": {
            "inputText": "abcdef",
            "startIndex": "{start}",
            "variableName": "out",
        },
    },
    {
        "type": "string_substring",
        "config": {"inputText": "abc", "startIndex": "bad", "variableName": "out"},
    },
]

REQUIRED_AND_BRANCH_CASES: list[dict[str, Any]] = [
    {"type": "list_operation", "config": {}},
    {
        "type": "list_operation",
        "variables": {"items": [1, 3], "action": "insert", "index": "1.9", "value": 2},
        "config": {
            "listVariable": "items",
            "listAction": "{action}",
            "listIndex": "{index}",
            "listValue": "{value}",
        },
    },
    {
        "type": "list_operation",
        "variables": {"items": ["a"]},
        "config": {
            "listVariable": "${items}",
            "listAction": "pop",
            "resultVariable": "${popped}",
        },
    },
    {"type": "list_get", "config": {"variableName": "out"}},
    {
        "type": "list_get",
        "variables": {"items": [1]},
        "config": {"listVariable": "items"},
    },
    {
        "type": "list_get",
        "variables": {"items": "bad"},
        "config": {"listVariable": "items", "variableName": "out"},
    },
    {
        "type": "list_get",
        "variables": {"items": ["a", "b"], "index": 1},
        "config": {
            "listVariable": "{items}",
            "listIndex": "{index}",
            "variableName": "{out}",
        },
    },
    {"type": "list_length", "config": {"variableName": "out"}},
    {
        "type": "list_length",
        "variables": {"items": []},
        "config": {"listVariable": "items"},
    },
    {
        "type": "list_length",
        "config": {"listVariable": "missing", "variableName": "out"},
    },
    {
        "type": "list_length",
        "variables": {"items": [1, 2]},
        "config": {"listVariable": "${items}", "variableName": "${length}"},
    },
    {"type": "dict_operation", "config": {}},
    {
        "type": "dict_operation",
        "config": {"dictVariable": "data", "dictAction": "unknown"},
    },
    {
        "type": "dict_operation",
        "variables": {"data": {}},
        "config": {
            "dictVariable": "data",
            "dictAction": "set",
            "dictKey": ["bad"],
            "dictValue": 1,
        },
    },
    {
        "type": "dict_operation",
        "variables": {"data": {}, "action": "set", "key": "编号", "value": 7},
        "config": {
            "dictVariable": "${data}",
            "dictAction": "{action}",
            "dictKey": "{key}",
            "dictValue": "{value}",
        },
    },
    {"type": "dict_get", "config": {"dictKey": "a", "variableName": "out"}},
    {
        "type": "dict_get",
        "variables": {"data": {}},
        "config": {"dictVariable": "data", "variableName": "out"},
    },
    {
        "type": "dict_get",
        "variables": {"data": {}},
        "config": {"dictVariable": "data", "dictKey": "a"},
    },
    {
        "type": "dict_get",
        "variables": {"data": []},
        "config": {"dictVariable": "data", "dictKey": "a", "variableName": "out"},
    },
    {
        "type": "dict_get",
        "variables": {"data": {}, "key": "a", "fallback": "默认"},
        "config": {
            "dictVariable": "{data}",
            "dictKey": "{key}",
            "defaultValue": "{fallback}",
            "variableName": "{out}",
        },
    },
    {"type": "dict_keys", "config": {"variableName": "out"}},
    {
        "type": "dict_keys",
        "variables": {"data": {}},
        "config": {"dictVariable": "data"},
    },
    {"type": "dict_keys", "config": {"dictVariable": "missing", "variableName": "out"}},
    {
        "type": "dict_keys",
        "variables": {"data": []},
        "config": {"dictVariable": "data", "variableName": "out"},
    },
    {
        "type": "dict_keys",
        "variables": {"data": {"a": 1}, "kind": "values"},
        "config": {
            "dictVariable": "${data}",
            "keyType": "{kind}",
            "variableName": "${out}",
        },
    },
    {"type": "regex_extract", "config": {"inputText": "abc", "variableName": "out"}},
    {"type": "regex_extract", "config": {"inputText": "abc", "pattern": "a"}},
    {
        "type": "regex_extract",
        "config": {
            "inputText": "abc",
            "pattern": "z",
            "extractMode": "first",
            "variableName": "out",
        },
    },
    {
        "type": "regex_extract",
        "config": {
            "inputText": "a1 b22",
            "pattern": "([a-z])(\\d+)",
            "extractMode": "all",
            "variableName": "out",
        },
    },
    {
        "type": "regex_extract",
        "config": {
            "inputText": "abc",
            "pattern": "a",
            "extractMode": "groups",
            "variableName": "out",
        },
    },
    {
        "type": "regex_extract",
        "variables": {"text": "A1", "pattern": "a\\d", "flag": "true"},
        "config": {
            "inputText": "{text}",
            "pattern": "{pattern}",
            "ignoreCase": "{flag}",
            "variableName": "{out}",
        },
    },
    {
        "type": "string_replace",
        "config": {"searchValue": "a", "replaceValue": "b", "variableName": "out"},
    },
    {
        "type": "string_replace",
        "config": {"inputText": "a", "searchValue": "a", "replaceValue": "b"},
    },
    {
        "type": "string_replace",
        "config": {
            "inputText": "a",
            "replaceMode": "regex",
            "searchValue": "(a)",
            "replaceValue": "\\2",
            "variableName": "out",
        },
    },
    {
        "type": "string_replace",
        "variables": {"mode": "text", "all": "false"},
        "config": {
            "inputText": "aaa",
            "replaceMode": "{mode}",
            "searchValue": "a",
            "replaceValue": "b",
            "replaceAll": "{all}",
            "variableName": "{out}",
        },
    },
    {"type": "string_split", "config": {"inputText": "a,b", "separator": ","}},
    {
        "type": "string_split",
        "config": {"inputText": "a,b", "separator": ",", "variableName": "{out}"},
    },
    {"type": "string_join", "config": {"variableName": "out"}},
    {
        "type": "string_join",
        "variables": {"items": []},
        "config": {"listVariable": "items"},
    },
    {
        "type": "string_join",
        "variables": {"items": ["a", "b"], "separator": "-"},
        "config": {
            "listVariable": "${items}",
            "separator": "{separator}",
            "variableName": "${out}",
        },
    },
    {
        "type": "string_concat",
        "config": {"string1": "a" * 40, "string2": "b" * 20, "variableName": "{out}"},
    },
    {"type": "string_trim", "config": {"inputText": " a "}},
    {"type": "string_trim", "config": {"inputText": " a ", "variableName": "{out}"}},
    {"type": "string_case", "config": {"inputText": "a"}},
    {"type": "string_case", "config": {"inputText": "a", "variableName": "${out}"}},
    {"type": "string_substring", "config": {"inputText": "abc"}},
    {
        "type": "string_substring",
        "config": {"inputText": "abc", "endIndex": "bad", "variableName": "out"},
    },
    {
        "type": "string_substring",
        "config": {"inputText": "abc", "startIndex": 1, "variableName": "{out}"},
    },
]

CASES.extend(REQUIRED_AND_BRANCH_CASES)
CASES.extend(
    [
        {
            "type": "list_export",
            "config": {"outputPath": "/tmp/autoflow-list-export-unused.txt"},
        },
        {
            "type": "list_export",
            "variables": {"items": []},
            "config": {"listVariable": "items"},
        },
        {
            "type": "list_export",
            "config": {
                "listVariable": "missing",
                "outputPath": "/tmp/autoflow-list-export-unused.txt",
            },
        },
        {
            "type": "list_export",
            "variables": {"items": "not-a-list"},
            "config": {
                "listVariable": "items",
                "outputPath": "/tmp/autoflow-list-export-unused.txt",
            },
        },
        {
            "type": "list_export",
            "variables": {"1": []},
            "config": {
                "listVariable": 1,
                "outputPath": "/tmp/autoflow-list-export-unused.txt",
            },
        },
    ]
)

APPROVED_SOURCE_TYPES = {
    "list_operation",
    "list_get",
    "list_length",
    "list_export",
    "dict_operation",
    "dict_get",
    "dict_keys",
    "regex_extract",
    "string_replace",
    "string_split",
    "string_join",
    "string_concat",
    "string_trim",
    "string_case",
    "string_substring",
}


@pytest.mark.parametrize(
    "payload",
    CASES,
    ids=[f"{case['type']}-{index}" for index, case in enumerate(CASES)],
)
def test_data_structure_family_non_file_cases_match_frozen_webrpa(
    payload: dict[str, Any],
) -> None:
    assert asyncio.run(_target_result(payload)) == _source_result(payload)


def test_frozen_source_file_has_all_fifteen_approved_module_types() -> None:
    assert set(_source_result({"operation": "types"})["types"]) == APPROVED_SOURCE_TYPES


def test_target_contains_all_fifteen_approved_module_types() -> None:
    assert set(EXECUTORS) == APPROVED_SOURCE_TYPES


@pytest.mark.parametrize(
    "payload",
    [
        case
        for case in REQUIRED_AND_BRANCH_CASES
        if case.get("config", {}).get("variableName") in {"{out}", "${out}"}
    ],
)
def test_output_variable_names_remain_literal(payload: dict[str, Any]) -> None:
    result = asyncio.run(_target_result(payload))
    literal_name = payload["config"]["variableName"]
    assert literal_name in result["variables"]
    assert "out" not in result["variables"]


def test_pop_result_variable_name_remains_literal() -> None:
    payload = REQUIRED_AND_BRANCH_CASES[2]
    result = asyncio.run(_target_result(payload))
    assert result["variables"]["${popped}"] == "a"
    assert "popped" not in result["variables"]


class _DirectTextWriter:
    async def write_bytes(
        self, *, name: str, content: bytes, mime_type: str
    ) -> str:
        raise AssertionError("list_export must use the text output port")

    async def write_text(
        self,
        *,
        output_path: str,
        content: str,
        separator: str,
        encoding: str,
        append: bool,
        mime_type: str,
    ) -> str:
        def write() -> str:
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            with target.open(mode, encoding=encoding) as output:
                if append and target.exists() and target.stat().st_size > 0:
                    output.write(separator)
                output.write(content)
            return str(target)

        return await asyncio.to_thread(write)


def _restore_file(path: Path, content: bytes | None) -> None:
    path.unlink(missing_ok=True)
    if content is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


@pytest.mark.parametrize(
    ("variables", "config", "initial"),
    [
        (
            {"items": ["中文", 2, True, None, {"键": [1, 2]}]},
            {"listVariable": "items", "separator": "\\n", "encoding": "utf-8"},
            None,
        ),
        (
            {"items": ["a", "b"]},
            {"listVariable": "${items}", "separator": "\\t", "appendMode": False},
            b"old",
        ),
        (
            {"items": ["a", "b"]},
            {"listVariable": "{items}", "separator": "|", "appendMode": True},
            b"old",
        ),
        (
            {"items": []},
            {"listVariable": "items", "separator": "\\r\\n", "appendMode": "True"},
            b"old",
        ),
        (
            {"items": ["中文"]},
            {"listVariable": "items", "encoding": "utf-8-sig"},
            None,
        ),
    ],
)
def test_list_export_file_behavior_matches_frozen_webrpa(
    tmp_path: Path,
    variables: dict[str, Any],
    config: dict[str, Any],
    initial: bytes | None,
) -> None:
    target = tmp_path / "result.txt"
    payload = {
        "type": "list_export",
        "variables": variables,
        "config": {**config, "outputPath": str(target)},
    }
    _restore_file(target, initial)
    source_result = _source_result(payload)
    source_bytes = target.read_bytes()

    _restore_file(target, initial)
    target_result = asyncio.run(_target_result(payload, _DirectTextWriter()))

    assert target_result == source_result
    assert target.read_bytes() == source_bytes
    assert target_result["variables"] == variables


def test_list_export_resolves_file_options_and_preserves_reported_path(
    tmp_path: Path,
) -> None:
    target = tmp_path / "variable-output.txt"
    payload = {
        "type": "list_export",
        "variables": {
            "items": ["一", "二"],
            "path": str(target),
            "separator": ",",
            "encoding": "utf-8",
            "append": "true",
        },
        "config": {
            "listVariable": "items",
            "outputPath": "{path}",
            "separator": "${separator}",
            "encoding": "{encoding}",
            "appendMode": "${append}",
        },
    }

    source_result = _source_result(payload)
    source_bytes = target.read_bytes()
    target.unlink()
    target_result = asyncio.run(_target_result(payload, _DirectTextWriter()))

    assert target_result == source_result
    assert target.read_bytes() == source_bytes == "一,二".encode()
    assert target_result["data"] == {"path": str(target), "count": 2}


def test_list_export_codec_failure_matches_frozen_webrpa(tmp_path: Path) -> None:
    target = tmp_path / "invalid-codec.txt"
    payload = {
        "type": "list_export",
        "variables": {"items": ["x"]},
        "config": {
            "listVariable": "items",
            "outputPath": str(target),
            "encoding": "not-a-codec",
        },
    }

    assert asyncio.run(_target_result(payload, _DirectTextWriter())) == _source_result(
        payload
    )
