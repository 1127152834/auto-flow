"""PM7-C contract counterexamples for failed-Task follow-up Batches."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.projects.service import ProjectService
from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectRecordLeaseRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.integration.test_project_run_data_start import _setup, uid


def _payload(revision: int, overrides: dict | None = None) -> dict:
    return {
        "mode": "originalInputGroup",
        "expectedTaskStatusRevision": revision,
        "parameterOverrides": overrides or {},
    }


def _claim(project_id: str, factory, batch_id: str) -> str:
    return ProjectBatchScheduler.claim_data_task(factory, project_id, batch_id)


def _fail_run(factory, run_id: str) -> WorkflowRunRow:
    runtime = WorkflowRuntimeService(factory)
    queued = runtime.query_run(run_id=run_id)
    assert queued is not None
    running = runtime.dispatch_run(
        run_id,
        expected_status_revision=queued.status_revision,
        execution_generation=queued.execution_generation,
    )
    finishing = runtime._transition(
        run_id,
        target_status="finishing",
        expected_status_revision=running.status_revision,
        execution_generation=running.execution_generation,
    )
    runtime._transition(
        run_id,
        target_status="failed",
        expected_status_revision=finishing.status_revision,
        execution_generation=finishing.execution_generation,
    )
    failed = runtime.query_run(run_id=run_id)
    assert failed is not None and failed.status == "failed"
    return failed


def _failed_task(tmp_path):
    """One accepted Batch whose single Task ran and failed with two pinned rows."""
    factory, project_id, automation, coordinator = _setup(tmp_path)
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
    assert _claim(project_id, factory, batch.batch_id) == "ready"
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    run = _fail_run(factory, task.run_id)
    return factory, project_id, automation, coordinator, batch, task, run


def _counts(factory) -> tuple[int, int]:
    with factory() as session:
        return (
            session.scalar(select(func.count()).select_from(ProjectBatchRow)),
            session.scalar(select(func.count()).select_from(ProjectOperationRow)),
        )


def test_follow_up_pins_the_original_input_group_of_a_failed_task(tmp_path):
    factory, project_id, _automation, coordinator, _batch, task, run = _failed_task(
        tmp_path
    )
    batch, operation, replayed = coordinator.follow_up(
        project_id, task.task_id, uid(), _payload(run.status_revision)
    )
    assert not replayed
    assert operation.kind == "followUpBatch"
    assert operation.status == "succeeded"
    with factory() as session:
        row = session.get(ProjectBatchRow, batch.batch_id)
        assert row is not None
        frozen = row.frozen_request
    follow_up = frozen["followUp"]
    assert follow_up["sourceTaskId"] == task.task_id
    assert follow_up["sourceBatchId"] == task.batch_id
    assert follow_up["sourceTaskRevision"] == run.status_revision
    assert frozen["maxTasks"] == 1 and frozen["concurrency"] == 1
    restriction = follow_up["candidateRestriction"]
    assert len(restriction) == 2
    refs = [ref for values in restriction.values() for ref in values]
    assert len(refs) == 2
    assert {ref["recordKey"]["type"] for ref in refs} == {"uuid"}
    factory.dispose()


def test_replaying_the_same_key_returns_the_same_batch_and_creates_nothing(tmp_path):
    factory, project_id, _automation, coordinator, _batch, task, run = _failed_task(
        tmp_path
    )
    key = uid()
    first, _operation, replayed = coordinator.follow_up(
        project_id, task.task_id, key, _payload(run.status_revision)
    )
    before = _counts(factory)
    second, operation, replayed = coordinator.follow_up(
        project_id, task.task_id, key, _payload(run.status_revision)
    )
    assert replayed and operation.kind == "followUpBatch"
    assert second.batch_id == first.batch_id
    assert _counts(factory) == before
    factory.dispose()


def test_same_key_with_a_different_body_is_rejected(tmp_path):
    factory, project_id, _automation, coordinator, _batch, task, run = _failed_task(
        tmp_path
    )
    key = uid()
    coordinator.follow_up(
        project_id, task.task_id, key, _payload(run.status_revision)
    )
    before = _counts(factory)
    with pytest.raises(ProjectRunError) as failure:
        coordinator.follow_up(
            project_id,
            task.task_id,
            key,
            _payload(run.status_revision, {"anything": "else"}),
        )
    assert failure.value.code == "OPERATION_PAYLOAD_MISMATCH"
    assert failure.value.status == 409
    assert _counts(factory) == before
    factory.dispose()


def test_stale_task_revision_conflicts_without_creating_any_object(tmp_path):
    factory, project_id, _automation, coordinator, _batch, task, run = _failed_task(
        tmp_path
    )
    before = _counts(factory)
    with pytest.raises(ProjectRunError) as failure:
        coordinator.follow_up(
            project_id, task.task_id, uid(), _payload(run.status_revision - 1)
        )
    assert failure.value.code == "TASK_REVISION_CONFLICT"
    assert failure.value.status == 409
    assert _counts(factory) == before
    with factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(ProjectRecordLeaseRow)) == 2
        )
    factory.dispose()


def test_a_running_task_cannot_be_followed_up(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
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
    assert _claim(project_id, factory, batch.batch_id) == "ready"
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    before = _counts(factory)
    with pytest.raises(ProjectRunError) as failure:
        coordinator.follow_up(project_id, task.task_id, uid(), _payload(1))
    assert failure.value.code == "FOLLOW_UP_NOT_ALLOWED"
    assert failure.value.status == 409
    assert _counts(factory) == before
    factory.dispose()


def test_a_task_of_another_project_is_not_found(tmp_path):
    factory, _project_id, _automation, coordinator, _batch, task, run = _failed_task(
        tmp_path
    )
    other = ProjectService(SqlAlchemyProjects(factory)).create(
        str(uuid4()), {"name": "另一个项目", "description": ""}
    )[0]
    with pytest.raises(ProjectRunError) as failure:
        coordinator.follow_up(
            other.project_id, task.task_id, uid(), _payload(run.status_revision)
        )
    assert failure.value.code == "NOT_FOUND"
    assert failure.value.status == 404
    factory.dispose()


def test_a_deleted_candidate_row_is_never_replaced_by_another_row(tmp_path):
    factory, project_id, _automation, coordinator, _batch, task, run = _failed_task(
        tmp_path
    )
    with factory() as session:
        versions = list(session.scalars(select(DataRecordRow)))
        assert len(versions) == 2
        emails = next(row for row in versions if row.values_json)
        # A fresh row that a widening implementation would silently pick up.
        spare = DataRecordRow(
            project_id=emails.project_id,
            table_id=emails.table_id,
            dataset_generation=emails.dataset_generation,
            key_type=emails.key_type,
            key_value=str(uuid4()),
            values_json={},
            record_slots={},
            status_id=None,
            current_environment_id=None,
            content_revision=1,
            status_revision=1,
            link_revision=1,
            deleted=False,
            created_at=emails.created_at,
            updated_at=emails.updated_at,
        )
        session.add(spare)
        emails.deleted = True
        session.commit()
        spare_key = spare.key_value
    batch, _operation, _replayed = coordinator.follow_up(
        project_id, task.task_id, uid(), _payload(run.status_revision)
    )
    assert _claim(project_id, factory, batch.batch_id) == "noMatch"
    with factory() as session:
        row = session.get(ProjectBatchRow, batch.batch_id)
        assert row is not None and row.selection_outcome["status"] == "noMatch"
        assert session.scalar(select(func.count()).select_from(ProjectTaskRow)) == 1
        snapshots = list(session.scalars(select(ProjectTaskInputSnapshotRow)))
        assert len(snapshots) == 1
        assert all(
            item["recordRef"]["recordKey"]["value"] != spare_key
            for item in snapshots[0].inputs
        )
    factory.dispose()


def test_follow_up_leaves_the_source_task_and_business_status_untouched(tmp_path):
    factory, project_id, _automation, coordinator, _batch, task, run = _failed_task(
        tmp_path
    )
    with factory() as session:
        before_task = session.get(ProjectTaskRow, task.task_id)
        assert before_task is not None
        before_run = session.get(WorkflowRunRow, task.run_id)
        assert before_run is not None
        before_record = {
            (row.table_id, row.key_value): (
                row.status_id,
                row.content_revision,
                row.status_revision,
            )
            for row in session.scalars(select(DataRecordRow))
        }
        source = (
            before_run.status,
            before_run.status_revision,
            before_run.error,
            before_run.completed_at,
        )
    batch, _operation, _replayed = coordinator.follow_up(
        project_id, task.task_id, uid(), _payload(run.status_revision)
    )
    _claim(project_id, factory, batch.batch_id)
    with factory() as session:
        after_run = session.get(WorkflowRunRow, task.run_id)
        assert after_run is not None
        assert (
            after_run.status,
            after_run.status_revision,
            after_run.error,
            after_run.completed_at,
        ) == source
        after_task = session.get(ProjectTaskRow, task.task_id)
        assert after_task is not None
        assert after_task.batch_id == before_task.batch_id
        assert before_record == {
            (row.table_id, row.key_value): (
                row.status_id,
                row.content_revision,
                row.status_revision,
            )
            for row in session.scalars(select(DataRecordRow))
        }
    factory.dispose()
