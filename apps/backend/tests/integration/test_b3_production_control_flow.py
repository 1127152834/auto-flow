from __future__ import annotations

from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext


class _EventSink:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def publish(self, event: dict[str, Any]) -> None:
        self.events.append(event)


def _node(
    node_id: str, module_type: str, config: dict[str, object]
) -> dict[str, object]:
    return {
        "id": node_id,
        "type": "moduleNode",
        "data": {"moduleType": module_type, "config": config},
    }


def _edge(
    edge_id: str, source: str, target: str, handle: str | None = None
) -> dict[str, object]:
    value: dict[str, object] = {"id": edge_id, "source": source, "target": target}
    if handle is not None:
        value["sourceHandle"] = handle
    return value


@pytest.mark.asyncio
async def test_production_registry_runs_variable_loop_and_condition_as_one_graph() -> (
    None
):
    document = {
        "id": "b3-production-control-flow",
        "name": "B3 production control flow",
        "nodes": [
            _node(
                "initialize",
                "set_variable",
                {"variableName": "total", "variableValue": "0"},
            ),
            _node("repeat", "loop", {"loopCount": 3, "indexVariable": "index"}),
            _node(
                "increment",
                "increment_decrement",
                {"variableName": "total", "operation": "increment", "step": 1},
            ),
            _node(
                "condition",
                "condition",
                {"leftValue": "{total}", "operator": "==", "rightValue": "3"},
            ),
            _node(
                "passed",
                "set_variable",
                {"variableName": "outcome", "variableValue": "passed"},
            ),
            _node(
                "failed",
                "set_variable",
                {"variableName": "outcome", "variableValue": "failed"},
            ),
        ],
        "edges": [
            _edge("initialize-repeat", "initialize", "repeat"),
            _edge("repeat-body", "repeat", "increment", "loop"),
            _edge("repeat-done", "repeat", "condition", "done"),
            _edge("condition-true", "condition", "passed", "true"),
            _edge("condition-false", "condition", "failed", "false"),
        ],
        "variables": [],
    }
    context = ExecutionContext()

    result = await WorkflowRuntime(build_production_executor_registry()).execute(
        document, context
    )

    assert result.success is True
    assert result.executed_node_ids == (
        "initialize",
        "repeat",
        "increment",
        "increment",
        "increment",
        "condition",
        "passed",
    )
    assert context.variables == {"total": 3, "outcome": "passed"}


@pytest.mark.asyncio
async def test_production_runtime_completes_one_thousand_iterations_with_distinct_contexts() -> None:
    document = {
        "nodes": [
            _node("repeat", "loop", {"loopCount": 1_000, "indexVariable": "index"}),
            _node("body", "set_variable", {"variableName": "value", "variableValue": "{index}"}),
            _node("done", "set_variable", {"variableName": "completed", "variableValue": "完成"}),
        ],
        "edges": [
            _edge("repeat-body", "repeat", "body", "loop"),
            _edge("repeat-done", "repeat", "done", "done"),
        ],
        "variables": [],
    }
    sink = _EventSink()
    context = ExecutionContext(events=sink)

    result = await WorkflowRuntime(build_production_executor_registry()).execute(document, context)

    starts = [event for event in sink.events if event["type"] == "execution:node_start" and event["nodeId"] == "body"]
    assert result.success is True
    assert len(starts) == 1_000
    assert len({event["executionId"] for event in starts}) == 1_000
    assert [starts[0]["executionContext"]["loops"][0]["iteration"], starts[-1]["executionContext"]["loops"][0]["iteration"]] == [1, 1_000]
    assert context.variables == {"value": 999, "completed": "完成"}


