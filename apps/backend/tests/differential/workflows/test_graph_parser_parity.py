from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from autoflow.domain.workflows.graph import ExecutionGraph, parse_workflow

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference/WebRPA/backend"


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


def _normalized(graph: ExecutionGraph) -> dict[str, Any]:
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
    }


def _frozen_output(document: dict[str, Any]) -> dict[str, Any]:
    frozen_document = json.loads(json.dumps(document))
    for node in frozen_document["nodes"]:
        node["type"] = node.get("data", {}).get("moduleType", node.get("type", ""))
    script = """
import json, sys
from app.services.workflow_parser import parse_workflow
document = json.load(sys.stdin)
_, graph = parse_workflow(document)
node_ids = list(graph.nodes)
json.dump({
    'nodes': node_ids,
    'start': graph.get_start_nodes(),
    'isolated': graph.isolated_nodes,
    'adjacency': {node_id: graph.get_next_nodes(node_id) for node_id in node_ids},
    'reverse': {node_id: graph.get_prev_nodes(node_id) for node_id in node_ids},
    'join': {node_id: graph.get_join_prev_nodes(node_id) for node_id in node_ids},
    'condition': graph.condition_branches,
    'loop': graph.loop_branches,
    'error': graph.error_branches,
}, sys.stdout, ensure_ascii=False)
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(FROZEN_BACKEND)
    process = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps(frozen_document, ensure_ascii=False),
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    return json.loads(process.stdout)


@pytest.mark.parametrize(
    "nodes,edges",
    [
        ([_node("a"), _node("b"), _node("c")], [_edge("a", "b"), _edge("b", "c")]),
        (
            [_node("condition", "condition"), _node("yes"), _node("no")],
            [
                _edge("condition", "yes", "true"),
                _edge("condition", "yes", "true"),
                _edge("condition", "no", "false"),
            ],
        ),
        (
            [_node("loop", "loop"), _node("body"), _node("done")],
            [_edge("loop", "body", "loop-body"), _edge("loop", "done", "loop-done")],
        ),
        (
            [_node("a"), _node("b"), _node("handler")],
            [_edge("a", "b"), _edge("b", "handler"), _edge("handler", "b", "error")],
        ),
        (
            [_node("start"), _node("end"), _node("forgotten"), _node("group", "group")],
            [_edge("start", "end")],
        ),
    ],
    ids=["linear", "condition-dedup", "loop-alias", "error-backflow", "isolated-visual"],
)
def test_autoflow_graph_matches_frozen_webrpa(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> None:
    document = {
        "id": "parity",
        "name": "差分",
        "nodes": nodes,
        "edges": edges,
        "variables": [],
    }

    _, graph = parse_workflow(document)

    assert _normalized(graph) == _frozen_output(document)
    assert all(node.raw["type"] == "moduleNode" for node in graph.nodes.values())


def test_validation_reports_the_same_structural_failures() -> None:
    document = {
        "id": "invalid",
        "name": "错误图",
        "nodes": [_node("condition", "condition")],
        "edges": [_edge("condition", "missing")],
        "variables": [],
    }

    workflow, _ = parse_workflow(document)
    ok, errors = workflow.validate()

    assert ok is False
    assert errors == (
        "边的目标节点不存在: missing",
        "条件节点 'condition' (condition) 没有任何输出分支",
    )
