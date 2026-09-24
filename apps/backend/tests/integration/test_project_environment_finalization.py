"""Terminal core runs release disposable copies, never pending retention data."""
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from autoflow.application.environments.service import EnvironmentService
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.projects.service import ProjectService
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.environments import SqlAlchemyEnvironments
from autoflow.infrastructure.database.project_run_models import ProjectBatchRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore
from tests.contract.test_project_environments import _closed_instance
from tests.integration.test_project_run_evidence import _claim
from tests.integration.test_project_task_cleanup import _cleanup_of


def setup_copy(tmp_path, status="succeeded", state="active", persistent=False):
    factory, project, _coordinator, task = _claim(tmp_path)
    service = EnvironmentService(
        ProjectService(SqlAlchemyProjects(factory)), SqlAlchemyEnvironments(factory),
        EnvironmentStore(tmp_path / "copies"), closer=lambda _service, _instance: None,
    )
    policy = {"source": "newFromProfile", "profileId": str(uuid4())}
    if persistent:
        source = _closed_instance(service, project, b"original login")
        saved = service.save(project, str(uuid4()), {
            "instanceId": source.instance_id, "mode": "save_as", "name": "source",
            "expectedUseGeneration": 1, "executionGeneration": 1,
        })[0]
        service.close_instance(project, source.instance_id, None)
        policy = {"source": "fixedEnvironment", "environmentId": saved["saved"]["environmentId"]}
    instance = service.reserve(
        project, service.resolve(project, policy),
        task_id=task.task_id, run_id=task.run_id, holder_kind="task", holder_id=task.task_id,
    )
    service.environments.set_instance_state(instance.instance_id, state)
    directory = service.instance_path(instance.instance_id)
    (directory / "Cookies").write_bytes(b"must not lose retained login")
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.status = status
        run.completed_at = datetime.now(UTC)
        # Recovery must also discover copies belonging to already closed batches.
        session.get(ProjectBatchRow, task.batch_id).status = "completed"
    scheduler = ProjectBatchScheduler(factory, None, QuiesceGate(), service)
    return factory, project, task, service, instance, directory, scheduler


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["succeeded", "failed", "cancelled", "timed_out", "interrupted"])
async def test_terminal_task_removes_real_work_copy_even_after_batch_closed(tmp_path, status):
    factory, project, task, service, instance, directory, scheduler = setup_copy(tmp_path, status)
    await scheduler.tick()
    assert not directory.exists()
    assert service.environments.get_instance(project, instance.instance_id).state == "cleaned"
    assert _cleanup_of(factory, project, task.task_id)["status"] == "succeeded"
    await scheduler.tick()  # idempotent recovery


@pytest.mark.asyncio
@pytest.mark.parametrize("status,state", [
    ("running", "active"), ("reconciling", "active"), ("waiting_manual", "active"),
    ("succeeded", "waiting_manual"), ("succeeded", "saving"), ("succeeded", "unknown"),
])
async def test_unconfirmed_or_retained_copy_is_not_automatically_removed(tmp_path, status, state):
    _factory, project, _task, service, instance, directory, scheduler = setup_copy(tmp_path, status, state)
    await scheduler.tick()
    assert (directory / "Cookies").read_bytes() == b"must not lose retained login"
    assert service.environments.get_instance(project, instance.instance_id).state == state


@pytest.mark.asyncio
async def test_failed_save_before_candidate_creation_protects_copy(tmp_path):
    factory, project, task, service, instance, directory, scheduler = setup_copy(tmp_path, status="running", state="closed")
    # Admit an authorized save before the run ends; invalid metadata fails before
    # a candidate is created. A revoked request must not create retention intent.
    with pytest.raises(ProjectError) as failure:
        service.save(project, str(uuid4()), {
            "instanceId": instance.instance_id, "mode": "save_as", "name": " " * 5,
            "expectedUseGeneration": 1, "executionGeneration": 1,
        })
    assert failure.value.code == "VALIDATION_ERROR"
    with factory.begin() as session:
        session.get(WorkflowRunRow, task.run_id).status = "succeeded"
    await scheduler.tick()
    assert (directory / "Cookies").read_bytes() == b"must not lose retained login"
    assert service.environments.get_instance(project, instance.instance_id).state == "closed"