@pytest.mark.asyncio
async def test_debug_tracking_records_loop_local_entry_updates_and_scope_exit() -> None:
    document = {
        "nodes": [
            _node(
                "repeat",
                "foreach",
                {
                    "dataSource": "items",
                    "itemVariable": "item",
                    "indexVariable": "index",
                },
            ),
            _node(
                "body",
                "set_variable",
                {"variableName": "seen", "variableValue": "{item}"},
            ),
        ],
        "edges": [_edge("repeat-body", "repeat", "body", "loop")],
        "variables": [],
    }
    sink = _EventSink()
    context = ExecutionContext(
        variables={"items": ["甲", "乙"], "index": 99},
        events=sink,
        variable_tracking_enabled=True,
    )

    result = await WorkflowRuntime(build_production_executor_registry()).execute(
        document, context
    )

    changes = [
        event
        for event in sink.events
        if event["type"] == "execution:variable_changed"
        and event["nodeId"] == "repeat"
    ]
    index_changes = [event for event in changes if event["variable_name"] == "index"]
    item_changes = [event for event in changes if event["variable_name"] == "item"]
    assert result.success is True
    assert context.variables == {"items": ["甲", "乙"], "index": 99, "seen": "乙"}
    assert [(event["operation"], event["new_value"]) for event in index_changes] == [
        ("update", 0),
        ("update", 1),
        ("update", 2),
        ("scope_exit", 99),
    ]
    assert [(event["operation"], event["new_value"]) for event in item_changes] == [
        ("create", "甲"),
        ("update", "乙"),
        ("scope_exit", None),
    ]
    assert index_changes[1]["executionId"] == item_changes[1]["executionId"]
    assert index_changes[-1]["executionId"] == item_changes[-1]["executionId"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module_type", "config", "variables", "local_names"),
    [
        ("loop", {"loopCount": 0, "indexVariable": "slot"}, {}, {"slot"}),
        (
            "loop",
            {
                "loopType": "range",
                "startValue": 2,
                "endValue": 1,
                "stepValue": 1,
                "indexVariable": "slot",
            },
            {},
            {"slot"},
        ),
        (
            "loop",
            {"loopType": "while", "condition": "false", "indexVariable": "slot"},
            {},
            {"slot"},
        ),
        (
            "foreach",
            {
                "dataSource": "items",
                "itemVariable": "item",
                "indexVariable": "slot",
            },
            {"items": ["甲"]},
            {"slot", "item"},
        ),
        (
            "foreach_dict",
            {
                "dictVariable": "mapping",
                "keyVariable": "key",
                "valueVariable": "value",
                "indexVariable": "slot",
            },
            {"mapping": {"甲": 1}},
            {"slot", "key", "value"},
        ),
        ("infinite_loop", {"indexVariable": "slot"}, {}, {"slot"}),
    ],
)
async def test_each_loop_family_restores_outer_local_values(
    module_type: str,
    config: dict[str, object],
    variables: dict[str, object],
    local_names: set[str],
) -> None:
    initial = {**variables, **{name: f"outer-{name}" for name in local_names}}
    nodes = [_node("repeat", module_type, config)]
    edges: list[dict[str, object]] = []
    if module_type == "infinite_loop":
        nodes.append(_node("break", "break_loop", {}))
        edges.append(_edge("repeat-break", "repeat", "break", "loop"))
    sink = _EventSink()
    context = ExecutionContext(
        variables=initial.copy(), events=sink, variable_tracking_enabled=True
    )

    result = await WorkflowRuntime(build_production_executor_registry()).execute(
        {"nodes": nodes, "edges": edges, "variables": []}, context
    )

    exits = [
        event
        for event in sink.events
        if event["type"] == "execution:variable_changed"
        and event["operation"] == "scope_exit"
    ]
    assert result.success is True
    assert context.variables == initial
    assert {event["variable_name"] for event in exits} == local_names
    assert {event["new_value"] for event in exits} == {
        f"outer-{name}" for name in local_names
    }


@pytest.mark.asyncio
async def test_production_break_stops_only_the_current_loop_body() -> None:
    document = {
        "id": "b3-production-break",
        "name": "B3 production break",
        "nodes": [
            _node("repeat", "loop", {"loopCount": 100}),
            _node("break", "break_loop", {}),
            _node(
                "must-not-run",
                "set_variable",
                {"variableName": "wrong", "variableValue": "1"},
            ),
            _node(
                "done", "set_variable", {"variableName": "done", "variableValue": "1"}
            ),
        ],
        "edges": [
            _edge("repeat-body", "repeat", "break", "loop"),
            _edge("repeat-done", "repeat", "done", "done"),
            _edge("break-next", "break", "must-not-run"),
        ],
        "variables": [],
    }
    context = ExecutionContext()

    result = await WorkflowRuntime(build_production_executor_registry()).execute(
        document, context
    )

    assert result.success is True
    assert result.executed_node_ids == ("repeat", "break", "done")
    assert "wrong" not in context.variables
    assert context.variables["done"] == 1
    assert context.loop_stack == []


@pytest.mark.asyncio
async def test_production_while_loop_re_evaluates_the_resolved_expression() -> None:
    document = {
        "id": "b3-production-while",
        "name": "B3 production while",
        "nodes": [
            _node(
                "initialize",
                "set_variable",
                {"variableName": "total", "variableValue": "0"},
            ),
            _node("repeat", "loop", {"loopType": "while", "condition": "{total} < 3"}),
            _node(
                "increment",
                "increment_decrement",
                {"variableName": "total", "operation": "increment", "step": 1},
            ),
            _node(
                "done", "set_variable", {"variableName": "done", "variableValue": "1"}
            ),
        ],
        "edges": [
            _edge("initialize-repeat", "initialize", "repeat"),
            _edge("repeat-body", "repeat", "increment", "loop"),
            _edge("repeat-done", "repeat", "done", "done"),
        ],
        "variables": [],
    }
    context = ExecutionContext()

    result = await WorkflowRuntime(build_production_executor_registry()).execute(
        document, context
    )

    assert result.success is True
    assert result.executed_node_ids.count("increment") == 3
    assert context.variables["total"] == 3
    assert context.variables["done"] == 1
    assert "index" not in context.variables


@pytest.mark.parametrize(
    ("module_type", "config"),
    [
        ("condition", {"conditionType": "element_visible"}),
        ("wait", {"waitType": "selector"}),
        ("wait", {"waitType": "navigation"}),
        ("assert_checkpoint", {"checkType": "element"}),
    ],
)
def test_browser_backed_control_modes_request_cloakbrowser(
    module_type: str, config: dict[str, object]
) -> None:
    document = {
        "nodes": [_node("node", module_type, config)],
        "edges": [],
        "variables": [],
    }

    assert WorkflowRuntime(build_production_executor_registry()).requires_browser(
        document
    )


@pytest.mark.asyncio
async def test_visual_group_and_note_are_registered_but_not_dispatched() -> None:
    document = {
        "nodes": [
            _node("group", "group", {}),
            _node("note", "note", {}),
            _node(
                "work", "set_variable", {"variableName": "done", "variableValue": "1"}
            ),
        ],
        "edges": [],
        "variables": [],
    }
    context = ExecutionContext()

    result = await WorkflowRuntime(build_production_executor_registry()).execute(
        document, context
    )

    assert result.success is True
    assert result.executed_node_ids == ("work",)
    assert context.variables["done"] == 1
