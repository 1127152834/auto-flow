from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.application.project_runs.coordinator import ProjectRunCoordinator
from autoflow.application.projects.service import ProjectService
from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowPreparedContentRow,
    WorkflowRunRow,
)
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.fixtures.workflows import workflow_payload

PARAMETER_TEXT = "00000000-0000-0000-0000-000000000031"
PARAMETER_BOOL = "00000000-0000-0000-0000-000000000032"


def setup(tmp_path, resolver=None):
    database = tmp_path / "project-runs.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    projects = ProjectService(SqlAlchemyProjects(factory))
    project, _, _ = projects.create(
        str(uuid4()), {"name": "运行项目", "description": ""}
    )
    workflow_repository = SqlAlchemyWorkflowRepository(factory)
    workflow = WorkflowService(workflow_repository).create(
        workflow_payload(), str(uuid4())
    )
    automations = ProjectAutomationService(
        SqlAlchemyProjects(factory), SqlAlchemyProjectAutomations(factory)
    )
    automation, _, _ = automations.create(
        project.project_id,
        str(uuid4()),
        {
            "name": "参数自动化",
            "description": "",
            "workflowId": workflow.workflow_id,
            "inputPlan": {"inputs": []},
            "parameterSchema": [
                {
                    "parameterId": PARAMETER_TEXT,
                    "name": "文本",
                    "type": "string",
                    "required": True,
                },
                {
                    "parameterId": PARAMETER_BOOL,
                    "name": "启用",
                    "type": "boolean",
                    "required": False,
                    "defaultValue": False,
                },
            ],
            "environmentPolicy": {"source": "newFromProfile"},
            "runPolicy": {
                "maxTasks": 1,
                "concurrency": 1,
                "maxLiveInstances": 1,
                "continueAfterFailure": False,
                "automaticExecutionTimeoutSeconds": 60,
                "manualDeadlineSeconds": 300,
            },
        },
    )
    runtime = WorkflowRuntimeService(factory, workflow_repository)

    def resolve_resources(_automation, _defaults):
        # Synthetic integration seam: this test proves database atomicity, not a browser launch.
        return {"browser": "none", "modelProviderId": None}

    coordinator = ProjectRunCoordinator(
        factory,
        runtime,
        resolve_resources=resolver or resolve_resources,
        available_capabilities=["browser.cloakbrowser"],
    )
    return factory, projects, automations, coordinator, runtime, project, automation


def start_payload(automation, *, max_tasks=1):
    return {
        "expectedAutomationRevision": automation.management_revision,
        "parameters": {PARAMETER_TEXT: "每个任务的冻结值"},
        "maxTasks": max_tasks,
        "concurrency": 1,
    }


def test_environment_reservation_failure_rolls_back_task_run_and_acceptance(tmp_path):
    from autoflow.application.environments.service import EnvironmentService
    from autoflow.domain.projects.models import ProjectError
    from autoflow.infrastructure.database.environment_models import (
        ProjectEnvironmentInstanceRow,
    )
    from autoflow.infrastructure.database.environments import SqlAlchemyEnvironments
    from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore

    factory, projects, _, coordinator, _, project, automation = setup(tmp_path)
    with factory() as session:
        row = session.get(ProjectRow, project.project_id)
        row.default_resources = {**row.default_resources, "profileId": str(uuid4())}
        session.commit()
    coordinator._resolve_resources = lambda _automation, defaults: {"browser": "newFromProfile", "profileId": defaults["profileId"]}
    coordinator._environments = EnvironmentService(
        projects, SqlAlchemyEnvironments(factory), EnvironmentStore(tmp_path / "environments"),
        max_live_instances=1,
    )
    key = str(uuid4())
    with pytest.raises(ProjectError) as failure:
        coordinator.start(project.project_id, automation.automation_id, key,
                          start_payload(automation, max_tasks=2))
    assert failure.value.code == "CAPACITY_EXHAUSTED"
    with factory() as session:
        for model in (ProjectTaskRow, ProjectTaskInputSnapshotRow, WorkflowRunRow,
                      ProjectBatchRow, WorkflowPreparedContentRow, ProjectEnvironmentInstanceRow):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.scalar(select(ProjectOperationRow).where(
            ProjectOperationRow.idempotency_key == key)) is None
    factory.dispose()


