from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _snapshot(document: dict[str, Any], frozen_backend: Path) -> dict[str, Any]:
    sys.path.insert(0, str(frozen_backend))
    from app.services.workflow_parser import WorkflowParser, parse_workflow

    workflow, graph = parse_workflow(document)
    ok, errors = WorkflowParser().validate(workflow)
    node_ids = list(graph.nodes)
    return {
        "nodes": node_ids,
        "start": graph.get_start_nodes(),
        "isolated": graph.isolated_nodes,
        "adjacency": {
            node_id: graph.get_next_nodes(node_id) for node_id in node_ids
        },
        "reverse": {node_id: graph.get_prev_nodes(node_id) for node_id in node_ids},
        "join": {
            node_id: graph.get_join_prev_nodes(node_id) for node_id in node_ids
        },
        "condition": graph.condition_branches,
        "loop": graph.loop_branches,
        "error": graph.error_branches,
        "validation": {"ok": ok, "errors": errors},
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: frozen_graph_parser_harness.py FROZEN_BACKEND")
    document = json.load(sys.stdin)
    snapshot = _snapshot(document, Path(sys.argv[1]))
    json.dump(snapshot, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