@pytest.mark.asyncio
async def test_disk_failure_is_visible_and_next_tick_retries(tmp_path, monkeypatch):
    factory, project, task, service, instance, directory, scheduler = setup_copy(tmp_path)
    close = service.store.close_instance
    def denied(_instance_id):
        raise PermissionError("injected disk failure")
    monkeypatch.setattr(service.store, "close_instance", denied)
    await scheduler.tick()
    assert directory.exists()
    assert _cleanup_of(factory, project, task.task_id)["status"] == "failed"
    monkeypatch.setattr(service.store, "close_instance", close)
    await scheduler.tick()
    assert not directory.exists()
    assert service.environments.get_instance(project, instance.instance_id).state == "cleaned"


@pytest.mark.asyncio
async def test_cleanup_failure_keeps_source_occupied_and_retry_preserves_generation(tmp_path, monkeypatch):
    _factory, project, _task, service, instance, directory, scheduler = setup_copy(tmp_path, persistent=True)
    source = service.store.generation_dir(instance.environment_id, 1)
    before = service.store.digest(source)
    close = service.store.close_instance
    def denied(_instance_id):
        raise PermissionError("injected disk failure")
    monkeypatch.setattr(service.store, "close_instance", denied)
    await scheduler.tick()
    assert service.environments.get_with_instance(project, instance.environment_id)[1] is not None
    monkeypatch.setattr(service.store, "close_instance", close)
    await scheduler.tick()
    assert not directory.exists()
    assert service.environments.get_with_instance(project, instance.environment_id)[1] is None
    assert service.store.digest(source) == before
    assert (source / "Default" / "Cookies").read_bytes() == b"original login"


@pytest.mark.asyncio
async def test_browser_close_must_be_confirmed_before_deleting_copy(tmp_path):
    from autoflow.domain.environments.rules import environment_error
    factory, project, task, service, _instance, directory, scheduler = setup_copy(tmp_path)
    def still_open(_service, _instance):
        raise environment_error("INSTANCE_NOT_QUIESCENT", "still open", 409)
    service._closer = still_open
    await scheduler.tick()
    assert directory.exists()
    assert _cleanup_of(factory, project, task.task_id)["status"] == "failed"


@pytest.mark.asyncio
async def test_accepted_retain_end_is_protected_before_a_save_candidate_exists(tmp_path):
    _factory, project, _task, service, instance, directory, scheduler = setup_copy(tmp_path)
    now = datetime.now(UTC)
    service.environments.accept_operation(service._command(
        str(uuid4()), "saveEnvironment", project, instance.instance_id,
        {"scope": "endTask", "request": {"instanceId": instance.instance_id,
         "retainEnvironment": {"enabled": True}}}, now,
    ))
    await scheduler.tick()
    assert directory.exists()
    assert service.environments.get_instance(project, instance.instance_id).state == "active"


@pytest.mark.asyncio
async def test_stop_writing_gate_defers_automatic_cleanup(tmp_path):
    _factory, _project, _task, _service, _instance, directory, scheduler = setup_copy(tmp_path)
    assert scheduler._gate.pause(list) == []
    await scheduler.tick()
    assert directory.exists()
    scheduler._gate.resume()
    await scheduler.tick()
    assert not directory.exists()


@pytest.mark.asyncio
async def test_legacy_save_with_unknown_instance_is_not_a_deletion_authorization(tmp_path):
    _factory, project, _task, service, _instance, directory, scheduler = setup_copy(tmp_path)
    # Old operation records carry only the environment resource, not instanceId.
    from dataclasses import replace
    operation = service._command(str(uuid4()), "saveEnvironment", project, None, {}, datetime.now(UTC))
    service.environments.accept_operation(replace(operation, resource={"type": "environment", "projectId": project, "environmentId": None}))
    await scheduler.tick()
    assert directory.exists()


