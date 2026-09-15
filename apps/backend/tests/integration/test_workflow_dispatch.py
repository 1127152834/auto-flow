from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.domain.workflows.runtime import WorkflowRuntimeError
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.process.workflow_worker import WorkerOutcome
from tests.fixtures.workflow_runs import NOW, SyntheticResources, create_queued_run


class SyntheticWorker:
    def __init__(
        self, *, outcome="succeeded", fail=None, cleanup_fail=False, blocked=None
    ):
        self.outcome = outcome
        self.fail = fail
        self.cleanup_fail = cleanup_fail
        self.blocked = blocked
        self.calls = []
        self.stop_calls = []
        self.force_calls = []
        self.running = False
        self.shutdown_calls = 0

    def busy(self):
        return self.running

    async def run(self, **values):
        self.running = True
        self.calls.append(values)
        try:
            await values["on_event"](
                {
                    "eventId": "event-1",
                    "runId": values["run_id"],
                    "executionGeneration": values["execution_generation"],
                    "kind": "log",
                    "nodeId": "open",
                    "nodeVisitId": "visit-1",
                    "attempt": 1,
                    "occurredAt": NOW.isoformat(),
                    "payload": {"message": "committed"},
                }
            )
            if self.blocked is not None:
                await self.blocked.wait()
            if self.fail is not None:
                raise self.fail
            return WorkerOutcome(
                self.outcome,
                None
                if self.outcome == "succeeded"
                else {"code": "WORKFLOW_FAILED", "message": "synthetic"},
                True,
            )
        finally:
            if not self.cleanup_fail:
                self.running = False

    async def stop(self, run_id):
        self.stop_calls.append(run_id)
        if self.blocked is not None:
            self.blocked.set()

    async def force_stop(self, run_id):
        self.force_calls.append(run_id)
        if self.cleanup_fail:
            raise RuntimeError("cleanup unknown")
        self.running = False
        if self.blocked is not None:
            self.blocked.set()

    async def shutdown(self):
        self.shutdown_calls += 1
        if self.cleanup_fail:
            raise RuntimeError("shutdown cleanup unknown")
        self.running = False


@pytest.fixture
def runtime(tmp_path):
    database = tmp_path / "dispatcher.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    yield factory
    factory.dispose()


def make_dispatcher(factory, worker, resources, recovery=None, **kwargs):
    async def recovered(_run):
        if recovery is not None:
            await recovery(_run)

    return WorkflowRunDispatcher(
        factory, worker, resources, QuiesceGate(), recovered, **kwargs
    )


@pytest.mark.asyncio
async def test_success_uses_frozen_plan_typed_parameters_and_commits_event_before_return(
    runtime,
):
    run, _ = create_queued_run(runtime)
    worker, resources = SyntheticWorker(), SyntheticResources()
    dispatcher = make_dispatcher(runtime, worker, resources)

    running = await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await dispatcher.wait_idle()

    assert running.status == "running" and running.execution_generation == 1
    assert running.last_sequence == 1
    call = worker.calls[0]
    assert call["execution_plan"] == {"orderedNodeIds": ["open"], "frozen": True}
    assert call["parameters"] == {"count": 0, "enabled": False, "name": "测试"}
    assert isinstance(call["parameters"]["count"], int)
    assert isinstance(call["parameters"]["enabled"], bool)
    assert call["variables"] == {
        "fromDocument": "frozen",
        "count": 0,
        "enabled": False,
        "name": "测试",
    }
    assert resources.requests == [({"frozen": "request"}, run.run_request_id)]
    with runtime() as session:
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        finished = repository.get_run(run_id=run.run_id)
        events = repository.list_events(run.run_id, after_sequence=0, limit=10)
    assert finished.status == "succeeded" and finished.last_sequence == 4
    assert [event.kind for event in events] == ["status", "log", "status", "status"]
    assert events[1].sequence == 2 and events[1].event_id == "event-1"
    assert resources.lease.released


