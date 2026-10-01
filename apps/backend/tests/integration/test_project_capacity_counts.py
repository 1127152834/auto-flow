"""Remediation M1 R1-09: waiting-for-person runs keep a live browser, not an execution slot."""

import asyncio
from uuid import uuid4

import pytest

from autoflow.application.project_runs.scheduler import (
    ProjectBatchScheduler,
    _capacity_counts,
    _core_limits,
)
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.fixtures.workflow_runs import create_queued_run
from tests.integration.test_project_parameter_concurrency import (
    Workers,
    configure,
    until,
)
from tests.integration.test_project_run_start import setup, start_payload
from tests.integration.test_workflow_dispatch import ConcurrentResources


def test_waiting_manual_runs_count_as_live_but_not_executing(tmp_path):
    database = tmp_path / "counts.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    try:
        running, _ = create_queued_run(factory)
        waiting, _ = create_queued_run(factory)
        queued, _ = create_queued_run(factory)
        with factory.begin() as session:
            session.get(WorkflowRunRow, running.run_id).status = "running"
            session.get(WorkflowRunRow, waiting.run_id).status = "waiting_manual"
        with factory() as session:
            counts = _capacity_counts(session, "no-batch", "no-automation")
        assert (counts.executing, counts.live, counts.automation, counts.batch) == (1, 2, 0, 0)
        assert queued.status == "queued"
    finally:
        factory.dispose()


def test_core_limits_default_live_capacity_to_twice_the_execution_capacity():
    class LegacyCore:
        capacity = 3

    class SplitCore:
        capacity = 2
        live_capacity = 5

    assert _core_limits(LegacyCore()) == (3, 6)
    assert _core_limits(SplitCore()) == (2, 5)


async def running_scheduler(tmp_path, *, capacity, live_capacity, max_tasks=3):
    """A real scheduler loop and dispatcher; only the worker processes are controlled."""
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    configure(factory, automation, concurrency=3, instances=3)
    coordinator.start(project.project_id, automation.automation_id, str(uuid4()),
                      {**start_payload(automation, max_tasks=max_tasks), 'concurrency': 3})
    workers, resources, gate = Workers(), ConcurrentResources(), QuiesceGate()

    async def cleanup(_run):
        pass

    core = WorkflowRunDispatcher(
        factory, workers, resources, gate, cleanup, capacity=capacity, live_capacity=live_capacity
    )
    scheduler = ProjectBatchScheduler(factory, core, gate)
    await scheduler.startup()
    return factory, workers, resources, core, scheduler


async def settle_while_waiting_for_capacity(workers, expected):
    """The loop has dispatched what fits and is now parked on its wake event."""
    await until(lambda: len(workers.calls) >= expected)
    await asyncio.sleep(0.3)
    assert len(workers.calls) == expected


@pytest.mark.asyncio
async def test_a_run_waiting_for_a_person_frees_its_slot_and_wakes_the_scheduler(tmp_path):
    factory, workers, resources, core, scheduler = await running_scheduler(
        tmp_path, capacity=1, live_capacity=2
    )
    try:
        await settle_while_waiting_for_capacity(workers, 1)
        first = workers.calls[0]
        core.pause_manual(first, core.query_run(first).execution_generation)
        # No tick(), wake() or dispatch() here: only the dispatcher's own subscription may start B.
        async with asyncio.timeout(5):
            while len(workers.calls) < 2:
                await asyncio.sleep(0.01)
        assert workers.busy(first) and not resources.leases[first].released
        await asyncio.sleep(0.3)
        assert len(workers.calls) == 2  # the live-browser limit stops a third dispatch
        assert core.executing_count() == 1
    finally:
        await scheduler.shutdown()
        await core.shutdown()
        factory.dispose()


@pytest.mark.asyncio
async def test_raising_the_capacity_wakes_the_scheduler_and_lowering_never_stops_runs(tmp_path):
    factory, workers, _, core, scheduler = await running_scheduler(
        tmp_path, capacity=1, live_capacity=2
    )
    try:
        await settle_while_waiting_for_capacity(workers, 1)
        core.set_capacity(2, 2)
        async with asyncio.timeout(5):
            while len(workers.calls) < 2:
                await asyncio.sleep(0.01)
        core.set_capacity(1, 1)
        await asyncio.sleep(0.3)
        assert len(workers.calls) == 2
        assert all(core.query_run(run_id).status == 'running' for run_id in workers.calls)
    finally:
        await scheduler.shutdown()
        await core.shutdown()
        factory.dispose()
