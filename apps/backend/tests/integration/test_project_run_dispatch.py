"""Real SQLite/CoreRun coordination; synthetic worker, not browser E2E."""

import asyncio
from uuid import uuid4

import pytest

from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.process.workflow_worker import WorkerOutcome
from tests.fixtures.workflow_runs import SyntheticResources
from tests.integration.test_project_run_start import setup, start_payload


class Worker:
    def __init__(self, results=None, wait=None):
        self.results = list(results or ["succeeded"])
        self.wait = wait
        self.calls = []
        self.running = False
        self.discarded = []

    def busy(self, run_id=None):
        return self.running

    async def run(self, **values):
        self.running = True
        self.calls.append(values["run_id"])
        try:
            if self.wait is not None:
                await self.wait.wait()
            result = self.results.pop(0) if self.results else "succeeded"
            return WorkerOutcome(result, None, True)
        finally:
            self.running = False

    async def stop(self, _run_id):
        if self.wait is not None:
            self.wait.set()

    async def force_stop(self, _run_id):
        await self.stop(_run_id)

    async def shutdown(self):
        await self.stop("")

    def discard_uncommitted_artifact(
        self, run_id, execution_generation, artifact_id, relative_path
    ):
        self.discarded.append(
            (run_id, execution_generation, artifact_id, relative_path)
        )


def services(tmp_path, *, results=None, wait=None, continue_after_failure=False):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    with factory() as session:
        row = session.get(ProjectAutomationRow, automation.automation_id)
        row.run_policy = {
            **row.run_policy,
            "continueAfterFailure": continue_after_failure,
        }
        session.commit()
    batch, _, _ = coordinator.start(
        project.project_id,
        automation.automation_id,
        str(uuid4()),
        start_payload(automation, max_tasks=3),
    )
    worker, gate = Worker(results, wait), QuiesceGate()

    async def cleanup(_run):
        pass

    core = WorkflowRunDispatcher(factory, worker, SyntheticResources(), gate, cleanup)
    scheduler = ProjectBatchScheduler(factory, core, gate)
    return factory, coordinator, project, batch, worker, core, scheduler, gate


@pytest.mark.asyncio
async def test_serial_tasks_use_core_facts_and_finish_batch(tmp_path):
    factory, coordinator, project, batch, worker, core, scheduler, _ = services(
        tmp_path
    )
    for index in range(3):
        await scheduler.tick()
        await core.wait_idle()
        assert len(worker.calls) == index + 1
    await scheduler.tick()
    current = coordinator.get_batch(project.project_id, batch.batch_id)
    assert current.status == "completed" and current.counts.active_task_count == 0
    assert current.counts.by_status["succeeded"] == 3
    assert len(set(worker.calls)) == 3
    assert not scheduler.blockers()
    factory.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("continue_after_failure", [False, True])
async def test_failure_policy_never_replays_completed_task(
    tmp_path, continue_after_failure
):
    factory, coordinator, project, batch, worker, core, scheduler, _ = services(
        tmp_path, results=["failed"], continue_after_failure=continue_after_failure
    )
    for _ in range(5):
        await scheduler.tick()
        await core.wait_idle()
    current = coordinator.get_batch(project.project_id, batch.batch_id)
    assert current.counts.by_status["failed"] == 1
    assert len(worker.calls) == (3 if continue_after_failure else 1)
    assert current.counts.by_status["cancelled"] == (0 if continue_after_failure else 2)
    assert current.status == "failed"
    factory.dispose()


@pytest.mark.asyncio
async def test_stop_before_dispatch_is_durable_and_original_key_recoverable(tmp_path):
    factory, coordinator, project, batch, worker, _core, scheduler, _ = services(
        tmp_path
    )
    key = str(uuid4())
    request = {"expectedStatusRevision": 1, "reason": "测试停止"}
    operation = await scheduler.stop(project.project_id, batch.batch_id, key, request)
    assert operation.status in {"running", "succeeded"}
    await scheduler.tick()
    replay = await scheduler.stop(project.project_id, batch.batch_id, key, request)
    assert replay.operation_id == operation.operation_id
    current = coordinator.get_batch(project.project_id, batch.batch_id)
    assert current.status == "stopped" and current.counts.by_status["cancelled"] == 3
    assert worker.calls == []
    factory.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("force", [False, True])