@pytest.mark.asyncio
async def test_capacity_is_one_and_queued_cancel_never_launches(runtime):
    release = asyncio.Event()
    first, _ = create_queued_run(runtime)
    second, _ = create_queued_run(runtime)
    worker = SyntheticWorker(blocked=release)
    dispatcher = make_dispatcher(runtime, worker, SyntheticResources())
    active = await dispatcher.dispatch(
        first.run_id, expected_status_revision=1, execution_generation=0
    )
    await asyncio.sleep(0)
    with pytest.raises(WorkflowRuntimeError, match="容量"):
        await dispatcher.dispatch(
            second.run_id, expected_status_revision=1, execution_generation=0
        )
    cancelled = await dispatcher.cancel(
        second.run_id, expected_status_revision=1, execution_generation=0
    )
    assert cancelled.status == "cancelled" and len(worker.calls) == 1
    await dispatcher.cancel(
        first.run_id,
        expected_status_revision=active.status_revision,
        execution_generation=active.execution_generation,
    )
    await dispatcher.wait_idle()


@pytest.mark.asyncio
async def test_unknown_worker_failure_fences_then_interrupts_only_after_cleanup(
    runtime,
):
    run, _ = create_queued_run(runtime)
    worker = SyntheticWorker(fail=RuntimeError("lost"))
    dispatcher = make_dispatcher(runtime, worker, SyntheticResources())
    await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await dispatcher.wait_idle()
    current = dispatcher._get_run(run.run_id)
    assert current.status == "interrupted" and current.execution_generation == 2
    assert worker.force_calls == [run.run_id]


@pytest.mark.asyncio
async def test_cleanup_failure_retains_reconciling_lease_and_capacity(runtime):
    run, _ = create_queued_run(runtime)
    worker = SyntheticWorker(fail=RuntimeError("lost"), cleanup_fail=True)
    resources = SyntheticResources()
    dispatcher = make_dispatcher(runtime, worker, resources)
    await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await dispatcher.wait_idle()
    current = dispatcher._get_run(run.run_id)
    assert current.status == "reconciling" and not resources.lease.released
    assert "workflow_worker_busy" in dispatcher.blockers()
    worker.cleanup_fail = False
    worker.running = False  # synthetic recovery has now confirmed the owner is gone
    reconciled = await dispatcher.reconcile(run.run_id)
    assert reconciled.status == "interrupted" and resources.lease.released


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["failed", "timed_out"])
async def test_explicit_worker_terminal_status_is_preserved(runtime, outcome):
    run, _ = create_queued_run(runtime)
    dispatcher = make_dispatcher(
        runtime, SyntheticWorker(outcome=outcome), SyntheticResources()
    )
    await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await dispatcher.wait_idle()
    finished = dispatcher._get_run(run.run_id)
    assert finished.status == outcome and finished.status_revision == 4
    assert finished.execution_generation == 1


@pytest.mark.asyncio
async def test_stopping_event_is_acked_until_force_revokes_generation(runtime):
    run, _ = create_queued_run(runtime)
    release = asyncio.Event()
    worker = SyntheticWorker(blocked=release)
    dispatcher = make_dispatcher(runtime, worker, SyntheticResources())
    running = await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await asyncio.sleep(0)
    stopping = await dispatcher.cancel(
        run.run_id,
        expected_status_revision=running.status_revision,
        execution_generation=running.execution_generation,
    )
    event = {
        "eventId": "in-flight",
        "runId": run.run_id,
        "executionGeneration": running.execution_generation,
        "kind": "log",
        "nodeId": "open",
        "occurredAt": NOW.isoformat(),
        "payload": {},
    }
    await worker.calls[0]["on_event"](event)
    dispatcher._now = lambda: NOW + timedelta(seconds=31)
    forced = await dispatcher.force_stop(
        run.run_id,
        expected_status_revision=stopping.status_revision,
        execution_generation=stopping.execution_generation,
    )
    with pytest.raises(WorkflowRuntimeError) as caught:
        await worker.calls[0]["on_event"]({**event, "eventId": "late"})
    assert caught.value.code == "EXECUTION_GENERATION_REVOKED"
    await dispatcher.wait_idle()
    assert forced.status == "interrupted"


