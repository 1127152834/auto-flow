"""PM7-B overview aggregation: real counts, real day window, no filler numbers."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.projects.overview import ProjectOverviewService
from autoflow.application.projects.service import AVAILABILITY, ProjectService
from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.environment_models import ProjectManualItemRow
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_models import DataChangeRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.fixtures.workflows import workflow_payload


def uid() -> str:
    return str(uuid4())


def _setup(tmp_path):
    database = tmp_path / "overview.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    project = ProjectService(SqlAlchemyProjects(factory)).create(
        uid(), {"name": "概览项目", "description": ""}
    )[0]
    return factory, project.project_id


def _change(factory, project_id, *, sequence, before, after, created_at):
    operation_id = uid()
    with factory() as session:
        session.add(
            ProjectOperationRow(
                id=operation_id,
                project_id=project_id,
                idempotency_key=uid(),
                kind="workflowDataWrite",
                request_digest="0" * 64,
                status="succeeded",
                status_revision=2,
                resource={"type": "project", "projectId": project_id},
                result=None,
                error=None,
                created_at=created_at,
                updated_at=created_at,
                completed_at=created_at,
            )
        )
        session.flush()
        session.add(
            DataChangeRow(
                id=uid(),
                project_id=project_id,
                operation_id=operation_id,
                sequence=sequence,
                resource={
                    "type": "record",
                    "recordRef": {
                        "projectId": project_id,
                        "tableId": uid(),
                        "datasetGeneration": uid(),
                        "recordKey": {"type": "text", "value": str(sequence)},
                    },
                },
                origin="workflow",
                before=before,
                after=after,
                created_at=created_at,
            )
        )
        session.commit()


def test_an_empty_project_reports_real_zeroes_and_no_invented_numbers(tmp_path):
    factory, project_id = _setup(tmp_path)
    overview = ProjectOverviewService(factory).get(project_id)
    assert overview["counts"] == {
        "automations": 0,
        "tables": 0,
        "batches": 0,
        "environments": 0,
    }
    assert overview["activity"] == []
    assert overview["recent"] == []
    assert overview["dataChanges"]["newRecords"] == 0
    assert overview["dataChanges"]["updatedRecords"] == 0
    assert overview["dataChanges"]["timezone"] == "Asia/Shanghai"
    factory.dispose()


def test_counts_come_from_committed_rows(tmp_path):
    factory, project_id = _setup(tmp_path)
    workflows = WorkflowService(SqlAlchemyWorkflowRepository(factory))
    automations = ProjectAutomationService(
        SqlAlchemyProjects(factory), SqlAlchemyProjectAutomations(factory)
    )
    for index in range(2):
        workflow = workflows.create(workflow_payload(str(uuid4())), uid())
        automations.create(
            project_id,
            uid(),
            {
                "name": f"自动化{index}",
                "description": "",
                "workflowId": workflow.workflow_id,
                "inputPlan": {"inputs": []},
                "parameterSchema": [],
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
    tables = DataTableService(SqlAlchemyProjectData(factory))
    for index in range(3):
        tables.create(project_id, uid(), {"name": f"数据表{index}"})
    counts = ProjectOverviewService(factory).get(project_id)["counts"]
    assert counts["automations"] == 2
    assert counts["tables"] == 3
    factory.dispose()


def test_day_changes_split_creation_from_update_and_honour_the_window(tmp_path):
    factory, project_id = _setup(tmp_path)
    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    for index in range(3):
        _change(
            factory,
            project_id,
            sequence=index,
            before=None,
            after={"value": index},
            created_at=now - timedelta(hours=1),
        )
    for index in range(2):
        _change(
            factory,
            project_id,
            sequence=10 + index,
            before={"value": 1},
            after={"value": 2},
            created_at=now - timedelta(hours=2),
        )
    _change(
        factory,
        project_id,
        sequence=99,
        before=None,
        after={"value": "yesterday"},
        created_at=now - timedelta(days=2),
    )
    changes = ProjectOverviewService(factory).get(
        project_id, timezone="Asia/Shanghai", now=now
    )["dataChanges"]
    assert changes["newRecords"] == 3
    assert changes["updatedRecords"] == 2
    assert changes["dayStart"].startswith("2026-09-18T16:00:00")
    factory.dispose()


def test_attention_lists_failed_tasks_and_waiting_manual_items(tmp_path):
    factory, project_id = _setup(tmp_path)
    now = datetime.now(UTC)
    with factory() as session:
        session.add(
            ProjectManualItemRow(
                id=uid(),
                project_id=project_id,
                task_id=uid(),
                run_id=uid(),
                instance_id=None,
                checkpoint_revision=1,
                status="waiting",
                status_revision=1,
                expires_at=now + timedelta(hours=1),
                allowed_targets=[],
                resume_started=False,
                reason="等待人工确认验证码",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    activity = ProjectOverviewService(factory).get(project_id)["activity"]
    manual = [item for item in activity if item["kind"] == "manual"]
    assert [item["message"] for item in manual] == ["等待人工确认验证码"]
    assert manual[0]["severity"] == "warning"
    assert manual[0]["resource"]["type"] == "task"
    factory.dispose()


def test_an_expired_manual_item_is_not_attention(tmp_path):
    factory, project_id = _setup(tmp_path)
    now = datetime.now(UTC)
    with factory() as session:
        session.add(
            ProjectManualItemRow(
                id=uid(),
                project_id=project_id,
                task_id=uid(),
                run_id=uid(),
                instance_id=None,
                checkpoint_revision=1,
                status="waiting",
                status_revision=1,
                expires_at=now - timedelta(minutes=1),
                allowed_targets=[],
                resume_started=False,
                reason=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    assert ProjectOverviewService(factory).get(project_id)["activity"] == []
    factory.dispose()


def test_a_failed_task_is_attention_with_an_error_severity(tmp_path):
    from tests.integration.test_project_failure_followup import _claim, _fail_run
    from tests.integration.test_project_run_data_start import _setup as data_setup

    factory, project_id, automation, coordinator = data_setup(tmp_path)
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
    _fail_run(factory, task.run_id)
    activity = ProjectOverviewService(factory).get(project_id)["activity"]
    kinds = {item["kind"] for item in activity}
    assert kinds == {"batch", "task"}
    failed = next(item for item in activity if item["kind"] == "task")
    assert failed["severity"] == "error"
    assert failed["resource"] == {
        "type": "task",
        "projectId": project_id,
        "taskId": task.task_id,
    }
    assert "任务失败" in failed["message"]
    factory.dispose()


def test_a_missing_timezone_is_rejected_and_statistics_is_declared_available(tmp_path):
    factory, project_id = _setup(tmp_path)
    with pytest.raises(ProjectError) as failure:
        ProjectOverviewService(factory).get(project_id, timezone="Nope/Nowhere")
    assert failure.value.status == 422
    assert AVAILABILITY["statistics"] == "available"
    factory.dispose()
