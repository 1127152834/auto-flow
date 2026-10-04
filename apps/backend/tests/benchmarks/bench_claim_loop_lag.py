"""Loop lag microbenchmark for a threaded SQLite claim (remediation M1, AC1-09).

Run: uv run --directory apps/backend python -m tests.benchmarks.bench_claim_loop_lag --rows 10000
"""

from __future__ import annotations

import argparse
import asyncio
import tempfile
import time
from pathlib import Path

from autoflow.domain.project_runs.input_selection import candidate_page_sizes
from autoflow.infrastructure.database.project_claims import SqlAlchemyProjectInputGroups
from autoflow.infrastructure.observability import LoopLagMonitor

from .bench_claims import _seed, plans
from .report import Unit, build_manifest, write_report

HEARTBEAT_SECONDS = 0.005


async def _run(rows: int, threaded: bool) -> dict[str, tuple[float, Unit]]:
    with tempfile.TemporaryDirectory() as raw:
        factory, project_id, table, field = _seed(Path(raw), rows)
        plan = plans(project_id, table, field)["claim_ms_key_order"]

        def claim() -> str:
            with factory() as session:
                # The scheduler's candidate page for a batch with concurrency 2 (M3 R3-02).
                return SqlAlchemyProjectInputGroups(session).select_required(
                    project_id, plan, candidate_page_sizes=candidate_page_sizes(plan, 2)
                ).status

        monitor = LoopLagMonitor(interval=HEARTBEAT_SECONDS)
        await monitor.start()
        try:
            started = time.perf_counter()
            # The synchronous control runs the very same claim on the loop thread.
            status = await asyncio.to_thread(claim) if threaded else claim()
            elapsed_ms = (time.perf_counter() - started) * 1000
            # Record the first heartbeat after completion, including a delayed one.
            previous_samples = monitor.snapshot().samples
            while monitor.snapshot().samples == previous_samples:
                await asyncio.sleep(0.001)
            snapshot = monitor.snapshot()
        finally:
            await monitor.stop()
            factory.dispose()
    if status != "ready":
        raise RuntimeError(f"unexpected selection status {status}")
    return {
        "rows": (rows, "count"),
        "claim_ms": (elapsed_ms, "ms"),
        "loop_lag_p50_ms": (snapshot.p50_ms, "ms"),
        "loop_lag_max_ms": (snapshot.max_ms, "ms"),
        "loop_lag_samples": (snapshot.samples, "count"),
    }


def run(rows: int, *, threaded: bool = True) -> dict[str, tuple[float, Unit]]:
    return asyncio.run(_run(rows, threaded))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=10000)
    arguments = parser.parse_args()
    results = {}
    for mode, threaded in (("sync-control", False), ("threaded", True)):
        manifest = build_manifest(
            "claim-loop-lag-v1", {"rows": arguments.rows},
            execution_profile=f"offline-{mode}-claim-v1",
        )
        results[mode] = run(arguments.rows, threaded=threaded)
        write_report(f"claim-loop-lag-{mode}-{arguments.rows}", results[mode], manifest=manifest)
    for mode, metrics in results.items():
        print(mode, {name: round(value, 3) for name, (value, _) in metrics.items()})
    metrics = results["threaded"]
    # The synchronous control is recorded only; AC1-09 applies to the threaded path.
    assert metrics["loop_lag_samples"][0] > 0
    assert metrics["loop_lag_p50_ms"][0] < 10, metrics["loop_lag_p50_ms"]
    assert metrics["loop_lag_max_ms"][0] < 250, metrics["loop_lag_max_ms"]


if __name__ == "__main__":
    main()