@pytest.mark.asyncio
async def test_startup_fences_active_without_replaying_queued_or_terminal(runtime):
    queued, _ = create_queued_run(runtime)
    active, _ = create_queued_run(runtime)
    done, _ = create_queued_run(runtime)
    with runtime() as session:
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        active = repository.transition_run(
            active.run_id,
            target_status="running",
            expected_status_revision=1,
            expected_execution_generation=0,
            now=NOW,
        )
        done = repository.transition_run(
            done.run_id,
            target_status="running",
            expected_status_revision=1,
            expected_execution_generation=0,
            now=NOW,
        )
        done = repository.transition_run(
            done.run_id,
            target_status="finishing",
            expected_status_revision=2,
            expected_execution_generation=1,
            now=NOW,
        )
        repository.transition_run(
            done.run_id,
            target_status="succeeded",
            expected_status_revision=3,
            expected_execution_generation=1,
            now=NOW,
        )
        session.commit()
    recovered = []

    async def recovery(run):
        recovered.append(run)

    worker = SyntheticWorker()
    dispatcher = make_dispatcher(runtime, worker, SyntheticResources(), recovery)
    await dispatcher.startup()
    assert dispatcher._get_run(queued.run_id).status == "queued"
    assert dispatcher._get_run(active.run_id).status == "interrupted"
    assert dispatcher._get_run(done.run_id).status == "succeeded"
    assert [item.run_id for item in recovered] == [active.run_id]
    assert not worker.calls


@pytest.mark.asyncio
async def test_failed_startup_recovery_blocks_new_dispatch(runtime):
    orphan, _ = create_queued_run(runtime)
    queued, _ = create_queued_run(runtime)
    with runtime() as session:
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        repository.transition_run(
            orphan.run_id,
            target_status="running",
            expected_status_revision=1,
            expected_execution_generation=0,
            now=NOW,
        )
        session.commit()

    async def fail_recovery(_run):
        raise RuntimeError("ownership unknown")

    dispatcher = make_dispatcher(
        runtime, SyntheticWorker(), SyntheticResources(), fail_recovery
    )
    await dispatcher.startup()
    assert dispatcher._get_run(orphan.run_id).status == "reconciling"
    with pytest.raises(WorkflowRuntimeError) as caught:
        await dispatcher.dispatch(
            queued.run_id, expected_status_revision=1, execution_generation=0
        )
    assert caught.value.code == "WORKFLOW_CAPACITY_FULL"


@pytest.mark.asyncio
async def test_status_and_status_event_commit_atomically(runtime, monkeypatch):
    run, _ = create_queued_run(runtime)
    original = SqlAlchemyWorkflowRuntimeRepository.append_event

    def fail_status(self, event):
        if event.get("kind") == "status":
            raise RuntimeError("event write failed")
        return original(self, event)

    monkeypatch.setattr(
        SqlAlchemyWorkflowRuntimeRepository, "append_event", fail_status
    )
    dispatcher = make_dispatcher(runtime, SyntheticWorker(), SyntheticResources())
    with pytest.raises(RuntimeError, match="event write failed"):
        await dispatcher.dispatch(
            run.run_id, expected_status_revision=1, execution_generation=0
        )
    assert dispatcher._get_run(run.run_id).status == "queued"


@pytest.mark.asyncio
async def test_cancel_during_acquire_prevents_launch_and_force_requires_grace(runtime):
    acquire = asyncio.Event()
    run, _ = create_queued_run(runtime)
    worker, resources = SyntheticWorker(), SyntheticResources(blocked=acquire)
    dispatcher = make_dispatcher(
        runtime,
        worker,
        resources,
        force_stop_grace=timedelta(seconds=30),
        now=lambda: NOW,
    )
    running = await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await asyncio.sleep(0)
    stopping = await dispatcher.cancel(
        run.run_id,
        expected_status_revision=running.status_revision,
        execution_generation=running.execution_generation,
    )
    with pytest.raises(WorkflowRuntimeError) as caught:
        await dispatcher.force_stop(
            run.run_id,
            expected_status_revision=stopping.status_revision,
            execution_generation=stopping.execution_generation,
        )
    assert caught.value.code == "FORCE_STOP_GRACE_ACTIVE"
    acquire.set()
    await dispatcher.wait_idle()
    assert not worker.calls and dispatcher._get_run(run.run_id).status == "cancelled"


@pytest.mark.asyncio
async def test_force_during_acquire_revokes_generation_before_cleanup(runtime):
    acquire = asyncio.Event()
    clock = [NOW]
    run, _ = create_queued_run(runtime)
    worker, resources = SyntheticWorker(), SyntheticResources(blocked=acquire)
    dispatcher = make_dispatcher(runtime, worker, resources, now=lambda: clock[0])
    running = await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await asyncio.sleep(0)
    stopping = await dispatcher.cancel(
        run.run_id,
        expected_status_revision=running.status_revision,
        execution_generation=running.execution_generation,
    )
    clock[0] += timedelta(seconds=31)
    forced = await dispatcher.force_stop(
        run.run_id,
        expected_status_revision=stopping.status_revision,
        execution_generation=stopping.execution_generation,
    )
    assert forced.status == "interrupted" and forced.execution_generation == 2
    acquire.set()
    await dispatcher.wait_idle()
    assert not worker.calls and resources.lease.released


