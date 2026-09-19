"""PM8-B: restart re-verification against durable facts, and visible residue.

Spec: ``docs/project-management/design/pm8-lifecycle-recovery.md`` §6.1 items
10-13.  Each item has exactly one covering test; where the fact is already
proven elsewhere this module names the test instead of re-implementing the rule.

* item 10 (non-terminal batches settle from core facts) -
  ``test_project_run_dispatch.py::test_restart_reconciles_running_before_considering_queued``.
  The "unknown keeps its occupancy" half is executed here, because no other test
  restarts while a real record lease is held.
* item 11 (publish-then-lose-result recovers or reports a conflict) -
  ``test_project_excel_exports.py`` for both export directions and
  ``tests/contract/test_pm2_excel_imports.py`` for
  ``test_chunk_interruption_stays_hidden_and_settles_after_shutdown`` /
  ``test_import_accepted_before_process_loss_is_not_replayed_at_startup``.
* item 12 (unknown send is never replayed) -
  ``test_project_sheets_recovery.py::test_an_unknown_send_stays_unknown_across_a_restart``.
* item 13 (revoked execution generations cannot write) -
  ``test_project_capability_fencing.py::test_old_execution_generation_read_evidence_cannot_authorize_dynamic_write``
  and ``::test_read_evidence_persists_across_service_instances_for_dynamic_write``.

Lifecycle command continuation (spec §3.5) has no other coverage and runs here.
"""

from __future__ import annotations

import shutil
from uuid import uuid4

import pytest
from sqlalchemy import select

from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.projects.lifecycle import (
    ProjectLifecycleCoordinator,
)
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_lifecycle import (
    SqlAlchemyProjectLifecycle,
)
from autoflow.infrastructure.database.project_run_models import ProjectRecordLeaseRow
from tests.fixtures.workflow_runs import SyntheticResources
from tests.integration.test_project_lifecycle import Context, _busy_environment
from tests.integration.test_project_run_data_start import _setup as setup_data_batch
from tests.integration.test_project_run_dispatch import Worker


def uid() -> str:
    return str(uuid4())


async def _noop_cleanup(_run) -> None:
    return None


async def _unverifiable_orphan(_run) -> None:
    """Production refuses to claim ownership it cannot prove (see workflow_recovery)."""
    raise RuntimeError("native orphan ownership could not be verified")


def _lease_states(factory, task_id: str) -> list[str]:
    with factory() as session:
        return list(
            session.scalars(
                select(ProjectRecordLeaseRow.state)
                .where(ProjectRecordLeaseRow.task_id == task_id)
                .order_by(ProjectRecordLeaseRow.lease_key)
            )
        )


def _restarted_lifecycle(
    context: Context,
) -> tuple[SqlAlchemyProjectLifecycle, ProjectLifecycleCoordinator]:
    """A second service instance over the same database: what a restart sees."""
    repository = SqlAlchemyProjectLifecycle(
        context.factory, environment_root=context.environment_root
    )
    return repository, ProjectLifecycleCoordinator(repository, QuiesceGate())


@pytest.mark.asyncio
async def test_restart_keeps_an_unverifiable_run_and_its_record_occupancy(tmp_path):
    factory, project_id, automation, coordinator = setup_data_batch(tmp_path)
    batch, _operation, _replayed = coordinator.start(
        project_id,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project_id, batch.batch_id)
        == "ready"
    )
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    held = _lease_states(factory, task.task_id)
    assert held == ["held", "held"]

    writer = WorkflowRunDispatcher(
        factory, Worker(), SyntheticResources(), QuiesceGate(), _noop_cleanup
    )
    queued = writer.query_run(task.run_id)
    assert queued.status == "queued"
    writer._transition_identity(
        task.run_id, "running", queued.status_revision, queued.execution_generation
    )
    running = writer.query_run(task.run_id)
    # Process loss without a stop command: the worker is gone, the fact is not.
    writer._transition_identity(
        task.run_id, "reconciling", running.status_revision, running.execution_generation
    )

    restarted_worker = Worker()
    restarted_gate = QuiesceGate()
    restarted = WorkflowRunDispatcher(
        factory,
        restarted_worker,
        SyntheticResources(),
        restarted_gate,
        _unverifiable_orphan,
    )
    restarted_scheduler = ProjectBatchScheduler(factory, restarted, restarted_gate)
    await restarted.startup()
    await restarted_scheduler.tick()

    assert restarted.query_run(task.run_id).status == "reconciling"
    current = coordinator.get_batch(project_id, batch.batch_id)
    assert current.status == "reconciling"
    assert current.counts.by_status["reconciling"] == 1
    assert restarted_worker.calls == []
    assert _lease_states(factory, task.task_id) == ["held", "held"]

    # A verified core fact (no live owner) is what releases the occupancy.
    resolved_worker = Worker()
    resolved_gate = QuiesceGate()
    resolved = WorkflowRunDispatcher(
        factory, resolved_worker, SyntheticResources(), resolved_gate, _noop_cleanup
    )
    resolved_scheduler = ProjectBatchScheduler(factory, resolved, resolved_gate)
    await resolved.startup()
    await resolved_scheduler.tick()

    finished = resolved.query_run(task.run_id)
    assert finished.status == "interrupted" and finished.terminal
    assert resolved_worker.calls == []
    assert _lease_states(factory, task.task_id) == ["released", "released"]
    assert coordinator.get_batch(project_id, batch.batch_id).status == "interrupted"
    factory.dispose()


