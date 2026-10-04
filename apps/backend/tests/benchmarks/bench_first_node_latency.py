"""From dispatch to the first node's start, through a real worker and CloakBrowser (M3 AC3-04).

Targets: a new worker with a new browser < 3 s; a pooled worker reusing its browser < 300 ms.

Run: uv run --directory apps/backend python -m tests.benchmarks.bench_first_node_latency \\
       --executable <CloakBrowser chrome executable>
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from autoflow.infrastructure.process.project_workflow_worker import ProjectWorkflowWorkerManager

from .report import Unit, build_manifest, write_report


def _plan() -> dict[str, Any]:
    node = {"id": "open", "data": {"moduleType": "open_page", "url": "about:blank", "timeout": 15}}
    return {"orderedNodeIds": ["open"], "nodes": [{"nodeId": "open", "moduleType": "open_page", "data": node["data"]}],
            "document": {"nodes": [node], "edges": [], "variables": []}}


def _browser(version: str) -> dict[str, Any]:
    return {
        "sessionId": str(uuid4()), "fingerprintSeed": 24680, "headless": True, "geoip": False, "humanize": False,
        "humanPreset": "default", "expertArgs": [], "extensionPaths": [], "locale": None, "timezone": None,
        "userAgent": None, "colorScheme": None, "licenseKey": None, "browserVersion": version,
        "releaseChannel": "stable", "proxy": None, "viewport": None,
    }


async def _first_node_ms(manager: ProjectWorkflowWorkerManager, executable: Path, version: str, key: str | None) -> float:
    started = time.perf_counter()
    first: list[float] = []

    async def record(events: list[dict[str, Any]]) -> None:
        if not first and any(event["kind"] == "nodeAttempt" for event in events):
            first.append((time.perf_counter() - started) * 1000)

    outcome = await manager.run(
        run_id=str(uuid4()), execution_generation=1, execution_plan=_plan(), parameters={}, variables={},
        browser=_browser(version), executable=executable,
        on_event=lambda event: record([event]), on_events=record, session_key=key,
    )
    if outcome.status != "succeeded" or not first:
        raise SystemExit(f"run did not reach its first node: {outcome}")
    return first[0]


async def run(executable: Path, samples: int) -> dict[str, tuple[float | None, Unit]]:
    version = next(parent.name for parent in executable.parents if parent.name.startswith("chromium-")).removeprefix("chromium-")
    with tempfile.TemporaryDirectory() as temporary:
        manager = ProjectWorkflowWorkerManager(Path(temporary) / "worker", start_timeout=60, capacity=1)
        try:
            fresh = [await _first_node_ms(manager, executable, version, None) for _ in range(samples)]
            await _first_node_ms(manager, executable, version, "bench")  # warms the pooled worker
            reused = [await _first_node_ms(manager, executable, version, "bench") for _ in range(samples)]
        finally:
            await manager.shutdown()
    return {
        "first_node_ms_new_browser": (statistics.median(fresh), "ms"),
        "first_node_ms_reused_browser": (statistics.median(reused), "ms"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=5)
    arguments = parser.parse_args()
    metrics = asyncio.run(run(arguments.executable.resolve(strict=True), arguments.samples))
    for name, (value, unit) in metrics.items():
        print(f"{name}: {value:.0f} {unit}")
    write_report("first-node-latency", metrics, manifest=build_manifest(
        "first-node-latency-v1", {"plan": "open_page about:blank"}, browser_kernel=arguments.executable.parent.name,
        repetitions=arguments.samples,
    ))


if __name__ == "__main__":
    main()