@pytest.mark.asyncio
async def test_force_orphan_uses_recovery_instead_of_empty_manager(runtime):
    run, _ = create_queued_run(runtime)
    with runtime() as session:
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        running = repository.transition_run(
            run.run_id,
            target_status="running",
            expected_status_revision=1,
            expected_execution_generation=0,
            now=NOW,
        )
        stopping = repository.transition_run(
            run.run_id,
            target_status="stopping",
            expected_status_revision=running.status_revision,
            expected_execution_generation=running.execution_generation,
            now=NOW,
        )
        session.commit()
    recovered = []

    async def recovery(value):
        recovered.append(value.run_id)

    worker = SyntheticWorker()
    dispatcher = make_dispatcher(
        runtime,
        worker,
        SyntheticResources(),
        recovery,
        now=lambda: NOW + timedelta(seconds=31),
    )
    result = await dispatcher.force_stop(
        run.run_id,
        expected_status_revision=stopping.status_revision,
        execution_generation=stopping.execution_generation,
    )
    assert result.status == "interrupted"
    assert recovered == [run.run_id] and not worker.force_calls


@pytest.mark.asyncio
async def test_acquire_cleanup_error_stays_reconciling_until_recovery(runtime):
    gate = asyncio.Event()
    run, _ = create_queued_run(runtime)
    resources = SyntheticResources(
        blocked=gate, cleanup_failure=RuntimeError("guard close failed")
    )
    recovered = []

    async def recovery(value):
        recovered.append(value.run_id)

    dispatcher = make_dispatcher(
        runtime, SyntheticWorker(), resources, recovery, now=lambda: NOW
    )
    running = await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await asyncio.sleep(0)
    stopping = await dispatcher.cancel(
        run.run_id,
        expected_status_revision=running.status_revision,
        execution_generation=running.execution_generation,
    )
    dispatcher._now = lambda: NOW + timedelta(seconds=31)
    forced = await dispatcher.force_stop(
        run.run_id,
        expected_status_revision=stopping.status_revision,
        execution_generation=stopping.execution_generation,
    )
    assert forced.status == "reconciling" and dispatcher._run_id == run.run_id
    reconciled = await dispatcher.reconcile(run.run_id)
    assert reconciled.status == "interrupted" and recovered == [run.run_id]


@pytest.mark.asyncio
async def test_failed_guard_recovery_remains_owned_across_reconcile_retries(runtime):
    acquire = asyncio.Event()
    run, _ = create_queued_run(runtime)
    resources = SyntheticResources(
        blocked=acquire, cleanup_failure=RuntimeError("guard close failed")
    )
    attempts = []

    async def recovery(value):
        attempts.append(value.run_id)
        raise RuntimeError("guard ownership unknown")

    dispatcher = make_dispatcher(
        runtime, SyntheticWorker(), resources, recovery, now=lambda: NOW
    )
    running = await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await asyncio.sleep(0)
    stopping = await dispatcher.cancel(
        run.run_id,
        expected_status_revision=running.status_revision,
        execution_generation=running.execution_generation,
    )
    dispatcher._now = lambda: NOW + timedelta(seconds=31)
    first = await dispatcher.force_stop(
        run.run_id,
        expected_status_revision=stopping.status_revision,
        execution_generation=stopping.execution_generation,
    )
    assert first.status == "reconciling"
    second = await dispatcher.force_stop(
        run.run_id,
        expected_status_revision=first.status_revision,
        execution_generation=first.execution_generation,
    )
    assert second.status == "reconciling"
    assert (await dispatcher.reconcile(run.run_id)).status == "reconciling"
    assert attempts == [run.run_id, run.run_id]
    assert (
        dispatcher._run_id == run.run_id
        and "workflow_worker_busy" in dispatcher.blockers()
    )


