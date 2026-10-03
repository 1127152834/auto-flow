"""Remediation M2 R2-15/R2-16: threshold batches pause instead of failing every row, and resume."""

from uuid import uuid4

import pytest

from autoflow.domain.project_runs.models import ProjectRunError
from tests.integration.test_record_ledger_claims import SequenceWorker, World


class InfrastructureWorker(SequenceWorker):
    """Fails before any node starts, like a proxy or browser that never came up."""

    def __init__(self):
        super().__init__(["failed"] * 50)
        self.started = []


def thresholds(tmp_path, worker=None, **policy):
    world = World(tmp_path, claimMode="unprocessed", failurePolicy="thresholds", continueAfterFailure=False, **policy)
    if worker is not None:
        world.worker = worker
        world.core._worker = worker
    return world


@pytest.mark.asyncio
async def test_five_infrastructure_failures_pause_the_batch_without_spending_budget(tmp_path):
    world = thresholds(tmp_path, InfrastructureWorker())
    batch = world.start(max_tasks=10)
    await world.settle(rounds=12)
    stored = world.batch(batch.batch_id)
    assert stored.status == "paused"
    assert stored.claim_gate_state == "closed"
    reason = stored.selection_outcome["pauseReason"]
    assert reason["kind"] == "infrastructureStreak" and len(reason["sampleTaskIds"]) == 5
    assert len(world.processed_people(batch.batch_id)) == 5
    entry = next(iter(world.entries().values()))
    assert (entry.state, entry.attempts) == ("pending", 0)
    await world.settle(rounds=3)
    assert len(world.processed_people(batch.batch_id)) == 5, "a paused batch claims nothing"
    world.factory.dispose()


@pytest.mark.asyncio
async def test_resume_counts_only_failures_after_it_and_stop_ends_a_paused_batch(tmp_path):
    world = thresholds(tmp_path, InfrastructureWorker())
    batch = world.start(max_tasks=10)
    await world.settle(rounds=12)
    paused = world.batch(batch.batch_id)
    key = str(uuid4())
    body = {"expectedStatusRevision": paused.status_revision}
    first = await world.scheduler.resume(world.project, batch.batch_id, key, body)
    again = await world.scheduler.resume(world.project, batch.batch_id, key, body)
    assert first == again
    with pytest.raises(ProjectRunError) as stale:
        await world.scheduler.resume(world.project, batch.batch_id, str(uuid4()), body)
    assert stale.value.code == "REVISION_CONFLICT"
    await world.settle(rounds=12)
    assert world.batch(batch.batch_id).status == "paused"
    assert len(world.processed_people(batch.batch_id)) == 10
    current = world.batch(batch.batch_id)
    await world.scheduler.stop(world.project, batch.batch_id, str(uuid4()), {
        "expectedStatusRevision": current.status_revision, "reason": "环境问题未修好",
    })
    await world.settle()
    assert world.batch(batch.batch_id).status == "stopped"
    world.factory.dispose()


@pytest.mark.asyncio
async def test_threshold_mode_keeps_going_after_an_isolated_failure(tmp_path):
    world = thresholds(tmp_path)
    world.worker.statuses = ["failed", "succeeded", "succeeded"]
    world.add_person("李四")
    world.add_person("王五")
    batch = world.start(max_tasks=10)
    await world.settle(rounds=10)
    assert len(world.processed_people(batch.batch_id)) == 3
    assert world.batch(batch.batch_id).status not in {"paused"}
    world.factory.dispose()


@pytest.mark.asyncio
async def test_resume_is_refused_unless_the_batch_is_paused(tmp_path):
    world = thresholds(tmp_path)
    batch = world.start()
    stored = world.batch(batch.batch_id)
    with pytest.raises(ProjectRunError) as refused:
        await world.scheduler.resume(world.project, batch.batch_id, str(uuid4()), {"expectedStatusRevision": stored.status_revision})
    assert refused.value.code == "BATCH_NOT_PAUSED"
    world.factory.dispose()