async def test_terminal_batch_stop_returns_current_fact_even_with_stale_revision(
    tmp_path, force
):
    factory, coordinator, project, batch, _, core, scheduler, _ = services(tmp_path)
    for _ in range(4):
        await scheduler.tick()
        await core.wait_idle()
    current = coordinator.get_batch(project.project_id, batch.batch_id)
    assert current.status == "completed" and current.status_revision > 1
    key = str(uuid4())

    operation = await scheduler.stop(
        project.project_id,
        batch.batch_id,
        key,
        {"expectedStatusRevision": 1, "reason": "读取最终事实"},
        force=force,
    )

    assert operation.status == "succeeded"
    assert operation.result is not None
    assert operation.result["batch"]["status"] == "completed"
    replay = await scheduler.stop(
        project.project_id,
        batch.batch_id,
        key,
        {"expectedStatusRevision": 1, "reason": "读取最终事实"},
        force=force,
    )
    assert replay.operation_id == operation.operation_id
    factory.dispose()


def test_artifact_cleanup_requires_a_confirmed_missing_database_fact(tmp_path):
    factory, coordinator, project, batch, worker, core, _, _ = services(tmp_path)
    task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
    run = core.query_run(task.run_id)
    artifact_id = str(uuid4())
    relative_path = f"runs/{run.run_id}/generation-0/{artifact_id}.png"
    event = {
        "eventId": str(uuid4()),
        "runId": run.run_id,
        "executionGeneration": 0,
        "kind": "artifact",
        "nodeId": "click",
        "nodeVisitId": "visit-click",
        "attempt": 1,
        "occurredAt": "2026-09-15T00:00:00Z",
        "payload": {
            "artifactId": artifact_id,
            "kind": "screenshot",
            "purpose": "error",
            "availability": "available",
            "relativePath": relative_path,
            "mediaType": "image/png",
            "byteSize": 42,
            "sha256": "d" * 64,
        },
    }

    core._discard_uncommitted_artifact(run, event)
    assert worker.discarded == [(run.run_id, 0, artifact_id, relative_path)]

    with factory.begin() as session:
        from autoflow.infrastructure.database.workflow_runtime import (
            SqlAlchemyWorkflowRuntimeRepository,
        )

        SqlAlchemyWorkflowRuntimeRepository(session).append_event(event)
    core._discard_uncommitted_artifact(run, event)
    assert worker.discarded == [(run.run_id, 0, artifact_id, relative_path)]
    factory.dispose()


@pytest.mark.asyncio
async def test_stop_running_does_not_dispatch_remaining_tasks(tmp_path):
    factory, coordinator, project, batch, worker, core, scheduler, _ = services(
        tmp_path, wait=asyncio.Event()
    )
    await scheduler.tick()
    await asyncio.sleep(0)
    current = coordinator.get_batch(project.project_id, batch.batch_id)
    await scheduler.stop(
        project.project_id,
        batch.batch_id,
        str(uuid4()),
        {"expectedStatusRevision": current.status_revision, "reason": "测试"},
    )
    await scheduler.tick()
    await core.wait_idle()
    await scheduler.tick()
    assert len(worker.calls) == 1
    current = coordinator.get_batch(project.project_id, batch.batch_id)
    assert current.status == "stopped" and current.counts.by_status["cancelled"] == 3
    factory.dispose()


