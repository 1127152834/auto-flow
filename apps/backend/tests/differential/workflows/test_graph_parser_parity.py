from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from autoflow.domain.workflows.graph import ExecutionGraph, parse_workflow

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference/WebRPA/backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_graph_parser_harness.py")


def _node(node_id: str, node_type: str = "print_log") -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "moduleNode",
        "position": {"x": 0, "y": 0},
        "data": {"moduleType": node_type, "label": node_id},
    }


def _edge(source: str, target: str, handle: str | None = None) -> dict[str, Any]:
    edge: dict[str, Any] = {
        "id": f"e-{source}-{target}-{handle or 'plain'}",
        "source": source,
        "target": target,
    }
    if handle is not None:
        edge["sourceHandle"] = handle
    return edge


def _normalized(
    graph: ExecutionGraph, validation: tuple[bool, tuple[str, ...]]
) -> dict[str, Any]:
    node_ids = list(graph.nodes)
    return {
        "nodes": node_ids,
        "start": graph.get_start_nodes(),
        "isolated": graph.isolated_nodes,
        "adjacency": {node_id: graph.get_next_nodes(node_id) for node_id in node_ids},
        "reverse": {node_id: graph.get_prev_nodes(node_id) for node_id in node_ids},
        "join": {node_id: graph.get_join_prev_nodes(node_id) for node_id in node_ids},
        "condition": graph.condition_branches,
        "loop": graph.loop_branches,
        "error": graph.error_branches,
        "validation": {"ok": validation[0], "errors": list(validation[1])},
    }


def _frozen_output(document: dict[str, Any]) -> dict[str, Any]:
    frozen_document = json.loads(json.dumps(document))
    for node in frozen_document["nodes"]:
        node["type"] = node.get("data", {}).get("moduleType", node.get("type", ""))
    process = subprocess.run(
        [sys.executable, "-X", "utf8", str(FROZEN_HARNESS), str(FROZEN_BACKEND)],
        input=json.dumps(frozen_document, ensure_ascii=False),
        text=True, encoding="utf-8",
        capture_output=True,
        check=True,
    )
    return json.loads(process.stdout)


def _parity(document: dict[str, Any]) -> dict[str, Any]:
    original = json.loads(json.dumps(document))
    workflow, graph = parse_workflow(document)
    actual = _normalized(graph, workflow.validate())
    assert actual == _frozen_output(document)
    assert document == original
    assert all(node.raw["type"] == "moduleNode" for node in graph.nodes.values())
    return actual


@pytest.mark.parametrize(
    "nodes,edges,expected_starts",
    [
        ([_node("a"), _node("b")], [], ["a", "b"]),
        (
            [_node("a"), _node("b"), _node("c"), _node("d")],
            [_edge("a", "b"), _edge("c", "d")],
            ["a", "c"],
        ),
        (
            [_node("condition", "condition"), _node("yes"), _node("no")],
            [
                _edge("condition", "yes", "true"),
                _edge("condition", "yes", "true"),
                _edge("condition", "no", "false"),
            ],
            ["condition"],
        ),
        (
            [_node("start"), _node("end"), _node("forgotten"), _node("group", "group")],
            [_edge("start", "end")],
            ["start"],
        ),
    ],
    ids=["unconnected", "multiple-starts", "condition-dedup", "isolated-visual"],
)
def test_autoflow_graph_matches_frozen_webrpa(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    expected_starts: list[str],
) -> None:
    document = {
        "id": "parity",
        "name": "差分",
        "nodes": nodes,
        "edges": edges,
        "variables": [],
    }

    snapshot = _parity(document)

    assert snapshot["start"] == expected_starts


def test_condition_and_error_edges_stay_out_of_normal_adjacency() -> None:
    document = {
        "id": "branches",
        "name": "条件与错误边",
        "nodes": [
            _node("condition", "condition"),
            _node("yes"),
            _node("no"),
            _node("handler"),
        ],
        "edges": [
            _edge("condition", "yes", "true"),
            _edge("condition", "no", "false"),
            _edge("yes", "handler", "error"),
        ],
        "variables": [],
    }

    snapshot = _parity(document)

    assert snapshot["adjacency"] == {
        "condition": [],
        "yes": [],
        "no": [],
        "handler": [],
    }
    assert snapshot["condition"] == {
        "condition": {"true": ["yes"], "false": ["no"]}
    }
    assert snapshot["error"] == {"yes": ["handler"]}
    assert snapshot["join"]["handler"] == []


def test_diamond_join_keeps_both_normal_predecessors() -> None:
    document = {
        "id": "join",
        "name": "汇合",
        "nodes": [_node("start"), _node("left"), _node("right"), _node("join")],
        "edges": [
            _edge("start", "left"),
            _edge("start", "right"),
            _edge("left", "join"),
            _edge("right", "join"),
        ],
        "variables": [],
    }

    snapshot = _parity(document)

    assert snapshot["join"]["join"] == ["left", "right"]


def test_error_reentry_preserves_the_real_start_and_is_not_a_join_dependency() -> None:
    document = {
        "id": "error-reentry",
        "name": "错误回流",
        "nodes": [_node("entry"), _node("step")],
        "edges": [_edge("entry", "step"), _edge("step", "entry", "error")],
        "variables": [],
    }

    snapshot = _parity(document)

    assert snapshot["start"] == ["entry"]
    assert snapshot["error"] == {"step": ["entry"]}
    assert snapshot["join"]["entry"] == []


def test_loop_back_edge_is_excluded_from_join_predecessors() -> None:
    document = {
        "id": "loop-back-edge",
        "name": "合法循环回边",
        "nodes": [
            _node("entry"),
            _node("loop", "loop"),
            _node("body"),
            _node("done"),
        ],
        "edges": [
            _edge("entry", "loop"),
            _edge("loop", "body", "loop-body"),
            _edge("body", "loop"),
            _edge("loop", "done", "loop-done"),
        ],
        "variables": [],
    }

    snapshot = _parity(document)

    assert snapshot["loop"] == {"loop": {"loop": ["body"], "done": ["done"]}}
    assert snapshot["reverse"]["loop"] == ["entry", "body"]
    assert snapshot["join"]["loop"] == ["entry"]


def test_plain_cycle_has_no_start_and_fails_frozen_validation() -> None:
    document = {
        "id": "illegal-cycle",
        "name": "非法回环",
        "nodes": [_node("a"), _node("b")],
        "edges": [_edge("a", "b"), _edge("b", "a")],
        "variables": [],
    }

    snapshot = _parity(document)

    assert snapshot["start"] == []
    assert snapshot["validation"] == {
        "ok": False,
        "errors": ["工作流没有起始节点（所有节点都有入边，可能存在循环）"],
    }


def test_empty_workflow_fails_frozen_validation() -> None:
    snapshot = _parity(
        {"id": "empty", "name": "空流程", "nodes": [], "edges": [], "variables": []}
    )

    assert snapshot["validation"] == {
        "ok": False,
        "errors": ["工作流没有任何节点"],
    }


def test_validation_reports_the_same_structural_failures() -> None:
    document = {
        "id": "invalid",
        "name": "错误图",
        "nodes": [_node("condition", "condition")],
        "edges": [_edge("condition", "missing")],
        "variables": [],
    }

    snapshot = _parity(document)

    assert snapshot["validation"] == {
        "ok": False,
        "errors": [
            "边的目标节点不存在: missing",
            "条件节点 'condition' (condition) 没有任何输出分支",
        ],
    }
