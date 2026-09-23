"""Project-task admission and execution contract for the migrated B4 data family.

The frozen-source differential suite remains the authority for WebRPA behavior.
These tests reuse its successful payloads and verify that the project adapter does
not change their fields or outputs.  They deliberately stay below the browser and
process boundary so the project worker can later reuse the existing runtime.
"""

from __future__ import annotations

import copy
import importlib.util
import random
import subprocess
import sys
from pathlib import Path
from time import monotonic
from types import ModuleType
from typing import Any

import pytest

from autoflow.domain.workflows.catalog import node_catalog
from autoflow.domain.workflows.run_validation import prepare_run
from autoflow.providers.browser.project_graph import (
    ProjectGraphExecutor,
    _ProjectRegistry,
)
from tests.fixtures.workflows import workflow_payload

FIVE_NODE_BRIDGE = frozenset(
    {
        "open_page",
        "input_text",
        "click_element",
        "get_element_info",
        "screenshot",
    }
)


def _load_advanced_data_fixtures() -> ModuleType:
    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "differential"
        / "workflows"
        / "test_b4_advanced_data_executor_parity.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_autoflow_b4_advanced_data_fixtures", fixture_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载高级数据差分样例")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_FIXTURES = _load_advanced_data_fixtures()
ADVANCED_DATA_TYPES = frozenset(_FIXTURES.APPROVED_SOURCE_TYPES)


def _first_success_payloads() -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for payload in _FIXTURES.CASES:
        module_type = payload["type"]
        if module_type not in payloads:
            payloads[module_type] = copy.deepcopy(payload)
    if set(payloads) != ADVANCED_DATA_TYPES:
        raise RuntimeError("高级数据差分样例没有覆盖全部批准节点")
    return payloads


SUCCESS_PAYLOADS = _first_success_payloads()


def _advanced_document(payload: dict[str, Any]) -> dict[str, Any]:
    document = workflow_payload()
    document["content"]["nodes"] = [
        {
            "id": "advanced-data",
            "type": payload["type"],
            "position": {"x": 100, "y": 80},
            "data": {
                "label": payload["type"],
                "moduleType": payload["type"],
                **copy.deepcopy(payload["config"]),
            },
        }
    ]
    document["content"]["edges"] = []
    document["content"]["variables"] = [
        {
            "name": name,
            "value": copy.deepcopy(value),
            "type": _value_type(value),
            "scope": "global",
            "builtin": False,
        }
        for name, value in payload.get("variables", {}).items()
    ]
    return document


def _value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


@pytest.mark.parametrize("module_type", sorted(ADVANCED_DATA_TYPES))
def test_project_registry_reuses_each_advanced_data_executor(module_type: str) -> None:
    executor = _ProjectRegistry(None).get(module_type)

    assert executor is not None
    assert executor.module_type == module_type
    assert executor.requires_browser_for(SUCCESS_PAYLOADS[module_type]["config"]) is False


@pytest.mark.parametrize("module_type", sorted(ADVANCED_DATA_TYPES))
def test_project_admission_preserves_each_advanced_data_field(module_type: str) -> None:
    payload = SUCCESS_PAYLOADS[module_type]
    prepared = prepare_run(_advanced_document(payload))

    assert prepared.module_types == [module_type]
    prepared_data = prepared.document["content"]["nodes"][0]["data"]
    assert {
        key: prepared_data[key] for key in payload["config"]
    } == payload["config"]


@pytest.mark.asyncio
@pytest.mark.parametrize("module_type", sorted(ADVANCED_DATA_TYPES))
async def test_project_execution_matches_advanced_data_fixture_output(
    module_type: str,
) -> None:
    payload = copy.deepcopy(SUCCESS_PAYLOADS[module_type])
    expected = await _FIXTURES._target_result(payload)
    assert expected["success"], expected
    events: list[tuple[str, str, str, dict[str, object]]] = []

    async def emit(
        kind: str, node_id: str, visit: str, body: dict[str, object]
    ) -> None:
        events.append((kind, node_id, visit, body))

    random.seed(payload.get("seed", 8675309))
    executor = ProjectGraphExecutor(
        None,
        copy.deepcopy(payload.get("variables", {})),
        emit,
        lambda: False,
    )
    outcome = await executor.run(
        {
            "document": {
                "nodes": [
                    {
                        "id": "advanced-data",
                        "data": {
                            "moduleType": module_type,
                            **copy.deepcopy(payload["config"]),
                        },
                    }
                ],
                "edges": [],
            }
        }
    )

    assert outcome == {"status": "succeeded", "error": None}
    assert _FIXTURES._normalize(executor.context.variables) == expected["variables"]
    output_events = [event for event in events if event[0] == "output"]
    assert len(output_events) == 1
    assert output_events[0][1] == "advanced-data"
    assert output_events[0][3]["name"] == payload["config"]["resultVariable"]
    assert _FIXTURES._normalize(output_events[0][3]["value"]) == expected["data"]


def test_existing_five_node_bridge_remains_admitted() -> None:
    runnable = {
        item["moduleType"] for item in node_catalog() if item.get("runnable") is True
    }

    assert FIVE_NODE_BRIDGE <= runnable


