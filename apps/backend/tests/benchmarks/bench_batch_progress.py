"""Batch progress aggregation benchmark (remediation M5 5B-A4, B7).

Seeds one batch with ``--rows`` processing units (and one task each), then times the progress aggregation
in a worker thread while the event-loop heartbeat runs, so the loop lag it causes is measured as well.

Budget: median 110-190 ms and slowest-of-30 140-600 ms at 10,000 rows on the dev machine (Windows, SQLite);
the 2000 ms default is 3-4x the worst slowest call, leaving room for slow CI machines.
The budget applies to the slowest of the 30 calls, not to a multiple of the median: one cold or GC-hit call must
still pass, while a real regression (per-row queries) is orders of magnitude slower.
The loop_lag p50 bound (25 ms) is looser than the 10 ms target for idle loops because the worker thread holds the
GIL while it builds the result; the max bound (250 ms) is what catches a blocked loop.

Run: uv run --directory apps/backend python -m tests.benchmarks.bench_batch_progress --rows 10000
"""

from __future__ import annotations

import argparse
import asyncio
import os
import tempfile
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from autoflow.application.project_runs.progress import BatchProgressService
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.record_ledger_models import (
    AutomationRecordLedgerRow,
    ProjectBatchUnitRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from autoflow.infrastructure.observability import LoopLagMonitor
from tests.integration.test_project_run_data_start import _setup, uid

from .report import Unit, build_manifest, write_report

CALLS = 30
RUNNING = 100
HEARTBEAT_SECONDS = 0.005
FAILURES = (("page", "WORKFLOW_NODE_FAILED"), ("business", "END_BUSINESS_FAILED"), ("infrastructure", "BROWSER_LOST"))


def _columns(row) -> dict:
    return {column.name: getattr(row, column.key) for column in row.__table__.columns}


def _seed(directory: Path, rows: int):
    if rows < 1:
        raise ValueError("rows must be positive")
    factory, project_id, automation, coordinator = _setup(directory)
    batch, _operation, _replayed = coordinator.start(
        project_id, automation.automation_id, uid(),
        {"expectedAutomationRevision": automation.management_revision, "parameters": {}, "maxTasks": 1, "concurrency": 1},
    )
    if ProjectBatchScheduler.claim_data_task(factory, project_id, batch.batch_id) != "ready":
        raise RuntimeError("the seed batch could not claim its first task")
    now = datetime.now(UTC)
    plan = automation.input_plan
    first = plan["inputs"][0]
    with factory.begin() as session:
        # Start requests allow 1-100 tasks; the batch is then widened so the ETA path is exercised too.
        stored = session.get(ProjectBatchRow, batch.batch_id)
        stored.frozen_request = {**stored.frozen_request, "maxTasks": rows}
        task = session.scalars(select(ProjectTaskRow)).one()
        run = session.get(WorkflowRunRow, task.run_id)
        snapshot = session.scalars(select(ProjectTaskInputSnapshotRow)).one()
        task_cols, run_cols, snapshot_cols = _columns(task), _columns(run), _columns(snapshot)
        ledgers, units, runs, tasks, snapshots = [], [], [], [], []
        for index in range(1, rows):
            running = index <= RUNNING
            failed = not running and index % 25 == 0
            outcome, code = FAILURES[index % len(FAILURES)]
            run_id, task_id, ledger_id = uid(), uid(), uid()
            runs.append({
                **run_cols, "id": run_id, "run_request_id": uid(), "status": "running" if running else "failed" if failed else "succeeded",
                "started_at": now - timedelta(minutes=10, seconds=index % 60),
                "completed_at": None if running else now - timedelta(seconds=index % 280),
            })
            tasks.append({**task_cols, "id": task_id, "run_id": run_id, "run_request_id": uid(), "ordinal": index + 1})
            snapshots.append({**snapshot_cols, "id": uid(), "task_id": task_id})
            ledgers.append({
                "id": ledger_id, "automation_id": automation.automation_id, "processing_input_id": plan["processingInputId"],
                "project_id": project_id, "table_id": first["tableId"], "dataset_generation": first["datasetGeneration"],
                "key_type": "uuid", "key_value": str(uuid.UUID(int=index + 1)), "identity_namespace": "",
                "state": "pending" if running else "failed_retryable" if failed else "succeeded",
                "attempts": 1, "processing_cycle": 1, "cycle_attempts": 1,
                "last_outcome": outcome if failed else None,
                "last_error": {"code": code, "message": f"节点执行失败 {index}"} if failed else None,
                "revision": 1, "created_at": now, "updated_at": now,
            })
            units.append({"id": uid(), "batch_id": batch.batch_id, "ledger_id": ledger_id, "first_task_id": task_id, "created_at": now})
        for model, values in (
            (WorkflowRunRow, runs), (ProjectTaskRow, tasks), (ProjectTaskInputSnapshotRow, snapshots),
            (AutomationRecordLedgerRow, ledgers), (ProjectBatchUnitRow, units),
        ):
            for start in range(0, len(values), 1000):
                session.execute(model.__table__.insert(), values[start : start + 1000])
    return factory, project_id, batch.batch_id


async def _run(rows: int) -> dict[str, tuple[float, Unit]]:
    with tempfile.TemporaryDirectory() as raw:
        factory, project_id, batch_id = _seed(Path(raw), rows)
        service = BatchProgressService(factory)
        monitor = LoopLagMonitor(interval=HEARTBEAT_SECONDS)
        await monitor.start()
        samples: list[float] = []
        try:
            for _ in range(CALLS):
                started = time.perf_counter()
                body = await asyncio.to_thread(service.progress, project_id, batch_id)  # the route's own path
                samples.append((time.perf_counter() - started) * 1000)
            snapshot = monitor.snapshot()
        finally:
            await monitor.stop()
            factory.dispose()
    if body["ledger"]["total"] != rows or len(body["runningTasks"]) != min(RUNNING + 1, 50):
        raise RuntimeError(f"unexpected progress body: {body['ledger']}, {len(body['runningTasks'])} running")
    ordered = sorted(samples)
    return {
        "rows": (rows, "count"),
        "progress_ms_p50": (ordered[len(ordered) // 2], "ms"),
        "progress_ms_p99": (ordered[-1], "ms"),  # the slowest of CALLS calls
        "loop_lag_p50_ms": (snapshot.p50_ms, "ms"),
        "loop_lag_max_ms": (snapshot.max_ms, "ms"),
        "loop_lag_samples": (snapshot.samples, "count"),
    }


def run(rows: int) -> dict[str, tuple[float, Unit]]:
    return asyncio.run(_run(rows))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=10000)
    parser.add_argument("--budget-ms", type=float, default=2000, help="fail when the slowest of 30 calls is slower")
    arguments = parser.parse_args()
    metrics = run(arguments.rows)
    write_report(
        f"batch-progress-{arguments.rows}", metrics,
        manifest=build_manifest("batch-progress-v1", {"rows": arguments.rows}, execution_profile="offline-threaded-progress-v1"),
    )
    print({name: round(value, 3) for name, (value, _) in metrics.items()})
    # The worker thread holds the GIL for stretches while it builds the result, so the p50 bound is looser than for a 10 ms claim.
    assert metrics["loop_lag_p50_ms"][0] < 25, metrics["loop_lag_p50_ms"]
    assert metrics["loop_lag_max_ms"][0] < 250, metrics["loop_lag_max_ms"]
    slowest = metrics["progress_ms_p99"][0]
    if arguments.budget_ms is not None and slowest > arguments.budget_ms:
        message = f"batch progress budget {arguments.budget_ms} ms exceeded: {slowest:.1f} ms"
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title=batch progress budget::{message}")
        raise SystemExit(message)


if __name__ == "__main__":
    main()