def test_environment_reservation_commits_with_task_and_replay_reuses_instance(tmp_path):
    from autoflow.application.environments.service import EnvironmentService
    from autoflow.infrastructure.database.environment_models import (
        ProjectEnvironmentInstanceRow,
    )
    from autoflow.infrastructure.database.environments import SqlAlchemyEnvironments
    from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore

    factory, projects, _, coordinator, _, project, automation = setup(tmp_path)
    with factory() as session:
        row = session.get(ProjectRow, project.project_id)
        row.default_resources = {**row.default_resources, "profileId": str(uuid4())}
        session.commit()
    environment_service = EnvironmentService(
        projects, SqlAlchemyEnvironments(factory), EnvironmentStore(tmp_path / "environments"),
        max_live_instances=1,
    )
    coordinator._resolve_resources = lambda _automation, defaults: {"browser": "newFromProfile", "profileId": defaults["profileId"]}
    coordinator._environments = environment_service
    key = str(uuid4())
    batch, operation, replayed = coordinator.start(
        project.project_id, automation.automation_id, key, start_payload(automation)
    )
    assert not replayed
    repeated, repeated_operation, replayed = coordinator.start(
        project.project_id, automation.automation_id, key, start_payload(automation)
    )
    assert replayed and repeated == batch and repeated_operation == operation
    with factory() as session:
        instances = session.scalars(select(ProjectEnvironmentInstanceRow)).all()
        assert len(instances) == 1
        instance = instances[0]
        task = session.get(ProjectTaskRow, instance.active_task_id)
        assert task is not None and task.run_id == instance.active_run_id
        assert instance.state == "active"
        assert environment_service.instance_path(instance.id).is_dir()
    factory.dispose()


@pytest.mark.asyncio
async def test_project_run_acquires_its_reserved_persistent_directory(tmp_path, valid_profile_values):
    from autoflow.application.environments.service import EnvironmentService
    from autoflow.domain.projects.models import ProjectError
    from autoflow.infrastructure.database.environments import SqlAlchemyEnvironments
    from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore
    from tests.unit.test_workflow_browser_resources import resources

    browser, _, profile = resources(tmp_path, valid_profile_values)
    factory, projects, _, coordinator, runtime, project, automation = setup(
        tmp_path, resolver=lambda *_: browser.freeze(profile.id)
    )
    with factory() as session:
        row = session.get(ProjectRow, project.project_id)
        row.default_resources = {**row.default_resources, "profileId": profile.id}
        session.commit()
    environment_service = EnvironmentService(
        projects, SqlAlchemyEnvironments(factory), EnvironmentStore(tmp_path / "environments")
    )
    coordinator._environments = environment_service
    batch, _, _ = coordinator.start(
        project.project_id, automation.automation_id, str(uuid4()), start_payload(automation)
    )
    task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
    queued = runtime.query_run(run_id=task.run_id)
    running = runtime.dispatch_run(
        queued.run_id, expected_status_revision=queued.status_revision,
        execution_generation=queued.execution_generation,
    )
    instance = environment_service.environments.find_instance_by_task(project.project_id, task.task_id)
    browser._environment_directory = lambda request_id: environment_service.run_work_directory(request_id)
    lease = await browser.acquire(running.resource_request, running.run_request_id)
    try:
        assert lease.browser["userDataDir"] == str(environment_service.instance_path(instance.instance_id))
    finally:
        lease.release()
    runtime.cancel_run(
        running.run_id, expected_status_revision=running.status_revision,
        execution_generation=running.execution_generation,
    )
    with pytest.raises(ProjectError) as revoked:
        await browser.acquire(running.resource_request, running.run_request_id)
    assert revoked.value.code == "END_ACCESS_REVOKED"
    # A still-open instance must not be savable: quiescence precedes generation checks.
    with pytest.raises(ProjectError) as not_quiescent:
        environment_service.save(
            project.project_id,
            str(uuid4()),
            {
                "instanceId": instance.instance_id, "mode": "saveAs",
                "expectedUseGeneration": 1, "executionGeneration": running.execution_generation,
                "name": "未静止环境",
            },
        )
    assert not_quiescent.value.code == "INSTANCE_NOT_QUIESCENT"
    environment_service.environments.set_instance_state(instance.instance_id, "closed")
    # Once quiescent, a revoked execution generation cannot publish the environment.
    with pytest.raises(ProjectError) as stale_save:
        environment_service.save(
            project.project_id,
            str(uuid4()),
            {
                "instanceId": instance.instance_id, "mode": "saveAs",
                "expectedUseGeneration": 1, "executionGeneration": running.execution_generation,
                "currentExecutionGeneration": running.execution_generation + 1,
                "name": "旧执行代次",
            },
        )
    assert stale_save.value.code == "EXECUTION_GENERATION_REVOKED"
    factory.dispose()
    factory.dispose()


