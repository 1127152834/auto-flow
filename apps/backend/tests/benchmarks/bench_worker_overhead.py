"""G4 through the real worker process and event persistence (remediation M3 AC3-03).

``bench_runtime_overhead`` measures the executor alone; this one adds the worker IPC, the ACK
round trips and SQLite commits that every event pays. Target: < 5 ms per node.

Run: uv run --directory apps/backend python -m tests.benchmarks.bench_worker_overhead --iterations 200
"""

from __future__ import annotations

import argparse
import asyncio
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)

from .bench_runtime_overhead import WIDTH, g4_document
from .report import Unit, build_manifest, write_report

NOW = datetime(2026, 10, 3, tzinfo=UTC)


class _NoBrowser:
    async def acquire(self, *_args: Any) -> Any:
        raise AssertionError("G4 needs no browser")


def _queue(directory: Path, iterations: int) -> tuple[Any, Any]:
    database = directory / "worker-overhead.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    workflow_id = str(uuid4())
    content = {**g4_document(iterations), "variables": [], "name": "G4"}
    document = {"id": workflow_id, "content": content}
    plan = {
        "orderedNodeIds": [node["id"] for node in content["nodes"]],
        "nodes": [{"nodeId": node["id"], "moduleType": node["data"]["moduleType"], "data": node["data"]} for node in content["nodes"]],
        "document": content,
    }
    with factory() as session:
        session.add(WorkflowDocumentRow(id=workflow_id, name="G4", document=document, layout={}, revision=1, created_at=NOW, updated_at=NOW))
        session.flush()
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        prepared = repository.prepare_content(
            prepared_content_id=str(uuid4()), prepare_operation_id=str(uuid4()), request_digest="a" * 64,
            workflow_id=workflow_id, source_revision=1, checksum="b" * 64, document=document, execution_plan=plan,
            adapter_version="webrpa-graph/v2", capability_requirements=[], provenance={"kind": "benchmark"}, created_at=NOW,
        )
        run = repository.prepare_run(
            run_id=str(uuid4()), run_request_id=str(uuid4()), request_digest="c" * 64,
            prepared_content_id=prepared.prepared_content_id, parameters={}, input_snapshot_ref=None,
            resource_request={"browser": "none", "automaticExecutionTimeoutSeconds": 600}, capability_bindings=[], created_at=NOW,
        )
        session.commit()
    return factory, run


async def _run(iterations: int) -> dict[str, tuple[float | None, Unit]]:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
        directory = Path(raw)
        factory, queued = _queue(directory, iterations)
        worker = ProjectWorkflowWorkerManager(directory / "worker-temp", start_timeout=30)

        async def recover(_run: object) -> None:
            return None

        dispatcher = WorkflowRunDispatcher(factory, worker, _NoBrowser(), QuiesceGate(), recover)
        try:
            started = time.perf_counter()
            await dispatcher.dispatch(queued.run_id, expected_status_revision=queued.status_revision, execution_generation=queued.execution_generation)
            await dispatcher.wait_idle()
            elapsed_ms = (time.perf_counter() - started) * 1000
            with factory() as session:
                repository = SqlAlchemyWorkflowRuntimeRepository(session)
                finished = repository.get_run(run_id=queued.run_id)
                events = repository.list_events(queued.run_id, after_sequence=0, limit=100_000)
        finally:
            await dispatcher.shutdown()
            factory.dispose()
    if finished is None or finished.status != "succeeded":
        raise RuntimeError(f"G4 did not succeed: {finished}")
    nodes = iterations * WIDTH
    return {
        "nodes_executed": (nodes, "count"),
        "events_persisted": (len(events), "count"),
        "worker_ms_per_node": (elapsed_ms / nodes, "ms"),
    }


def run(iterations: int) -> dict[str, tuple[float | None, Unit]]:
    if iterations < 1:
        raise ValueError("iterations must be positive")
    return asyncio.run(_run(iterations))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=200)
    arguments = parser.parse_args()
    write_report("worker-overhead", run(arguments.iterations), manifest=build_manifest("worker-overhead-v1", {"iterations": arguments.iterations}))


if __name__ == "__main__":
    main()
