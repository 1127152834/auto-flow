from dataclasses import replace

import pytest
from sqlalchemy import select

from autoflow.adapters.http.project_run_schemas import TaskDetail
from autoflow.application.project_data.capabilities import ProjectDataCapabilityService
from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.project_runs.queries import ProjectRunQueries
from autoflow.domain.project_data.capabilities import (
    CreateProjectRecordCommand,
    SetRecordStatusCommand,
)
from autoflow.domain.project_data.identity import RecordKey, encode_record_key
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_capabilities import (
    SqlAlchemyProjectDataCapabilities,
)
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_data_status_batches import (
    SqlAlchemyRecordStatusBatches,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectTaskRecordCursorRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.integration.test_project_run_data_start import _setup, uid


def test_fake_capability_changes_email_status_and_creates_account_once(tmp_path):
    targets: list[tuple[str, str]] = []
    factory, project_id, automation, coordinator = _setup(
        tmp_path,
        resolve_create_record_targets=lambda _session, _automation: targets,
        resolve_status_input_ids=lambda current: (
            current.input_plan["inputs"][1]["inputId"],
        ),
    )
    catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(factory))
    email_input = automation.input_plan["inputs"][1]
    status = catalog.create_status(
        project_id,
        email_input["tableId"],
        uid(),
        {"name": "已使用", "color": "#8f4b2b", "order": 1, "expectedTableRevision": 2},
    )[0]["status"]
    account = DataTableService(SqlAlchemyProjectData(factory)).create(project_id, uid(), {"name": "账号"})[0]
    account_field = catalog.create_field(
        project_id,
        account["tableId"],
        uid(),
        {"definition": {"key": "result", "name": "网页结果", "type": "string", "required": True, "validation": {}}, "expectedTableRevision": 1, "sourceColumnPolicy": "localOnly"},
    )[0]["field"]
    targets.append((account["tableId"], account["datasetGeneration"]))
    batch = coordinator.start(project_id, automation.automation_id, uid(), {"expectedAutomationRevision": automation.management_revision, "parameters": {}, "maxTasks": 1, "concurrency": 1})[0]
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    snapshot = coordinator.get_snapshot(project_id, task.task_id)
    email = snapshot.inputs[1]
    email_ref = email["recordRef"]
    with pytest.raises(ProjectError) as held:
        DataRecordService(SqlAlchemyProjectDataRecords(factory)).set_status(
            project_id,
            email_ref["tableId"],
            encode_record_key(
                RecordKey(
                    email_ref["recordKey"]["type"],
                    str(email_ref["recordKey"]["value"]),
                )
            ),
            uid(),
            {
                "datasetGeneration": email_ref["datasetGeneration"],
                "recordKeyType": email_ref["recordKey"]["type"],
                "statusId": status["statusId"],
                "expectedStatusRevision": email["statusRevision"],
            },
        )
    assert held.value.code == "RECORD_IN_USE"
    preview = SqlAlchemyRecordStatusBatches(factory).preview(
        project_id,
        email_ref["tableId"],
        {
            "statusId": status["statusId"],
            "targets": [
                {
                    "recordRef": email_ref,
                    "expectedStatusRevision": email["statusRevision"],
                }
            ],
            "blockSize": 100,
        },
    )
    assert preview["blocks"][0]["blockers"][0]["code"] == "RECORD_IN_USE"
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.execution_generation = 1
        run.status = "running"
        run.status_revision += 1

    service = ProjectDataCapabilityService(SqlAlchemyProjectDataCapabilities(factory))
    scope = service.scope(project_id, task.task_id, task.run_id)
    person_ref = snapshot.inputs[0]["recordRef"]
    with pytest.raises(ProjectError) as person_denied:
        service.set_record_status(
            scope,
            SetRecordStatusCommand(
                uid(),
                1,
                RecordRef(
                    project_id,
                    person_ref["tableId"],
                    person_ref["datasetGeneration"],
                    RecordKey(
                        person_ref["recordKey"]["type"],
                        person_ref["recordKey"]["value"],
                    ),
                ),
                None,
                snapshot.inputs[0]["statusRevision"],
            ),
        )
    assert person_denied.value.code == "CAPABILITY_SCOPE_DENIED"
    ref = email["recordRef"]
    status_command = SetRecordStatusCommand(
        uid(),
        1,
        RecordRef(project_id, ref["tableId"], ref["datasetGeneration"], RecordKey(ref["recordKey"]["type"], ref["recordKey"]["value"])),
        status["statusId"],
        email["statusRevision"],
    )
    changed, replayed = service.set_record_status(scope, status_command)
    unchanged, noop_replayed = service.set_record_status(
        scope,
        SetRecordStatusCommand(
            uid(),
            1,
            status_command.record_ref,
            status["statusId"],
            changed["statusRevision"],
        ),
    )
    create_command = CreateProjectRecordCommand(
        uid(), 1, project_id, account["tableId"], account["datasetGeneration"], {account_field["ref"]["fieldId"]: "ACCOUNT-001"}
    )
    created, first_replay = service.create_record(scope, create_command)
    replay, second_replay = service.create_record(scope, create_command)
    foreign_scope = replace(scope, task_id=uid())
    with pytest.raises(ProjectError) as foreign_replay:
        service.create_record(foreign_scope, create_command)
    assert foreign_replay.value.code == "CAPABILITY_SCOPE_DENIED"
    with pytest.raises(ProjectError) as foreign_query:
        service.query_operation(foreign_scope, create_command.operation_id)
    assert foreign_query.value.code == "CAPABILITY_SCOPE_DENIED"

    assert changed["statusId"] == status["statusId"] and replayed is False
    assert noop_replayed is False
    assert unchanged["statusRevision"] == changed["statusRevision"]
    assert created == replay and first_replay is False and second_replay is True
    assert created["ref"]["tableId"] == account["tableId"]
    detail = ProjectRunQueries(factory).task_detail(project_id, task.task_id)
    writes = detail["dataWrites"]
    assert [item["kind"] for item in writes] == ["statusChange", "recordCreated"]
    assert writes[0]["tableDisplay"] == "邮箱"
    assert writes[1]["tableDisplay"] == "账号"
    assert TaskDetail.model_validate(detail).input_snapshot.inputs[0]["values"]
    with factory() as session:
        cursor = session.scalar(select(ProjectTaskRecordCursorRow).where(ProjectTaskRecordCursorRow.task_id == task.task_id, ProjectTaskRecordCursorRow.record_ref["tableId"].as_string() == email_input["tableId"]))
        assert cursor is not None and cursor.status_revision == email["statusRevision"] + 1
    factory.dispose()


def test_old_execution_generation_is_rejected_before_any_write(tmp_path):
    factory, project_id, automation, coordinator = _setup(
        tmp_path,
        resolve_status_input_ids=lambda current: (
            current.input_plan["inputs"][1]["inputId"],
        ),
    )
    batch = coordinator.start(project_id, automation.automation_id, uid(), {"expectedAutomationRevision": 1, "parameters": {}, "maxTasks": 1, "concurrency": 1})[0]
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    snapshot = coordinator.get_snapshot(project_id, task.task_id)
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.execution_generation = 1
        run.status = "running"
    service = ProjectDataCapabilityService(SqlAlchemyProjectDataCapabilities(factory))
    scope = service.scope(project_id, task.task_id, task.run_id)
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.execution_generation = 2
    ref = snapshot.inputs[1]["recordRef"]
    command = SetRecordStatusCommand(uid(), 1, RecordRef(project_id, ref["tableId"], ref["datasetGeneration"], RecordKey(ref["recordKey"]["type"], ref["recordKey"]["value"])), None, snapshot.inputs[1]["statusRevision"])
    with pytest.raises(ProjectError) as caught:
        service.set_record_status(scope, command)
    assert caught.value.code == "LEASE_REVOKED"
    factory.dispose()
