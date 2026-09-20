"""One-minute synthetic load, exclusively in the PM9 runner's disposable workspace."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import gettempdir
from time import perf_counter, sleep
from uuid import uuid4

from autoflow.infrastructure.database.project_run_models import ProjectTaskRow
from autoflow.infrastructure.database.session import create_session_factory
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)

workspace = Path(sys.argv[1]).resolve(strict=True)
assert workspace.parent == Path(gettempdir()).resolve()
assert workspace.name.startswith("autoflow-pm9 desktop 中文-")
assert json.loads((workspace / ".autoflow-workspace.json").read_text(encoding="utf-8"))["kind"] == "autoflow-workspace"
database = workspace / "data" / "autoflow.sqlite3"
assert database.is_file()
factory = create_session_factory(database)
try:
    with factory() as session:
        task = session.get(ProjectTaskRow, sys.argv[2])
        assert task is not None
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        run = repository.get_run(run_id=task.run_id)
        assert run is not None and run.status == "succeeded"
        run_id, generation = run.run_id, run.execution_generation
    started = perf_counter()
    emitted, lag_ms = 0, []
    for second in range(1, 61):
        sleep(max(0, started + second - perf_counter()))
        with factory.begin() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            while emitted < second * 1000 // 60:
                repository.append_event({
                    "eventId": str(uuid4()), "runId": run_id,
                    "executionGeneration": generation, "kind": "log",
                    "occurredAt": datetime.now(UTC),
                    "payload": {"level": "info", "message": f"PM9 synthetic cadence {emitted + 1:04d}"},
                })
                emitted += 1
        lag_ms.append(round((perf_counter() - started - second) * 1000))
    print(json.dumps({"targetLogsPerMinute": 1000, "seconds": 60, "emitted": emitted,
                      "elapsedMs": round((perf_counter() - started) * 1000), "maxBatchLagMs": max(lag_ms)}))
finally:
    factory.dispose()
