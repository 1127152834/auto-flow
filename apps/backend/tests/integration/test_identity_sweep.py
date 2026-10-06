"""Remediation M4 S8-5 (R4-12): the scheduler releases identity copies that are idle, belong to a finished batch,
or were left half released — whether or not other runs are active, and without ever blocking the event loop."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime

import pytest

from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.fixtures.workflow_runs import SyntheticResources
from tests.integration.test_identity_end import (
    _accept_end,
    _environments,
    _instance,
    _perIdentity_task,
    _saved_environments,
)
from tests.integration.test_identity_end import (
    capability_context as capability_context,  # noqa: PLC0414 -- pytest fixture
)
from tests.integration.test_workflow_dispatch import SyntheticWorker, make_dispatcher


async def _held(capability_context, tmp_path, *, retain=True):
    factory, project_id, task, *_rest = capability_context
    environments = _environments(factory, tmp_path / "environments")
    _identity, instance = _perIdentity_task(factory, project_id, task, environments)
    end = await _accept_end(factory, environments, task, retain_environment=retain)
    end.finalize(task.run_id)
    assert _instance(factory, instance.instance_id).state == "identity_held"
    return factory, project_id, task, environments, instance


def _scheduler(factory, environments, **options):
    dispatcher = make_dispatcher(factory, SyntheticWorker(), SyntheticResources())
    return ProjectBatchScheduler(factory, dispatcher, QuiesceGate(), environments, **options)


async def _tick(scheduler):
    await scheduler.tick()
    if scheduler._release_task is not None:
        await scheduler._release_task


@pytest.mark.asyncio
async def test_an_idle_copy_is_saved_and_cleaned_in_the_background(capability_context, tmp_path):
    factory, project_id, _task, environments, instance = await _held(capability_context, tmp_path)
    scheduler = _scheduler(factory, environments, identity_idle_seconds=0)
    woken = []
    scheduler.wake = lambda: woken.append(True)
    await _tick(scheduler)
    assert _instance(factory, instance.instance_id).state == "cleaned"
    assert len(_saved_environments(factory, project_id)) == 1
    assert woken, "a release wakes the scheduler so a batch that was waiting for the identity tries again at once"


@pytest.mark.asyncio
async def test_a_copy_in_recent_use_is_left_alone(capability_context, tmp_path):
    factory, _project_id, _task, environments, instance = await _held(capability_context, tmp_path)
    await _tick(_scheduler(factory, environments, identity_idle_seconds=600))
    assert _instance(factory, instance.instance_id).state == "identity_held"


@pytest.mark.asyncio
async def test_a_copy_held_by_a_finished_batch_is_released_even_when_not_idle(capability_context, tmp_path):
    factory, project_id, task, environments, instance = await _held(capability_context, tmp_path)
    with factory() as session:
        batch_id = session.get(ProjectTaskRow, task.task_id).batch_id
    scheduler = _scheduler(factory, environments, identity_idle_seconds=600)
    await _tick(scheduler)
    assert _instance(factory, instance.instance_id).state == "identity_held", "its batch is still running"
    with factory.begin() as session:
        session.get(ProjectBatchRow, batch_id).status = "completed"
    await _tick(scheduler)
    assert _instance(factory, instance.instance_id).state == "cleaned"
    assert len(_saved_environments(factory, project_id)) == 1


@pytest.mark.asyncio
async def test_the_sweep_runs_while_other_runs_are_active(capability_context, tmp_path):
    """Terminal-task cleanup waits for a quiet moment; the identity release must not, or one busy batch
    would keep every other batch's identities taken for ever."""
    factory, _project_id, task, environments, instance = await _held(capability_context, tmp_path)
    with factory.begin() as session:
        session.get(WorkflowRunRow, task.run_id).status = "running"
    await _tick(_scheduler(factory, environments, identity_idle_seconds=0))
    assert _instance(factory, instance.instance_id).state == "cleaned"


@pytest.mark.asyncio
async def test_after_a_restart_a_copy_with_a_browser_still_open_is_checked_not_saved_or_reused(capability_context, tmp_path):
    factory, project_id, _task, environments, instance = await _held(capability_context, tmp_path)
    restarted = _environments(factory, tmp_path / "environments")
    lock = environments.store.root / "instances" / instance.instance_id / "SingletonLock"
    lock.write_text("host-1")
    scheduler = _scheduler(factory, restarted, identity_idle_seconds=0)
    await _tick(scheduler)
    assert _instance(factory, instance.instance_id).state == "closing"
    assert _saved_environments(factory, project_id) == []
    await _tick(scheduler)
    assert _instance(factory, instance.instance_id).state == "closing", "still verified, still not saved"
    lock.unlink()
    await _tick(scheduler)
    assert _instance(factory, instance.instance_id).state == "cleaned"
    assert len(_saved_environments(factory, project_id)) == 1


@pytest.mark.asyncio
async def test_shutdown_waits_for_a_sweep_in_flight(capability_context, tmp_path, monkeypatch):
    factory, _project_id, _task, environments, _instance_row = await _held(capability_context, tmp_path)
    entered, release = threading.Event(), threading.Event()
    real = environments.release_due_identity_instances

    def slow(**options):
        entered.set()
        assert release.wait(10)
        return real(**options)

    monkeypatch.setattr(environments, "release_due_identity_instances", slow)
    scheduler = _scheduler(factory, environments, identity_idle_seconds=0)
    await scheduler.tick()
    assert await asyncio.to_thread(entered.wait, 5)
    closing = asyncio.ensure_future(scheduler.shutdown())
    await asyncio.sleep(0.2)
    assert not closing.done(), "shutdown must not leave a thread saving files behind it"
    release.set()
    await asyncio.wait_for(closing, 10)


@pytest.mark.asyncio
async def test_only_one_sweep_is_in_flight_at_a_time(capability_context, tmp_path, monkeypatch):
    factory, _project_id, _task, environments, _instance_row = await _held(capability_context, tmp_path)
    release, calls = threading.Event(), []

    def slow(**_options):
        calls.append(datetime.now(UTC))
        assert release.wait(10)
        return 0

    monkeypatch.setattr(environments, "release_due_identity_instances", slow)
    scheduler = _scheduler(factory, environments, identity_idle_seconds=0)
    await scheduler.tick()
    await scheduler.tick()
    await scheduler.tick()
    await asyncio.sleep(0.1)
    assert len(calls) == 1
    release.set()
    await scheduler._release_task