def test_existing_project_chain_format_remains_compatible() -> None:
    prepared = prepare_run(workflow_payload())

    assert prepared.graph_adapter is False
    assert prepared.node_ids == ["open", "input", "click", "read"]
    assert prepared.module_types == [
        "open_page",
        "input_text",
        "click_element",
        "get_element_info",
    ]


@pytest.mark.asyncio
async def test_project_browser_result_does_not_publish_sensitive_variable() -> None:
    events: list[tuple[str, dict[str, object]]] = []

    async def emit(kind: str, _node_id: str, _visit: str, payload: dict[str, object]) -> None:
        events.append((kind, payload))

    executor = ProjectGraphExecutor(None, {"secret": "hidden"}, emit, lambda: False)
    executor.context.sensitive_variables.add("secret")
    executor.nodes = {
        "script": {"moduleType": "inject_javascript", "config": {"saveResult": "secret"}}
    }
    executor.started["visit"] = monotonic()
    await executor.publish({
        "type": "execution:node_complete", "nodeId": "script", "executionId": "visit",
        "success": True, "data": {"results": [{"result": "hidden"}]},
    })

    assert not any(kind == "output" for kind, _ in events)
    assert any(kind == "nodeAttempt" and payload["status"] == "succeeded" for kind, payload in events)


@pytest.mark.asyncio
async def test_project_graph_reuses_condition_loop_and_variable_executors() -> None:
    document = workflow_payload()
    document["content"]["schemaVersion"] = 3
    document["content"]["nodes"] = [
        {
            "id": node_id,
            "type": module_type,
            "position": {"x": index * 150, "y": 0},
            "data": {"moduleType": module_type, "config": config},
        }
        for index, (node_id, module_type, config) in enumerate(
            [
                ("gate", "condition", {"conditionType": "boolean", "leftValue": True}),
                ("repeat", "loop", {"loopType": "count", "loopCount": 3}),
                ("body", "set_variable", {"variableName": "last", "variableValue": "{index}"}),
                ("done", "set_variable", {"variableName": "finished", "variableValue": "完成"}),
                ("skipped", "set_variable", {"variableName": "skipped", "variableValue": "跳过"}),
            ]
        )
    ]
    document["content"]["edges"] = [
        {"id": "true", "source": "gate", "sourceHandle": "true", "target": "repeat"},
        {"id": "false", "source": "gate", "sourceHandle": "false", "target": "skipped"},
        {"id": "body", "source": "repeat", "sourceHandle": "loop", "target": "body"},
        {"id": "done", "source": "repeat", "sourceHandle": "done", "target": "done"},
    ]
    prepared = prepare_run(document)
    visits: list[tuple[str, str, str, dict[str, object]]] = []

    async def emit(kind: str, node_id: str, visit: str, body: dict[str, object]) -> None:
        visits.append((kind, node_id, visit, body))

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    outcome = await executor.run({"document": prepared.document["content"]})
    assert outcome == {"status": "succeeded", "error": None}, [item for item in visits if item[3].get("status") == "failed"]
    completed = [node_id for kind, node_id, _visit, data in visits if kind == "nodeAttempt" and data["status"] == "succeeded"]
    assert completed.count("gate") == completed.count("repeat") == completed.count("done") == 1
    assert completed.count("body") == 3
    assert "skipped" not in completed
    assert executor.context.variables["finished"] == "完成"


def test_core_runtime_and_bootstrap_import_in_fresh_process() -> None:
    subprocess.run(
        [sys.executable, "-c", "import autoflow.application.workflows.core_runtime; import autoflow.bootstrap.app"],
        check=True,
        capture_output=True,
        timeout=20,
    )


@pytest.mark.asyncio
async def test_project_graph_executes_canvas_subflow_body() -> None:
    document = workflow_payload()
    document["content"]["schemaVersion"] = 3
    document["content"]["nodes"] = [
        {"id": "definition", "type": "group", "position": {"x": 100, "y": 100},
         "data": {"moduleType": "group", "isSubflow": True, "subflowName": "组内流程", "width": 300, "height": 200}},
        {"id": "inner", "type": "set_variable", "position": {"x": 150, "y": 150},
         "data": {"moduleType": "set_variable", "config": {"variableName": "answer", "variableValue": "42"}}},
        {"id": "call", "type": "subflow", "position": {"x": 500, "y": 100},
         "data": {"moduleType": "subflow", "config": {"subflowGroupId": "definition", "subflowName": "组内流程"}}},
        {"id": "tail", "type": "set_variable", "position": {"x": 700, "y": 100},
         "data": {"moduleType": "set_variable", "config": {"variableName": "result", "variableValue": "{answer}"}}},
    ]
    document["content"]["edges"] = [
        {"id": "after-call", "source": "call", "target": "tail"}
    ]
    prepared = prepare_run(document)
    events: list[tuple[str, str, str, dict[str, object]]] = []

    async def emit(kind: str, node_id: str, visit: str, body: dict[str, object]) -> None:
        events.append((kind, node_id, visit, body))

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    outcome = await executor.run({"document": prepared.document["content"]})

    assert outcome == {"status": "succeeded", "error": None}
    completed = [node_id for kind, node_id, _visit, body in events if kind == "nodeAttempt" and body["status"] == "succeeded"]
    assert completed == ["inner", "call", "tail"]
    assert executor.context.variables["result"] == 42