@pytest.mark.asyncio
async def test_accepted_archive_finishes_on_a_restarted_service(tmp_path):
    context = Context(tmp_path)
    operation = context.archive()
    assert context.state() == "closing"

    repository, restarted = _restarted_lifecycle(context)
    assert repository.pending() == [context.project_id]
    await restarted.startup()
    try:
        await restarted.tick()
    finally:
        await restarted.shutdown()

    assert context.state() == "archived"
    saved = context.operation(operation.operation_id)
    assert saved.status == "succeeded"
    assert saved.result["lifecycleState"] == "archived"


@pytest.mark.asyncio
async def test_delete_residue_survives_a_restart_and_settles_once_files_are_gone(
    tmp_path,
):
    environment_root = tmp_path / "environments"
    context = Context(tmp_path, environment_root=environment_root)
    instance_id = _busy_environment(context.factory, context.project_id, state="closed")
    work_dir = environment_root / "instances" / instance_id
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "payload").write_text("x", encoding="utf-8")
    context.archive_to_settled()
    operation = context.delete()
    container = environment_root / "instances"
    container.chmod(0o500)
    try:
        context.repository.advance(context.project_id)
        assert context.state() == "deleting"

        repository, restarted = _restarted_lifecycle(context)
        assert repository.pending() == [context.project_id]
        # A restart must not turn residue into success, and must not lose it.
        await restarted.tick()
        assert context.state() == "deleting"
        saved = context.operation(operation.operation_id)
        assert saved.status == "failed"
        assert saved.error["code"] == "DELETE_CLEANUP_FAILED"
        assert str(work_dir) in saved.error["details"]["cleanup"]["residue"]
    finally:
        container.chmod(0o755)

    # The user retries from the archived directory once the files are usable again.
    retry = context.delete()
    with pytest.raises(ProjectError) as blocked:
        context.delete()
    assert blocked.value.status == 409 and context.state() == "deleting"

    await restarted.tick()
    assert context.state() == "deleted"
    assert context.operation(retry.operation_id).status == "succeeded"
    assert not work_dir.exists()
    shutil.rmtree(container, ignore_errors=True)


@pytest.mark.asyncio
async def test_delete_residue_that_clears_on_its_own_still_reports_its_operation(
    tmp_path,
):
    """Residue must never make the project disappear without a queryable fact."""
    environment_root = tmp_path / "environments"
    context = Context(tmp_path, environment_root=environment_root)
    instance_id = _busy_environment(context.factory, context.project_id, state="closed")
    work_dir = environment_root / "instances" / instance_id
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "payload").write_text("x", encoding="utf-8")
    context.archive_to_settled()
    operation = context.delete()
    container = environment_root / "instances"
    container.chmod(0o500)
    try:
        context.repository.advance(context.project_id)
    finally:
        container.chmod(0o755)
    assert context.state() == "deleting"

    repository, restarted = _restarted_lifecycle(context)
    assert repository.pending() == [context.project_id]
    # Nobody retries; the filesystem simply becomes usable again after a restart.
    await restarted.tick()

    assert context.state() == "deleted"
    saved = context.operation(operation.operation_id)
    assert saved.status == "succeeded"
    assert saved.result == {
        "target": {"type": "project", "projectId": context.project_id},
        "deleted": True,
    }
    recovered = context.projects.workspace_operation(operation.idempotency_key)
    assert recovered.operation_id == operation.operation_id
    shutil.rmtree(container, ignore_errors=True)