@pytest.mark.parametrize("count", [1, 2, 100])
def test_start_commits_every_task_snapshot_run_content_and_operation_atomically(
    tmp_path, count
):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)

    batch, operation, replayed = coordinator.start(
        project.project_id,
        automation.automation_id,
        str(uuid4()),
        start_payload(automation, max_tasks=count),
    )

    assert not replayed and operation.status == "succeeded"
    assert batch.requested_count == count
    tasks = coordinator.list_tasks(project.project_id, batch.batch_id)
    assert len(tasks) == count
    assert len({task.task_id for task in tasks}) == count
    assert len({task.run_id for task in tasks}) == count
    assert len({task.run_request_id for task in tasks}) == count
    assert {task.status for task in tasks} == {"queued"}
    with factory() as session:
        snapshots = session.scalars(
            select(ProjectTaskInputSnapshotRow).where(
                ProjectTaskInputSnapshotRow.batch_id == batch.batch_id
            )
        ).all()
        runs = session.scalars(
            select(WorkflowRunRow).where(
                WorkflowRunRow.id.in_([task.run_id for task in tasks])
            )
        ).all()
        stored_batch = session.get(ProjectBatchRow, batch.batch_id)
        assert stored_batch is not None
        prepared = session.scalars(
            select(WorkflowPreparedContentRow).where(
                WorkflowPreparedContentRow.id == stored_batch.prepared_content_id
            )
        ).all()
        stored_operation = session.get(ProjectOperationRow, operation.operation_id)
    assert len(snapshots) == len(runs) == count and len(prepared) == 1
    assert {snapshot.task_id for snapshot in snapshots} == {
        task.task_id for task in tasks
    }
    assert all(snapshot.inputs == [] for snapshot in snapshots)
    assert all(
        snapshot.parameters
        == {PARAMETER_TEXT: "每个任务的冻结值", PARAMETER_BOOL: False}
        for snapshot in snapshots
    )
    assert (
        stored_operation is not None
        and stored_operation.result["batch"]["batchId"] == batch.batch_id
    )
    factory.dispose()


def test_replay_returns_the_original_batch_even_after_automation_changes_and_mismatch_conflicts(
    tmp_path,
):
    factory, _, automations, coordinator, _, project, automation = setup(tmp_path)
    key = str(uuid4())
    payload = start_payload(automation, max_tasks=2)
    original, original_operation, _ = coordinator.start(
        project.project_id, automation.automation_id, key, payload
    )
    automations.update(
        project.project_id,
        automation.automation_id,
        str(uuid4()),
        {
            "name": "已修改",
            "description": "",
            "workflowId": automation.workflow_id,
            "inputPlan": automation.input_plan,
            "parameterSchema": automation.parameter_schema,
            "environmentPolicy": automation.environment_policy,
            "runPolicy": automation.run_policy,
            "expectedManagementRevision": automation.management_revision,
        },
    )

    replay, replay_operation, replayed = coordinator.start(
        project.project_id, automation.automation_id, key, payload
    )
    assert replayed and replay == original and replay_operation == original_operation
    with pytest.raises(ProjectRunError) as mismatch:
        coordinator.start(
            project.project_id,
            automation.automation_id,
            key,
            {**payload, "maxTasks": 1},
        )
    assert mismatch.value.code == "OPERATION_PAYLOAD_MISMATCH"
    factory.dispose()


def test_stale_revision_rejects_without_any_run_rows(tmp_path):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    with pytest.raises(ProjectRunError) as error:
        coordinator.start(
            project.project_id,
            automation.automation_id,
            str(uuid4()),
            {
                **start_payload(automation),
                "expectedAutomationRevision": automation.management_revision + 1,
            },
        )
    assert error.value.code == "REVISION_CONFLICT"
    _assert_no_started_rows(factory)
    factory.dispose()