@pytest.mark.asyncio
async def test_acquire_error_requires_recovery_to_prove_hidden_guards_released(runtime):
    run, _ = create_queued_run(runtime)
    guard_released = False
    recovery_calls = []

    class HiddenGuardFailure:
        async def acquire(self, _request, _run_request_id):
            raise RuntimeError("secret-profile-path guard close failed")

    async def recovery(value):
        recovery_calls.append(value.run_id)
        if not guard_released:
            raise RuntimeError("profile guard still held")

    dispatcher = make_dispatcher(
        runtime, SyntheticWorker(), HiddenGuardFailure(), recovery
    )
    await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await dispatcher.wait_idle()
    uncertain = dispatcher._get_run(run.run_id)
    assert uncertain.status == "reconciling"
    assert uncertain.error is None
    assert dispatcher._task is not None and dispatcher._task.done()
    assert "workflow_worker_busy" in dispatcher.blockers()

    guard_released = True
    reconciled = await dispatcher.reconcile(run.run_id)
    assert reconciled.status == "interrupted"
    assert reconciled.error == {
        "code": "WORKFLOW_RESULT_UNKNOWN",
        "message": "执行结果不明确，已撤销旧执行写入权限",
    }
    assert recovery_calls == [run.run_id, run.run_id]
    assert "secret-profile-path" not in str(reconciled.error)


@pytest.mark.asyncio
async def test_force_and_reconcile_are_serialized_until_cleanup_finishes(runtime):
    worker_gate = asyncio.Event()

    class BlockingForceWorker(SyntheticWorker):
        async def stop(self, run_id):
            self.stop_calls.append(run_id)

        async def force_stop(self, run_id):
            self.force_calls.append(run_id)
            await worker_gate.wait()
            self.running = False

    run, _ = create_queued_run(runtime)
    worker = BlockingForceWorker(blocked=asyncio.Event())
    dispatcher = make_dispatcher(runtime, worker, SyntheticResources(), now=lambda: NOW)
    running = await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await asyncio.sleep(0)
    stopping = await dispatcher.cancel(
        run.run_id,
        expected_status_revision=running.status_revision,
        execution_generation=running.execution_generation,
    )
    dispatcher._now = lambda: NOW + timedelta(seconds=31)
    forcing = asyncio.create_task(
        dispatcher.force_stop(
            run.run_id,
            expected_status_revision=stopping.status_revision,
            execution_generation=stopping.execution_generation,
        )
    )
    await asyncio.sleep(0)
    reconciling = asyncio.create_task(dispatcher.reconcile(run.run_id))
    await asyncio.sleep(0)
    assert dispatcher._get_run(run.run_id).status == "reconciling"
    assert not reconciling.done()
    worker_gate.set()
    assert (await forcing).status == "interrupted"
    with pytest.raises(WorkflowRuntimeError):
        await reconciling


@pytest.mark.asyncio
async def test_running_run_cannot_be_dispatched_again_and_noop_has_no_event(runtime):
    release = asyncio.Event()
    run, _ = create_queued_run(runtime)
    dispatcher = make_dispatcher(
        runtime, SyntheticWorker(blocked=release), SyntheticResources()
    )
    running = await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    with pytest.raises(WorkflowRuntimeError) as caught:
        await dispatcher.dispatch(
            run.run_id,
            expected_status_revision=running.status_revision,
            execution_generation=running.execution_generation,
        )
    assert caught.value.code == "RUN_NOT_DISPATCHABLE"
    same = dispatcher._transition_identity(
        run.run_id, "running", running.status_revision, running.execution_generation
    )
    assert same.last_sequence == running.last_sequence == 1
    await dispatcher.cancel(
        run.run_id,
        expected_status_revision=running.status_revision,
        execution_generation=running.execution_generation,
    )
    await dispatcher.wait_idle()


@pytest.mark.asyncio
async def test_quiesce_blockers_and_shutdown_preserve_cleanup_failure(runtime):
    release = asyncio.Event()
    run, _ = create_queued_run(runtime)
    worker = SyntheticWorker(blocked=release, cleanup_fail=True)
    dispatcher = make_dispatcher(runtime, worker, SyntheticResources())
    running = await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await asyncio.sleep(0)
    assert set(dispatcher.blockers()) == {
        "workflow_runs_active",
        "workflow_worker_busy",
    }
    with pytest.raises(RuntimeError, match="shutdown cleanup unknown"):
        await dispatcher.shutdown()
    assert dispatcher._task is not None and dispatcher._task.done()
    current = dispatcher._get_run(run.run_id)
    assert current.status == "reconciling"
    assert current.execution_generation > running.execution_generation


