"""Runtime framework overhead benchmark, golden scenario G4 (remediation M0, R0-02).

Run: uv run --directory apps/backend python -m tests.benchmarks.bench_runtime_overhead --iterations 1000
"""

from __future__ import annotations

import argparse
import asyncio
import time
from collections import Counter
from typing import Any

from autoflow.providers.browser.project_graph import ProjectGraphExecutor

from .report import Unit, build_manifest, write_report

WIDTH = 5


def _node(identity: str, kind: str, **config: Any) -> dict[str, Any]:
    return {"id": identity, "data": {"moduleType": kind, **config}}


def g4_document(iterations: int) -> dict[str, Any]:
    nodes = [_node("loop", "loop", count=iterations, indexVariable="i")] + [
        _node(f"s{k}", "set_variable", variableName=f"v{k}", variableValue="{i}")
        for k in range(WIDTH)
    ]
    edges = [
        {"id": "e-loop", "source": "loop", "target": "s0", "sourceHandle": "loop"}
    ] + [
        {"id": f"e{k}", "source": f"s{k}", "target": f"s{k + 1}"}
        for k in range(WIDTH - 1)
    ]
    return {"nodes": nodes, "edges": edges}


async def _run(iterations: int) -> dict[str, tuple[float | None, Unit]]:
    kinds: Counter[str] = Counter()
    completed: Counter[str] = Counter()

    async def emit(
        kind: str, node_id: str, _visit: str, payload: dict[str, Any]
    ) -> None:
        kinds[kind] += 1
        if (
            kind == "nodeAttempt"
            and payload.get("status") == "succeeded"
            and node_id.startswith("s")
        ):
            completed[node_id] += 1

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    started = time.perf_counter()
    result = await executor.run({"document": g4_document(iterations)})
    elapsed_ms = (time.perf_counter() - started) * 1000
    if result != {"status": "succeeded", "error": None}:
        raise RuntimeError(f"G4 did not succeed: {result}")
    if completed != {f"s{k}": iterations for k in range(WIDTH)}:
        raise RuntimeError(f"G4 workload incomplete: {dict(completed)}")
    nodes = sum(completed.values())
    return {
        "nodes_executed": (nodes, "count"),
        "framework_ms_per_node": (elapsed_ms / nodes, "ms"),
        "events_per_node": (sum(kinds.values()) / nodes, "per_node"),
    }


def run(iterations: int) -> dict[str, tuple[float | None, Unit]]:
    if iterations < 1:
        raise ValueError("iterations must be positive")
    return asyncio.run(_run(iterations))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1000)
    arguments = parser.parse_args()
    manifest = build_manifest(
        "runtime-overhead-v1", {"iterations": arguments.iterations}
    )
    write_report(
        "runtime-overhead",
        run(arguments.iterations),
        manifest=manifest,
    )


if __name__ == "__main__":
    main()
