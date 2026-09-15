from concurrent.futures import ThreadPoolExecutor
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
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.project_claims import SqlAlchemyProjectInputGroups
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectRecordLeaseRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRecordCursorRow,
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


def test_concurrent_distinct_starts_claim_one_group_once(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    payload = {
        "expectedAutomationRevision": automation.management_revision,
        "parameters": {},
        "maxTasks": 1,
        "concurrency": 1,
    }

    def start_once(_index: int):
        try:
            return coordinator.start(project_id, automation.automation_id, uid(), payload)[0]
        except ProjectRunError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(start_once, range(2)))

    assert sum(not isinstance(item, ProjectRunError) for item in results) == 1
    errors = [item for item in results if isinstance(item, ProjectRunError)]
    assert [error.code for error in errors] == ["INPUT_TEMPORARILY_BUSY"]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ProjectBatchRow)) == 1
        assert session.scalar(select(func.count()).select_from(ProjectTaskRow)) == 1
        assert session.scalar(select(func.count()).select_from(WorkflowRunRow)) == 1
        assert session.scalar(select(func.count()).select_from(ProjectRecordLeaseRow)) == 2
    factory.dispose()


def test_hold_failure_rolls_back_the_entire_input_group_and_run(tmp_path, monkeypatch):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    original = SqlAlchemyProjectInputGroups.hold

    def fail_after_hold(self, selection, **kwargs):
        original(self, selection, **kwargs)
        raise RuntimeError("injected hold failure")

    monkeypatch.setattr(SqlAlchemyProjectInputGroups, "hold", fail_after_hold)
    with pytest.raises(RuntimeError, match="injected hold failure"):
        coordinator.start(
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

    with factory() as session:
        for model in (
            ProjectBatchRow,
            ProjectTaskRow,
            ProjectTaskInputSnapshotRow,
            ProjectRecordLeaseRow,
            ProjectTaskRecordCursorRow,
            WorkflowPreparedContentRow,
            WorkflowRunRow,
        ):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.scalar(
            select(func.count())
            .select_from(ProjectOperationRow)
            .where(ProjectOperationRow.kind == "startBatch")
        ) == 0
    factory.dispose()


def test_optional_no_match_keeps_batch_runnable_and_freezes_unavailable_reason(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    optional = {
        **automation.input_plan["inputs"][0],
        "inputId": uid(),
        "alias": "可选人员",
        "required": False,
        "filter": {
            "type": "compare",
            "fieldId": automation.input_plan["inputs"][0]["fieldBindings"][0][
                "fieldRef"
            ]["fieldId"],
            "operator": "eq",
            "value": "不存在",
        },
    }
    with factory() as session:
        row = session.get(ProjectAutomationRow, automation.automation_id)
        assert row is not None
        row.input_plan = {
            "inputs": [*automation.input_plan["inputs"], optional]
        }
        session.commit()

    preview = coordinator.preview_inputs(
        project_id, automation.automation_id, automation.management_revision
    )
    assert preview["runnable"] is True
    assert preview["selectionStatus"] == "ready"
    assert preview["evaluatedCandidateBindings"] >= 2
    assert preview["inputs"][2] == {
        "inputId": optional["inputId"],
        "alias": "可选人员",
        "tableDisplay": "人员",
        "recordDisplay": None,
        "values": [],
        "outcome": "noMatch",
        "required": False,
        "detail": "可选输入没有符合条件的记录，本次任务将保留为空",
        "scannedCount": None,
    }

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
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    snapshot = coordinator.get_snapshot(project_id, task.task_id)
    assert snapshot.inputs[2]["recordRef"] is None
    assert snapshot.inputs[2]["unavailableReason"] == "no_match"
    with factory() as session:
        leases = list(
            session.scalars(
                select(ProjectRecordLeaseRow).where(
                    ProjectRecordLeaseRow.task_id == task.task_id
                )
            )
        )
    assert len(leases) == 2
    factory.dispose()


def test_invalid_optional_input_blocks_preview_and_start_without_durable_facts(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    optional = {
        **automation.input_plan["inputs"][0],
        "inputId": uid(),
        "alias": "可选人员",
        "required": False,
        "datasetGeneration": uid(),
    }
    with factory() as session:
        row = session.get(ProjectAutomationRow, automation.automation_id)
        assert row is not None
        row.input_plan = {"inputs": [*automation.input_plan["inputs"], optional]}
        session.commit()

    preview = coordinator.preview_inputs(
        project_id, automation.automation_id, automation.management_revision
    )
    assert preview["runnable"] is False
    assert preview["selectionStatus"] == "configurationError"
    assert [item["outcome"] for item in preview["inputs"]] == [
        "notEvaluated",
        "notEvaluated",
        "configurationError",
    ]
    assert preview["inputs"][2]["detail"] == "数据表已更新，请重新选择数据表"
    with pytest.raises(ProjectRunError) as error:
        coordinator.start(
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
    assert error.value.code == "INPUT_CONFIGURATION_ERROR"
    with factory() as session:
        for model in (
            ProjectBatchRow,
            ProjectTaskRow,
            ProjectTaskInputSnapshotRow,
            ProjectRecordLeaseRow,
            ProjectTaskRecordCursorRow,
            WorkflowPreparedContentRow,
            WorkflowRunRow,
        ):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.scalar(
            select(func.count())
            .select_from(ProjectOperationRow)
            .where(ProjectOperationRow.kind == "startBatch")
        ) == 0
    factory.dispose()


def test_preview_marks_an_optional_source_as_effectively_required(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    source = {
        **automation.input_plan["inputs"][0],
        "required": False,
        "filter": {
            "type": "compare",
            "fieldId": automation.input_plan["inputs"][0]["fieldBindings"][0][
                "fieldRef"
            ]["fieldId"],
            "operator": "eq",
            "value": "不存在",
        },
    }
    target = {
        **automation.input_plan["inputs"][0],
        "inputId": uid(),
        "alias": "必要别名",
        "mode": "related",
        "relation": {"type": "sameRecord", "sourceInputId": source["inputId"]},
    }
    with factory() as session:
        row = session.get(ProjectAutomationRow, automation.automation_id)
        assert row is not None
        row.input_plan = {"inputs": [source, target]}
        session.commit()

    preview = coordinator.preview_inputs(
        project_id, automation.automation_id, automation.management_revision
    )

    assert preview["runnable"] is False
    assert preview["selectionStatus"] == "noMatch"
    assert preview["inputs"][0]["required"] is True
    assert preview["inputs"][0]["outcome"] == "noMatch"
    assert preview["inputs"][0]["detail"] == "因后续必要输入依赖，本次必须提供"
    assert preview["inputs"][1]["outcome"] == "notEvaluated"
    factory.dispose()


def test_start_reselects_current_rows_instead_of_reusing_preview_facts(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    before = coordinator.preview_inputs(
        project_id, automation.automation_id, automation.management_revision
    )
    assert before["inputs"][0]["values"][0]["value"] == "张三"
    people_input = automation.input_plan["inputs"][0]
    people_field_id = people_input["fieldBindings"][0]["fieldRef"]["fieldId"]
    with factory() as session:
        row = session.scalar(
            select(DataRecordRow).where(
                DataRecordRow.table_id == people_input["tableId"]
            )
        )
        assert row is not None
        row.values_json = {people_field_id: "李四"}
        row.content_revision += 1
        session.commit()

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
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    snapshot = coordinator.get_snapshot(project_id, task.task_id)

    assert snapshot.inputs[0]["values"][0]["value"] == "李四"
    assert snapshot.inputs[0]["contentRevision"] == 2
    factory.dispose()


def test_ambiguous_relation_blocks_preview_and_start_without_durable_run_facts(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    people_input, email_input = automation.input_plan["inputs"]
    people_field_id = people_input["fieldBindings"][0]["fieldRef"]["fieldId"]
    email_field_id = email_input["fieldBindings"][0]["fieldRef"]["fieldId"]
    with factory() as session:
        people_row = session.scalar(
            select(DataRecordRow).where(DataRecordRow.table_id == people_input["tableId"])
        )
        email_row = session.scalar(
            select(DataRecordRow).where(DataRecordRow.table_id == email_input["tableId"])
        )
        automation_row = session.get(ProjectAutomationRow, automation.automation_id)
        assert people_row is not None and email_row is not None and automation_row is not None
        people_row.values_json = {people_field_id: "shared"}
        email_row.values_json = {email_field_id: "shared"}
        related = {
            **email_input,
            "mode": "related",
            "relation": {
                "type": "fieldEquals",
                "sourceInputId": people_input["inputId"],
                "sourceFieldRef": people_input["fieldBindings"][0]["fieldRef"],
                "targetFieldRef": email_input["fieldBindings"][0]["fieldRef"],
            },
        }
        automation_row.input_plan = {"inputs": [people_input, related]}
        session.commit()
    DataRecordService(SqlAlchemyProjectDataRecords(factory)).create(
        project_id,
        email_input["tableId"],
        uid(),
        {
            "datasetGeneration": email_input["datasetGeneration"],
            "values": [{"fieldId": email_field_id, "value": "shared"}],
        },
    )

    preview = coordinator.preview_inputs(
        project_id, automation.automation_id, automation.management_revision
    )
    assert preview["runnable"] is False
    assert preview["selectionStatus"] == "ambiguous"
    assert preview["inputs"][0]["outcome"] == "notEvaluated"
    assert preview["inputs"][1]["outcome"] == "ambiguous"
    assert "shared" in preview["inputs"][1]["detail"]
    assert "同时匹配记录" in preview["inputs"][1]["detail"]
    with pytest.raises(ProjectRunError) as error:
        coordinator.start(
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
    assert error.value.code == "INPUT_AMBIGUOUS"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ProjectTaskRow)) == 0
        assert session.scalar(select(func.count()).select_from(WorkflowRunRow)) == 0
        assert session.scalar(select(func.count()).select_from(ProjectRecordLeaseRow)) == 0
    factory.dispose()