@pytest.mark.asyncio
async def test_restart_reconciles_running_before_considering_queued(tmp_path):
    factory, coordinator, project, batch, worker, core, scheduler, _ = services(
        tmp_path
    )
    task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
    core._transition_identity(task.run_id, "running", 1, 0)
    await core.startup()  # production bootstrap must run this before project scheduler
    await scheduler.tick()
    current = coordinator.get_batch(project.project_id, batch.batch_id)
    assert current.status == "interrupted"
    assert current.counts.by_status["interrupted"] == 1
    assert current.counts.by_status["cancelled"] == 2
    assert worker.calls == []
    factory.dispose()


@pytest.mark.asyncio
async def test_queued_batch_blocks_workspace_quiesce_even_without_http_request(
    tmp_path,
):
    factory, _, _, _, worker, _core, scheduler, gate = services(tmp_path)
    assert gate.pause(scheduler.blockers) == ["project_batches_active"]
    await scheduler.shutdown()
    assert (
        scheduler.blockers()
    )  # shutdown stops scheduling, not durable acceptance facts
    assert worker.calls == []
    factory.dispose()


@pytest.mark.asyncio
async def test_force_stop_unknown_owner_recovers_only_original_facts(tmp_path):
    factory, coordinator, project, batch, worker, core, scheduler, _ = services(
        tmp_path
    )
    task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
    core._transition_identity(task.run_id, "running", 1, 0)
    core._transition_identity(task.run_id, "reconciling", 2, 1)
    await scheduler.tick()
    current = coordinator.get_batch(project.project_id, batch.batch_id)
    assert current.status == "reconciling"
    key = str(uuid4())
    payload = {
        "expectedStatusRevision": current.status_revision,
        "reason": "核验并结束未知运行",
    }
    operation = await scheduler.stop(
        project.project_id, batch.batch_id, key, payload, force=True
    )
    await scheduler.tick()
    replay = await scheduler.stop(
        project.project_id, batch.batch_id, key, payload, force=True
    )
    assert (
        replay.operation_id == operation.operation_id and replay.status == "succeeded"
    )
    current = coordinator.get_batch(project.project_id, batch.batch_id)
    assert current.status == "stopped"
    assert current.counts.by_status["interrupted"] == 1
    assert current.counts.by_status["cancelled"] == 2
    assert worker.calls == []
    assert core.query_run(task.run_id).execution_generation == 2
    factory.dispose()


@pytest.mark.asyncio
async def test_force_stop_requires_normal_stop_and_grace(tmp_path):
    from autoflow.domain.project_runs.models import ProjectRunError
    from autoflow.domain.workflows.runtime import WorkflowRuntimeError

    factory, coordinator, project, batch, worker, core, scheduler, _ = services(
        tmp_path, wait=asyncio.Event()
    )
    await scheduler.tick()
    await asyncio.sleep(0)
    current = coordinator.get_batch(project.project_id, batch.batch_id)
    with pytest.raises(ProjectRunError, match="先停止"):
        await scheduler.stop(
            project.project_id,
            batch.batch_id,
            str(uuid4()),
            {"expectedStatusRevision": current.status_revision, "reason": "强制停止"},
            force=True,
        )
    task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
    run = core.query_run(task.run_id)
    core._transition_identity(
        run.run_id, "stopping", run.status_revision, run.execution_generation
    )
    await scheduler.stop(
        project.project_id,
        batch.batch_id,
        str(uuid4()),
        {"expectedStatusRevision": current.status_revision, "reason": "普通停止"},
    )
    current = coordinator.get_batch(project.project_id, batch.batch_id)
    allowed, available_at = scheduler.force_stop_availability(
        project.project_id, batch.batch_id
    )
    assert allowed is False
    assert available_at is not None
    with pytest.raises(WorkflowRuntimeError, match="宽限期"):
        await scheduler.stop(
            project.project_id,
            batch.batch_id,
            str(uuid4()),
            {"expectedStatusRevision": current.status_revision, "reason": "强制停止"},
            force=True,
        )
    worker.wait.set()
    await core.wait_idle()
    await scheduler.tick()
    factory.dispose()
