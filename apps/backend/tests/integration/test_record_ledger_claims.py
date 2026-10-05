"""Remediation M2 Task 4: claim modes, blocked units, per-unit batch limits and backoff waits."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectTaskInputSnapshotRow,
)
from autoflow.infrastructure.database.record_ledger import SqlAlchemyRecordLedger
from autoflow.infrastructure.database.record_ledger_models import (
    AutomationRecordLedgerRow,
    ProjectBatchUnitRow,
)
from tests.fixtures.workflow_runs import SyntheticResources
from tests.integration.test_project_run_data_start import _setup, uid
from tests.integration.test_record_ledger_projection import FactWorker


class SequenceWorker(FactWorker):
    """Each run reports the next status; a page failure only touches read-only nodes."""

    def __init__(self, statuses):
        super().__init__("succeeded", [("open", "none")])
        self.statuses = list(statuses)

    async def run(self, **values):
        self.status = self.statuses.pop(0) if self.statuses else "succeeded"
        return await super().run(**values)


class World:
    def __init__(self, tmp_path, statuses=(), **policy):
        self.factory, self.project, self.automation, self.coordinator = _setup(tmp_path)
        self.chosen = self.automation.input_plan["processingInputId"]
        people = self.automation.input_plan["inputs"][0]
        self.people_table, self.people_generation = people["tableId"], people["datasetGeneration"]
        self.field_id = people["fieldBindings"][0]["fieldRef"]["fieldId"]
        with self.factory.begin() as session:
            row = session.get(ProjectAutomationRow, self.automation.automation_id)
            row.run_policy = {**row.run_policy, "continueAfterFailure": True, **policy}
        self.worker = SequenceWorker(statuses)

        async def cleanup(_run):
            pass

        self.core = WorkflowRunDispatcher(self.factory, self.worker, SyntheticResources(), QuiesceGate(), cleanup)
        self.scheduler = ProjectBatchScheduler(self.factory, self.core, QuiesceGate())

    def add_person(self, value):
        DataRecordService(SqlAlchemyProjectDataRecords(self.factory)).create(
            self.project, self.people_table, uid(),
            {"datasetGeneration": self.people_generation, "values": [{"fieldId": self.field_id, "value": value}]},
        )

    def start(self, max_tasks=10):
        with self.factory() as session:
            revision = session.get(ProjectAutomationRow, self.automation.automation_id).management_revision
        return self.coordinator.start(self.project, self.automation.automation_id, uid(), {
            "expectedAutomationRevision": revision, "parameters": {}, "maxTasks": max_tasks, "concurrency": 1,
        })[0]

    async def settle(self, rounds=6):
        for _ in range(rounds):
            await self.scheduler.tick()
            await self.core.wait_idle()
        await self.scheduler.tick()

    def batch(self, batch_id):
        with self.factory() as session:
            return session.get(ProjectBatchRow, batch_id)

    def processed_people(self, batch_id):
        """Primary values claimed by the batch's Tasks, in claim order."""
        with self.factory() as session:
            snapshots = session.scalars(select(ProjectTaskInputSnapshotRow).where(
                ProjectTaskInputSnapshotRow.batch_id == batch_id).order_by(ProjectTaskInputSnapshotRow.captured_at))
            values = []
            for snapshot in snapshots:
                primary = next(item for item in snapshot.inputs if item["inputId"] == self.chosen)
                values.append(primary["values"][0]["value"])
            return values

    def entries(self):
        with self.factory() as session:
            return {
                stored.entry.scope.key_value: stored.entry
                for stored in SqlAlchemyRecordLedger(session).list(self.automation.automation_id, limit=50)
            }

    def make_due(self):
        with self.factory.begin() as session:
            session.execute(update(AutomationRecordLedgerRow).values(next_eligible_at=datetime.now(UTC) - timedelta(seconds=1)))

    def set_state(self, value, state):
        with self.factory.begin() as session:
            for row in session.scalars(select(AutomationRecordLedgerRow)):
                if self.value_of(row.key_value) == value:
                    row.state = state

    def value_of(self, key_value):
        from autoflow.infrastructure.database.project_data_models import DataRecordRow

        with self.factory() as session:
            row = session.scalar(select(DataRecordRow).where(DataRecordRow.key_value == key_value))
            return row.values_json[self.field_id]


@pytest.mark.asyncio
async def test_unprocessed_takes_each_row_once_and_keeps_reference_rows_reusable(tmp_path):
    world = World(tmp_path, claimMode="unprocessed")
    world.add_person("李四")
    first = world.start()
    await world.settle()
    assert sorted(world.processed_people(first.batch_id)) == ["张三", "李四"]
    assert world.batch(first.batch_id).status == "completed"
    second = world.start()
    await world.settle()
    assert world.processed_people(second.batch_id) == []
    assert world.batch(second.batch_id).status == "completed"
    assert len(world.entries()) == 2, "the shared reference row is never consumed"
    world.factory.dispose()


@pytest.mark.asyncio
async def test_cycle_reuses_successes_only_after_they_are_due(tmp_path):
    world = World(tmp_path, claimMode="cycle")
    first = world.start()
    await world.settle()
    assert world.processed_people(first.batch_id) == ["张三"]
    early = world.start()
    await world.settle()
    assert world.processed_people(early.batch_id) == []
    world.make_due()
    later = world.start()
    await world.settle()
    assert world.processed_people(later.batch_id) == ["张三"]
    entry = next(iter(world.entries().values()))
    assert entry.processing_cycle == 2 and entry.attempts == 2
    world.factory.dispose()


