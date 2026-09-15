from __future__ import annotations

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext


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
    assert context.variables == {"total": 3, "index": 3, "outcome": "passed"}


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
