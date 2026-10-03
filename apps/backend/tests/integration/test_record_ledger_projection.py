"""Remediation M2 Task 3: Task terminals reach the ledger exactly once, with the lease release."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.infrastructure.database.project_run_models import ProjectRecordLeaseRow
from autoflow.infrastructure.database.record_ledger import SqlAlchemyRecordLedger
from autoflow.infrastructure.database.record_ledger_models import ProjectBatchUnitRow
from autoflow.infrastructure.process.workflow_worker import WorkerOutcome
from tests.fixtures.workflow_runs import SyntheticResources
from tests.integration.test_project_run_data_start import _setup, uid


class FactWorker:
    """Reports acknowledged node-start facts like the real project worker, then a terminal."""

    def __init__(self, status, started=()):
        self.status, self.started, self.running = status, list(started), False

    def busy(self, run_id=None):
        return self.running

    async def run(self, **values):
        self.running = True
        try:
            for index, (node, effect) in enumerate(self.started, start=1):
                await values["on_event"]({
                    "eventId": str(uuid4()), "runId": values["run_id"],
                    "executionGeneration": values["execution_generation"], "kind": "nodeAttempt",
                    "nodeId": node, "nodeVisitId": f"{node}-{index}", "attempt": 1,
                    "occurredAt": datetime.now(UTC).isoformat(),
                    "payload": {"status": "started", "sideEffect": effect},
                })
            error = None if self.status == "succeeded" else {"code": "WORKFLOW_NODE_FAILED", "message": "失败原因"}
            return WorkerOutcome(self.status, error, True)
        finally:
            self.running = False

    async def stop(self, _run_id):
        pass

    async def force_stop(self, _run_id):
        pass

    async def shutdown(self):
        pass

    def discard_uncommitted_artifact(self, *_args):
        pass


async def run_one(tmp_path, worker):
    factory, project, automation, coordinator = _setup(tmp_path)

    async def cleanup(_run):
        pass

    core = WorkflowRunDispatcher(factory, worker, SyntheticResources(), QuiesceGate(), cleanup)
    scheduler = ProjectBatchScheduler(factory, core, QuiesceGate())
    batch = coordinator.start(project, automation.automation_id, uid(), {
        "expectedAutomationRevision": automation.management_revision,
        "parameters": {}, "maxTasks": 1, "concurrency": 1,
    })[0]
    await scheduler.tick()
    await core.wait_idle()
    await scheduler.tick()
    await scheduler.tick()  # a second release pass must not project again
    with factory() as session:
        entries = SqlAlchemyRecordLedger(session).list(automation.automation_id, limit=10)
        units = list(session.scalars(select(ProjectBatchUnitRow)))
        leases = list(session.scalars(select(ProjectRecordLeaseRow)))
    factory.dispose()
    return automation, batch, entries, units, leases


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "started", "state", "attempts"),
    [
        ("succeeded", [("open", "none")], "succeeded", 1),
        ("failed", [("open", "none"), ("read", "none")], "failed_retryable", 1),
        ("failed", [("open", "none"), ("click", "possible")], "needs_review", 1),
        ("failed", [], "pending", 0),
    ],
)
async def test_terminal_projects_only_the_primary_input_once(tmp_path, status, started, state, attempts):
    automation, batch, entries, units, leases = await run_one(tmp_path, FactWorker(status, started))
    assert all(lease.state == "released" for lease in leases) and len(leases) == 2
    assert len(entries) == 1, "the reference input is never consumed"
    entry = entries[0].entry
    assert entry.scope.processing_input_id == automation.input_plan["processingInputId"]
    assert (entry.state, entry.attempts) == (state, attempts)
    assert entry.revision == 2
    assert [(unit.batch_id, unit.ledger_id) for unit in units] == [(batch.batch_id, entries[0].id)]