@pytest.mark.asyncio
async def test_a_cycle_batch_takes_each_row_once_even_when_it_becomes_due_again(tmp_path, monkeypatch):
    """Found by G1: a due success was taken again by the same batch, which then never ended."""
    from autoflow.domain.project_runs import ledger

    monkeypatch.setattr(ledger, "CYCLE_REUSE_SECONDS", 0)
    world = World(tmp_path, claimMode="cycle")
    world.add_person("李四")
    first = world.start(max_tasks=10)
    await world.settle(rounds=10)
    assert sorted(world.processed_people(first.batch_id)) == ["张三", "李四"]
    assert world.batch(first.batch_id).status == "completed"
    second = world.start(max_tasks=10)
    await world.settle(rounds=10)
    assert sorted(world.processed_people(second.batch_id)) == ["张三", "李四"], "the next batch takes them again"
    world.factory.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["unprocessed", "cycle", "retryFailed"])
async def test_blocked_units_are_never_claimed_in_any_mode(tmp_path, mode):
    world = World(tmp_path, claimMode="unprocessed")
    world.add_person("李四")
    seed = world.start()
    await world.settle()
    assert len(world.processed_people(seed.batch_id)) == 2
    world.set_state("张三", "needs_review")
    world.set_state("李四", "quarantined")
    with world.factory.begin() as session:
        row = session.get(ProjectAutomationRow, world.automation.automation_id)
        row.run_policy = {**row.run_policy, "claimMode": mode}
    world.make_due()
    batch = world.start()
    await world.settle()
    assert world.processed_people(batch.batch_id) == []
    world.factory.dispose()


@pytest.mark.asyncio
async def test_retry_failed_only_takes_rows_waiting_for_a_retry(tmp_path):
    world = World(tmp_path, ["failed"], claimMode="unprocessed", continueAfterFailure=False)
    seed = world.start()
    await world.settle()
    assert world.processed_people(seed.batch_id) == ["张三"]
    assert world.batch(seed.batch_id).status == "failed"
    world.add_person("李四")  # never processed: retryFailed must leave it alone
    with world.factory.begin() as session:
        row = session.get(ProjectAutomationRow, world.automation.automation_id)
        row.run_policy = {**row.run_policy, "claimMode": "retryFailed"}
    world.make_due()
    retry = world.start()
    await world.settle()
    assert world.processed_people(retry.batch_id) == ["张三"]
    world.factory.dispose()


@pytest.mark.asyncio
async def test_batch_waits_for_its_backoff_and_retries_without_spending_its_row_limit(tmp_path):
    world = World(tmp_path, ["failed", "succeeded"], claimMode="unprocessed")
    batch = world.start(max_tasks=1)
    await world.settle()
    stored = world.batch(batch.batch_id)
    assert stored.status not in {"completed", "failed"}, "a due retry is still ahead"
    assert stored.claim_gate_state == "open"
    assert (stored.selection_outcome or {}).get("status") == "waiting"
    world.make_due()
    await world.settle()
    assert world.processed_people(batch.batch_id) == ["张三", "张三"]
    assert world.batch(batch.batch_id).status == "failed"  # the first attempt still failed technically
    entry = next(iter(world.entries().values()))
    assert (entry.state, entry.attempts) == ("succeeded", 2)
    with world.factory() as session:
        assert len(list(session.scalars(select(ProjectBatchUnitRow)))) == 1
    world.factory.dispose()


@pytest.mark.asyncio
async def test_stopping_a_waiting_batch_ends_it_without_another_claim(tmp_path):
    world = World(tmp_path, ["failed"], claimMode="unprocessed")
    batch = world.start(max_tasks=1)
    await world.settle()
    stored = world.batch(batch.batch_id)
    await world.scheduler.stop(world.project, batch.batch_id, uid(), {
        "expectedStatusRevision": stored.status_revision, "reason": "不再等待",
    })
    world.make_due()
    await world.settle()
    assert world.batch(batch.batch_id).status == "stopped"
    assert world.processed_people(batch.batch_id) == ["张三"]
    world.factory.dispose()


@pytest.mark.asyncio
async def test_a_bad_primary_row_is_quarantined_and_the_batch_continues(tmp_path):
    """R2-17: one identifiable bad primary row must not stop the whole batch."""
    from autoflow.infrastructure.database.project_data_models import DataRecordRow

    world = World(tmp_path, claimMode="unprocessed")
    world.add_person("李四")
    with world.factory.begin() as session:
        bad = session.scalar(select(DataRecordRow).where(DataRecordRow.table_id == world.people_table).order_by(DataRecordRow.key_value).limit(1))
        bad.values_json = {**bad.values_json, world.field_id: 123}  # no longer a valid text value
        bad_key = bad.key_value
    batch = world.start()
    await world.settle(rounds=8)
    processed = world.processed_people(batch.batch_id)
    assert len(processed) == 1 and 123 not in processed
    assert world.batch(batch.batch_id).status == "completed"
    entry = world.entries()[bad_key]
    assert entry.state == "quarantined" and entry.last_error["code"] == "INPUT_VALUE_INVALID"
    assert entry.attempts == 0
    world.factory.dispose()
