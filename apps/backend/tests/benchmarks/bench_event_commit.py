"""Run-event commit latency benchmark (remediation M0, R0-03).

Run: uv run --directory apps/backend python -m tests.benchmarks.bench_event_commit --events 1000
"""

from __future__ import annotations

import argparse
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from tests.fixtures.workflow_runs import create_queued_run

from .report import Unit, build_manifest, write_report


def _percentile(ordered: list[float], fraction: float) -> float:
    return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))]


def run(events: int) -> dict[str, tuple[float | None, Unit]]:
    if events < 1:
        raise ValueError("events must be positive")
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "events.sqlite3"
        migrate_database(path)
        factory = create_session_factory(path)
        try:
            run_row, _content = create_queued_run(factory)
            samples: list[float] = []
            for index in range(events):
                event = {
                    "eventId": str(uuid4()),
                    "runId": run_row.run_id,
                    "executionGeneration": 0,
                    "kind": "log",
                    "nodeId": "open",
                    "nodeVisitId": "visit-1",
                    "attempt": 1,
                    "occurredAt": datetime.now(UTC).isoformat(),
                    "payload": {"level": "info", "message": f"benchmark {index}"},
                }
                started = time.perf_counter()
                with factory.begin() as session:
                    SqlAlchemyWorkflowRuntimeRepository(session).append_event(event)
                samples.append((time.perf_counter() - started) * 1000)
            with factory() as session:
                persisted = SqlAlchemyWorkflowRuntimeRepository(session).list_events(
                    run_row.run_id,
                    after_sequence=0,
                    limit=events + 1,
                )
            if len(persisted) != events:
                raise RuntimeError(
                    f"Expected {events} durable events, got {len(persisted)}"
                )
        finally:
            factory.dispose()
    samples.sort()
    return {
        "events": (events, "count"),
        "event_commit_ms_p50": (_percentile(samples, 0.50), "ms"),
        "event_commit_ms_p99": (_percentile(samples, 0.99), "ms"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=1000)
    arguments = parser.parse_args()
    manifest = build_manifest("event-commit-v1", {"events": arguments.events})
    write_report(
        "event-commit",
        run(arguments.events),
        manifest=manifest,
    )


if __name__ == "__main__":
    main()