@pytest.mark.asyncio
async def test_save_in_flight_and_cleanup_share_the_instance_lock(tmp_path, monkeypatch):
    import asyncio
    from threading import Event
    factory, project, task, service, instance, directory, scheduler = setup_copy(tmp_path, status="running", state="closed")
    started, release = Event(), Event()
    original = service.store.stage_candidate
    def stage_candidate(*args):
        started.set()
        assert release.wait(5)
        return original(*args)
    # PM9 admission fences terminal runs. End the run only after this save is
    # accepted, while candidate creation still owns the instance lifecycle lock.
    monkeypatch.setattr(service.store, "stage_candidate", stage_candidate)
    save = asyncio.create_task(asyncio.to_thread(service.save, project, str(uuid4()), {
        "instanceId": instance.instance_id, "mode": "save_as", "name": "safe",
        "expectedUseGeneration": 1, "executionGeneration": 1,
    }))
    assert await asyncio.to_thread(started.wait, 5)
    with factory.begin() as session:
        session.get(WorkflowRunRow, task.run_id).status = "succeeded"
    # The scheduler already excludes accepted saves. A direct cleanup request
    # must additionally wait for the same lock rather than removing a live save.
    await scheduler.tick()
    assert directory.exists()
    assert service.environments.get_instance(project, instance.instance_id).state == "saving"
    cleanup = asyncio.create_task(asyncio.to_thread(
        service.close_instance, project, instance.instance_id, instance.environment_id,
    ))
    try:
        await asyncio.sleep(0.05)
        assert directory.exists()
        assert not cleanup.done()
    finally:
        release.set()
    outcome, _operation, _replayed = await save
    await cleanup
    saved = service.store.generation_dir(outcome["saved"]["environmentId"], 1)
    assert (saved / "Cookies").read_bytes() == b"must not lose retained login"
    assert not directory.exists()


@pytest.mark.asyncio
async def test_manual_request_cannot_resurrect_an_already_cleaned_task_copy(tmp_path):
    _factory, project, task, service, instance, directory, scheduler = setup_copy(tmp_path)
    await scheduler.tick()
    with pytest.raises(ProjectError) as failure:
        service.open_manual(project, {"instanceId": instance.instance_id, "taskId": task.task_id, "runId": task.run_id})
    assert failure.value.code == "ENVIRONMENT_UNAVAILABLE"
    assert service.environments.get_instance(project, instance.instance_id).state == "cleaned"
    assert not directory.exists()


@pytest.mark.asyncio
async def test_cleanup_does_not_hold_the_batch_stop_admission_lock(tmp_path):
    import asyncio
    from threading import Event
    _factory, project, task, service, _instance, _directory, scheduler = setup_copy(tmp_path)
    started, release = Event(), Event()
    def close(_service, _instance):
        started.set()
        assert release.wait(5)
    service._closer = close
    cleanup = asyncio.create_task(scheduler.tick())
    assert await asyncio.to_thread(started.wait, 5)
    try:
        operation = await asyncio.wait_for(scheduler.stop(project, task.batch_id, str(uuid4()), {
            "expectedStatusRevision": 1, "reason": "stop must remain responsive",
        }), 1)
        assert operation.kind == "stopBatch"
    finally:
        release.set()
        await cleanup


@pytest.mark.asyncio
async def test_slow_terminal_cleanup_is_deferred_while_another_core_run_is_active(tmp_path):
    from tests.fixtures.workflow_runs import create_queued_run
    factory, _project, _task, _service, _instance, directory, scheduler = setup_copy(tmp_path)
    other, _content = create_queued_run(factory)
    with factory.begin() as session:
        session.get(WorkflowRunRow, other.run_id).status = "running"
    await scheduler.tick()
    assert directory.exists()
    with factory.begin() as session:
        session.get(WorkflowRunRow, other.run_id).status = "cancelled"
    await scheduler.tick()
    assert not directory.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected_generation,execution_generation", [
    ("running", 99, 1), ("running", 1, 2), ("succeeded", 1, 1),
])
async def test_rejected_save_cannot_create_retention_intent(
    tmp_path, status, expected_generation, execution_generation,
):
    from sqlalchemy import select

    from autoflow.infrastructure.database.models import ProjectOperationRow

    factory, project, task, service, instance, directory, scheduler = setup_copy(
        tmp_path, status=status, state="closed",
    )
    with pytest.raises(ProjectError) as rejected:
        service.save(project, str(uuid4()), {
            "instanceId": instance.instance_id, "mode": "save_as", "name": "rejected",
            "expectedUseGeneration": expected_generation,
            "executionGeneration": execution_generation,
        })
    assert rejected.value.code == "CAPABILITY_SCOPE_DENIED"
    assert (directory / "Cookies").read_bytes() == b"must not lose retained login"
    with factory.begin() as session:
        assert session.scalar(select(ProjectOperationRow).where(
            ProjectOperationRow.project_id == project,
            ProjectOperationRow.kind == "saveEnvironment",
        )) is None
        session.get(WorkflowRunRow, task.run_id).status = "succeeded"
    await scheduler.tick()
    assert not directory.exists()
    assert service.environments.get_instance(project, instance.instance_id).state == "cleaned"