@pytest.mark.asyncio
async def test_shutdown_retries_unknown_guard_cleanup_and_retains_failed_owner(runtime):
    run, _ = create_queued_run(runtime)
    released = False
    attempts = []

    class HiddenGuardFailure:
        async def acquire(self, _request, _run_request_id):
            raise RuntimeError("guard close failed")

    async def recover(value):
        attempts.append(value.run_id)
        if not released:
            raise RuntimeError("guard ownership unknown")

    dispatcher = make_dispatcher(
        runtime, SyntheticWorker(), HiddenGuardFailure(), recover
    )
    await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await dispatcher.wait_idle()
    with pytest.raises(RuntimeError, match="guard ownership unknown"):
        await dispatcher.shutdown()
    assert attempts == [run.run_id, run.run_id]
    assert dispatcher._owner_cleanup_unknown
    assert dispatcher._run_id == run.run_id
    assert "workflow_worker_busy" in dispatcher.blockers()
    assert dispatcher._get_run(run.run_id).status == "reconciling"

    released = True
    await dispatcher.shutdown()
    assert attempts == [run.run_id] * 3
    assert not dispatcher._owner_cleanup_unknown
    assert dispatcher._run_id is None
    assert "workflow_worker_busy" not in dispatcher.blockers()
    assert dispatcher._get_run(run.run_id).status == "reconciling"


@pytest.mark.asyncio
async def test_shutdown_recovery_resolves_failed_acquire_cancellation(runtime):
    run, _ = create_queued_run(runtime)
    resources = SyntheticResources(
        blocked=asyncio.Event(), cleanup_failure=RuntimeError("guard close failed")
    )
    attempts = []

    async def recover(value):
        attempts.append(value.run_id)

    dispatcher = make_dispatcher(runtime, SyntheticWorker(), resources, recover)
    await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await asyncio.sleep(0)
    await dispatcher.shutdown()
    assert attempts == [run.run_id]
    assert dispatcher._run_id is None
    assert "workflow_worker_busy" not in dispatcher.blockers()
    assert dispatcher._get_run(run.run_id).status == "reconciling"
    await dispatcher.shutdown()
    assert attempts == [run.run_id]


@pytest.mark.asyncio
async def test_automatic_budget_times_out_only_after_confirmed_cleanup(runtime):
    from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow

    run, _ = create_queued_run(runtime)
    with runtime() as session:
        row = session.get(WorkflowRunRow, run.run_id)
        row.resource_request = {
            **row.resource_request,
            "automaticExecutionTimeoutSeconds": 0.01,
        }
        session.commit()
    worker, resources = SyntheticWorker(blocked=asyncio.Event()), SyntheticResources()
    dispatcher = make_dispatcher(runtime, worker, resources)
    await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await asyncio.wait_for(dispatcher.wait_idle(), timeout=2)
    current = dispatcher._get_run(run.run_id)
    assert current.status == "timed_out"
    assert current.error["code"] == "AUTOMATIC_EXECUTION_TIMEOUT"
    assert not worker.busy() and resources.lease.released


@pytest.mark.asyncio
async def test_budget_with_unknown_cleanup_does_not_claim_terminal_timeout(runtime):
    from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow

    run, _ = create_queued_run(runtime)
    with runtime() as session:
        row = session.get(WorkflowRunRow, run.run_id)
        row.resource_request = {
            **row.resource_request,
            "automaticExecutionTimeoutSeconds": 0.01,
        }
        session.commit()
    worker = SyntheticWorker(blocked=asyncio.Event(), cleanup_fail=True)
    resources = SyntheticResources()
    dispatcher = make_dispatcher(runtime, worker, resources)
    await dispatcher.dispatch(
        run.run_id, expected_status_revision=1, execution_generation=0
    )
    await asyncio.wait_for(dispatcher.wait_idle(), timeout=2)
    current = dispatcher._get_run(run.run_id)
    assert current.status == "reconciling" and current.execution_generation == 2
    assert worker.busy() and not resources.lease.released
    worker.cleanup_fail = False
    await dispatcher.reconcile(run.run_id)
    assert dispatcher._get_run(run.run_id).status == "interrupted"
