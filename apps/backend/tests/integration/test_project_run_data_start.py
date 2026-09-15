from uuid import uuid4

import pytest
from sqlalchemy import func, select

from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.project_runs.coordinator import ProjectRunCoordinator
from autoflow.application.projects.service import ProjectService
from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.project_claims import SqlAlchemyProjectInputGroups
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectRecordLeaseRow,
    ProjectTaskRecordCursorRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.fixtures.workflows import workflow_payload


def uid() -> str:
    return str(uuid4())


def _table(factory, project_id: str, name: str, value: str):
    table = DataTableService(SqlAlchemyProjectData(factory)).create(project_id, uid(), {"name": name})[0]
    field = DataCatalogService(SqlAlchemyProjectDataCatalog(factory)).create_field(
        project_id,
        table["tableId"],
        uid(),
        {"definition": {"key": "value", "name": "值", "type": "string", "required": True, "validation": {}}, "expectedTableRevision": 1, "sourceColumnPolicy": "localOnly"},
    )[0]["field"]
    DataRecordService(SqlAlchemyProjectDataRecords(factory)).create(
        project_id,
        table["tableId"],
        uid(),
        {"datasetGeneration": table["datasetGeneration"], "values": [{"fieldId": field["ref"]["fieldId"], "value": value}]},
    )
    return table, field


def _input(project_id: str, table: dict, field: dict, alias: str):
    return {
        "inputId": uid(), "alias": alias, "tableId": table["tableId"],
        "datasetGeneration": table["datasetGeneration"], "mode": "independent", "required": True,
        "fieldBindings": [{"inputFieldId": uid(), "inputFieldAlias": "值", "fieldRef": {"projectId": project_id, "tableId": table["tableId"], "datasetGeneration": table["datasetGeneration"], "fieldId": field["ref"]["fieldId"]}}],
        "filter": {"type": "all", "items": []}, "orderBy": [{"systemField": "recordKey", "direction": "asc"}],
    }


def _setup(
    tmp_path,
    resolve_create_record_targets=None,
    resolve_status_input_ids=None,
):
    path = tmp_path / "data-run.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = ProjectService(SqlAlchemyProjects(factory)).create(uid(), {"name": "三表链"})[0].project_id
    people, people_field = _table(factory, project_id, "人员", "张三")
    emails, email_field = _table(factory, project_id, "邮箱", "pm4@example.test")
    workflow_repository = SqlAlchemyWorkflowRepository(factory)
    workflow = WorkflowService(workflow_repository).create(workflow_payload(), uid())
    automation = ProjectAutomationService(SqlAlchemyProjects(factory), SqlAlchemyProjectAutomations(factory)).create(
        project_id,
        uid(),
        {
            "name": "首条三表链", "description": "", "workflowId": workflow.workflow_id,
            "inputPlan": {"inputs": [_input(project_id, people, people_field, "人员"), _input(project_id, emails, email_field, "邮箱")]},
            "parameterSchema": [], "environmentPolicy": {"source": "newFromProfile"},
            "runPolicy": {"maxTasks": 1, "concurrency": 1, "maxLiveInstances": 1, "continueAfterFailure": False, "automaticExecutionTimeoutSeconds": 60, "manualDeadlineSeconds": 300},
        },
    )[0]
    runtime = WorkflowRuntimeService(factory, workflow_repository)
    coordinator = ProjectRunCoordinator(
        factory, runtime, resolve_resources=lambda *_: {"browser": "none", "modelProviderId": None},
        available_capabilities=["browser.cloakbrowser", "project.data"],
        resolve_create_record_targets=resolve_create_record_targets,
        resolve_status_input_ids=resolve_status_input_ids,
    )
    return factory, project_id, automation, coordinator


def test_start_atomically_creates_one_task_with_two_inputs_and_typed_leases(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    batch, _operation, replayed = coordinator.start(project_id, automation.automation_id, uid(), {"expectedAutomationRevision": automation.management_revision, "parameters": {}, "maxTasks": 1, "concurrency": 1})
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    with factory() as session:
        snapshot = SqlAlchemyProjectInputGroups(session)
        del snapshot
        stored = coordinator.get_snapshot(project_id, task.task_id)
        leases = list(session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.task_id == task.task_id)))
        cursors = list(session.scalars(select(ProjectTaskRecordCursorRow).where(ProjectTaskRecordCursorRow.task_id == task.task_id)))
    assert not replayed
    assert [item["alias"] for item in stored.inputs] == ["人员", "邮箱"]
    assert len(leases) == len(cursors) == 2
    assert {lease.record_ref["recordKey"]["type"] for lease in leases} == {"uuid"}
    factory.dispose()


def test_busy_second_required_group_rolls_back_task_snapshot_run_and_lease(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    payload = {"expectedAutomationRevision": automation.management_revision, "parameters": {}, "maxTasks": 1, "concurrency": 1}
    coordinator.start(project_id, automation.automation_id, uid(), payload)
    with pytest.raises(ProjectRunError) as caught:
        coordinator.start(project_id, automation.automation_id, uid(), payload)
    assert caught.value.code == "INPUT_TEMPORARILY_BUSY"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ProjectTaskRow)) == 1
        assert session.scalar(select(func.count()).select_from(WorkflowRunRow)) == 1
        assert session.scalar(select(func.count()).select_from(ProjectRecordLeaseRow)) == 2
    factory.dispose()