def test_second_core_prepare_run_failure_rolls_back_the_whole_start(
    tmp_path, monkeypatch
):
    factory, _, _, coordinator, runtime, project, automation = setup(tmp_path)
    original = runtime.prepare_run
    calls = 0

    def fail_second(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected second prepare_run failure")
        return original(**kwargs)

    monkeypatch.setattr(runtime, "prepare_run", fail_second)
    with pytest.raises(RuntimeError, match="second prepare_run"):
        coordinator.start(
            project.project_id,
            automation.automation_id,
            str(uuid4()),
            start_payload(automation, max_tasks=2),
        )
    _assert_no_started_rows(factory)
    factory.dispose()


def test_resource_resolution_failure_rolls_back_content_and_operation(tmp_path):
    def unavailable(_automation, _defaults):
        raise ProjectRunError("RESOURCE_UNAVAILABLE", "资源不可用", 422)

    factory, _, _, coordinator, _, project, automation = setup(tmp_path, unavailable)
    with pytest.raises(ProjectRunError, match="资源不可用"):
        coordinator.start(
            project.project_id,
            automation.automation_id,
            str(uuid4()),
            start_payload(automation),
        )
    _assert_no_started_rows(factory)
    factory.dispose()


@pytest.mark.parametrize("state", ["closing", "archived"])
def test_project_lifecycle_blocks_new_batches(tmp_path, state):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    with factory() as session:
        session.get(ProjectRow, project.project_id).lifecycle_state = state
        session.commit()
    with pytest.raises(ProjectRunError):
        coordinator.start(
            project.project_id,
            automation.automation_id,
            str(uuid4()),
            start_payload(automation),
        )
    _assert_no_started_rows(factory)
    factory.dispose()


def test_batch_and_tasks_enforce_project_ownership(tmp_path):
    factory, projects, _, coordinator, _, project, automation = setup(tmp_path)
    other, _, _ = projects.create(str(uuid4()), {"name": "其他项目", "description": ""})
    batch, _, _ = coordinator.start(
        project.project_id,
        automation.automation_id,
        str(uuid4()),
        start_payload(automation),
    )
    with pytest.raises(ProjectRunError):
        coordinator.get_batch(other.project_id, batch.batch_id)
    with pytest.raises(ProjectRunError):
        coordinator.list_tasks(other.project_id, batch.batch_id)
    factory.dispose()


def test_concurrent_same_key_creates_one_batch(tmp_path):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    key, payload = str(uuid4()), start_payload(automation, max_tasks=2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: coordinator.start(
                    project.project_id, automation.automation_id, key, payload
                ),
                range(2),
            )
        )
    assert len({result[0].batch_id for result in results}) == 1
    assert sorted(result[2] for result in results) == [False, True]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ProjectBatchRow)) == 1
        assert session.scalar(select(func.count()).select_from(ProjectTaskRow)) == 2
    factory.dispose()


def _assert_no_started_rows(factory):
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ProjectBatchRow)) == 0
        assert session.scalar(select(func.count()).select_from(ProjectTaskRow)) == 0
        assert (
            session.scalar(
                select(func.count()).select_from(ProjectTaskInputSnapshotRow)
            )
            == 0
        )
        assert (
            session.scalar(select(func.count()).select_from(WorkflowPreparedContentRow))
            == 0
        )
        assert session.scalar(select(func.count()).select_from(WorkflowRunRow)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(ProjectOperationRow)
                .where(ProjectOperationRow.kind == "startBatch")
            )
            == 0
        )


@pytest.mark.parametrize("first_action", ["read", "start"])
def test_final_commit_failure_discards_connection_transaction_before_next_start(
    tmp_path, monkeypatch, first_action
):
    import sqlite3

    from sqlalchemy.exc import OperationalError

    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    engine = factory.kw["bind"]
    original_commit = engine.dialect.do_commit

    def fail_commit(_connection):
        raise sqlite3.OperationalError("injected final commit failure")

    monkeypatch.setattr(engine.dialect, "do_commit", fail_commit)
    with pytest.raises(OperationalError, match="final commit failure"):
        coordinator.start(
            project.project_id,
            automation.automation_id,
            str(uuid4()),
            start_payload(automation, max_tasks=2),
        )
    monkeypatch.setattr(engine.dialect, "do_commit", original_commit)
    if first_action == "read":
        _assert_no_started_rows(factory)
    accepted, _, _ = coordinator.start(
        project.project_id,
        automation.automation_id,
        str(uuid4()),
        start_payload(automation),
    )
    assert accepted.counts.created_task_count == 1
    factory.dispose()
