from dataclasses import replace

import pytest
from sqlalchemy import select

from autoflow.adapters.http.project_run_schemas import TaskDetail
from autoflow.application.project_data.capabilities import ProjectDataCapabilityService
from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.project_runs.queries import ProjectRunQueries
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.domain.project_data.capabilities import (
    AddProjectFieldCommand,
    CreateProjectRecordCommand,
    DeleteProjectRecordCommand,
    EnsureProjectFieldCommand,
    ModifyProjectFieldCommand,
    PreviewProjectFieldChangeRequest,
    QueryProjectRecordsRequest,
    SetRecordStatusCommand,
    UpdateProjectRecordCommand,
)
from autoflow.domain.project_data.identity import RecordKey, encode_record_key
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow
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
    ProjectRecordLeaseRow,
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
    account = DataTableService(SqlAlchemyProjectData(factory)).create(
        project_id, uid(), {"name": "账号"}
    )[0]
    account_field = catalog.create_field(
        project_id,
        account["tableId"],
        uid(),
        {
            "definition": {
                "key": "result",
                "name": "网页结果",
                "type": "string",
                "required": True,
                "validation": {},
            },
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]
    targets.append((account["tableId"], account["datasetGeneration"]))
    batch = coordinator.start(
        project_id,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )[0]
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project_id, batch.batch_id)
        == "ready"
    )
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
        RecordRef(
            project_id,
            ref["tableId"],
            ref["datasetGeneration"],
            RecordKey(ref["recordKey"]["type"], ref["recordKey"]["value"]),
        ),
        status["statusId"],
        email["statusRevision"],
        email["contentRevision"],
        (None,),
    )
    changed, replayed = service.set_record_status(scope, status_command)
    replayed_status, status_replay = service.set_record_status(scope, status_command)
    with pytest.raises(ProjectError) as stale_business_conclusion:
        service.set_record_status(
            scope,
            SetRecordStatusCommand(
                uid(),
                1,
                status_command.record_ref,
                None,
                changed["statusRevision"],
                changed["contentRevision"],
                (None,),
            ),
        )
    assert stale_business_conclusion.value.code == "STATUS_PRECONDITION_FAILED"
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
        uid(),
        1,
        project_id,
        account["tableId"],
        account["datasetGeneration"],
        {account_field["ref"]["fieldId"]: "ACCOUNT-001"},
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
    assert status_replay is True and replayed_status == changed
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
        cursor = session.scalar(
            select(ProjectTaskRecordCursorRow).where(
                ProjectTaskRecordCursorRow.task_id == task.task_id,
                ProjectTaskRecordCursorRow.record_ref["tableId"].as_string()
                == email_input["tableId"],
            )
        )
        assert (
            cursor is not None and cursor.status_revision == email["statusRevision"] + 1
        )
    factory.dispose()


def test_old_execution_generation_is_rejected_before_any_write(tmp_path):
    factory, project_id, automation, coordinator = _setup(
        tmp_path,
        resolve_status_input_ids=lambda current: (
            current.input_plan["inputs"][1]["inputId"],
        ),
    )
    batch = coordinator.start(
        project_id,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": 1,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )[0]
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project_id, batch.batch_id)
        == "ready"
    )
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
    command = SetRecordStatusCommand(
        uid(),
        1,
        RecordRef(
            project_id,
            ref["tableId"],
            ref["datasetGeneration"],
            RecordKey(ref["recordKey"]["type"], ref["recordKey"]["value"]),
        ),
        None,
        snapshot.inputs[1]["statusRevision"],
    )
    with pytest.raises(ProjectError) as caught:
        service.set_record_status(scope, command)
    assert caught.value.code == "LEASE_REVOKED"
    factory.dispose()


def test_query_then_dynamic_write_advances_task_cursor_and_stale_write_conflicts(
    tmp_path,
    monkeypatch,
):
    targets: list[tuple[str, str]] = []
    manifests: list[dict] = []
    factory, project_id, automation, coordinator = _setup(
        tmp_path,
        resolve_create_record_targets=lambda _session, _automation: targets,
        resolve_data_capability_manifest=lambda _session, _automation: (
            manifests[0] if manifests else {}
        ),
    )
    catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(factory))
    account = DataTableService(SqlAlchemyProjectData(factory)).create(
        project_id, uid(), {"name": "账号"}
    )[0]
    field = catalog.create_field(
        project_id,
        account["tableId"],
        uid(),
        {
            "definition": {
                "key": "result",
                "name": "网页结果",
                "type": "string",
                "required": True,
                "validation": {},
            },
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]
    records = DataRecordService(SqlAlchemyProjectDataRecords(factory))
    first = records.create(
        project_id,
        account["tableId"],
        uid(),
        {
            "datasetGeneration": account["datasetGeneration"],
            "values": [{"fieldId": field["ref"]["fieldId"], "value": "A-001"}],
        },
    )[0]
    second = records.create(
        project_id,
        account["tableId"],
        uid(),
        {
            "datasetGeneration": account["datasetGeneration"],
            "values": [{"fieldId": field["ref"]["fieldId"], "value": "A-002"}],
        },
    )[0]
    manifests.append(
        {
            "tableGrants": [
                {
                    "tableId": account["tableId"],
                    "datasetGeneration": account["datasetGeneration"],
                    "operations": [
                        "readRecord",
                        "queryRecords",
                        "updateRecord",
                        "deleteRecord",
                        "setRecordStatus",
                        "addField",
                        "ensureField",
                        "modifyField",
                    ],
                    "fieldIds": [field["ref"]["fieldId"]],
                    "readPurposes": ["workflow"],
                }
            ],
        }
    )
    targets.append((account["tableId"], account["datasetGeneration"]))
    batch = coordinator.start(
        project_id,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )[0]
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project_id, batch.batch_id)
        == "ready"
    )
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        assert run is not None
        run.execution_generation = 1
        run.status = "running"
        run.status_revision += 1
    service = ProjectDataCapabilityService(SqlAlchemyProjectDataCapabilities(factory))
    scope = service.scope(project_id, task.task_id, task.run_id)
    page = service.query_records(
        scope,
        QueryProjectRecordsRequest(
            1,
            project_id,
            account["tableId"],
            account["datasetGeneration"],
            [field["ref"]["fieldId"]],
            "workflow",
            None,
            [],
            None,
            1,
        ),
    )
    assert page["hasMore"] is True and page["nextCursor"]
    selected = page["items"][0]
    selected_ref = selected["ref"]
    ref = RecordRef(
        project_id,
        selected_ref["tableId"],
        selected_ref["datasetGeneration"],
        RecordKey(
            selected_ref["recordKey"]["type"], selected_ref["recordKey"]["value"]
        ),
    )
    update_command = UpdateProjectRecordCommand(
        uid(),
        1,
        ref,
        {field["ref"]["fieldId"]: "A-001-task"},
        selected["contentRevision"],
    )
    repository = service.repository
    original_commit = repository._commit

    def fail_commit(_session):
        raise RuntimeError("injected transaction failure")

    monkeypatch.setattr(repository, "_commit", fail_commit)
    with pytest.raises(RuntimeError, match="injected transaction failure"):
        service.update_record(scope, update_command)
    monkeypatch.setattr(repository, "_commit", original_commit)
    with factory() as session:
        persisted = SqlAlchemyProjectDataRecords(factory)._required_record(
            session,
            project_id,
            ref.table_id,
            ref.dataset_generation,
            ref.record_key,
        )
        assert persisted.content_revision == selected["contentRevision"]
        assert (
            session.scalar(
                select(ProjectRecordLeaseRow).where(
                    ProjectRecordLeaseRow.task_id == task.task_id,
                    ProjectRecordLeaseRow.record_ref["tableId"].as_string()
                    == ref.table_id,
                    ProjectRecordLeaseRow.record_ref["recordKey"]["value"].as_string()
                    == ref.record_key.value,
                )
            )
            is None
        )
        assert (
            session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == update_command.operation_id
                )
            )
            is None
        )
    changed, replayed = service.update_record(scope, update_command)
    assert replayed is False and changed["contentRevision"] == 2
    replayed_update, update_replay = service.update_record(scope, update_command)
    assert update_replay is True and replayed_update == changed
    assert service.query_operation(scope, update_command.operation_id) == changed
    manual = records.update(
        project_id,
        account["tableId"],
        encode_record_key(ref.record_key),
        uid(),
        {
            "datasetGeneration": account["datasetGeneration"],
            "recordKeyType": ref.record_key.type,
            "values": [{"fieldId": field["ref"]["fieldId"], "value": "A-001-human"}],
            "expectedContentRevision": 2,
        },
    )[0]
    assert manual["contentRevision"] == 3
    with pytest.raises(ProjectError) as stale:
        service.update_record(
            scope,
            UpdateProjectRecordCommand(
                uid(),
                1,
                ref,
                {field["ref"]["fieldId"]: "must-not-win"},
                2,
            ),
        )
    assert stale.value.code == "REVISION_CONFLICT"

    unqueried_record = (
        second if second["ref"]["recordKey"] != selected_ref["recordKey"] else first
    )
    unqueried_ref = unqueried_record["ref"]
    with pytest.raises(ProjectError) as unqueried:
        service.update_record(
            scope,
            UpdateProjectRecordCommand(
                uid(),
                1,
                RecordRef(
                    project_id,
                    unqueried_ref["tableId"],
                    unqueried_ref["datasetGeneration"],
                    RecordKey(
                        unqueried_ref["recordKey"]["type"],
                        unqueried_ref["recordKey"]["value"],
                    ),
                ),
                {field["ref"]["fieldId"]: "forbidden"},
                unqueried_record["contentRevision"],
            ),
        )
    assert unqueried.value.code == "CAPABILITY_SCOPE_DENIED"

    create = CreateProjectRecordCommand(
        uid(),
        1,
        project_id,
        account["tableId"],
        account["datasetGeneration"],
        {field["ref"]["fieldId"]: "A-003"},
    )
    created = service.create_record(scope, create)[0]
    created_ref = created["ref"]
    owned_ref = RecordRef(
        project_id,
        created_ref["tableId"],
        created_ref["datasetGeneration"],
        RecordKey(created_ref["recordKey"]["type"], created_ref["recordKey"]["value"]),
    )
    owned = service.update_record(
        scope,
        UpdateProjectRecordCommand(
            uid(), 1, owned_ref, {field["ref"]["fieldId"]: "A-003-updated"}, 1
        ),
    )[0]
    delete_command = DeleteProjectRecordCommand(
        uid(),
        1,
        owned_ref,
        owned["contentRevision"],
        owned["statusRevision"],
        owned["linkRevision"],
    )
    deleted = service.delete_record(
        scope,
        delete_command,
    )[0]
    assert deleted["deleted"] is True
    replayed_delete, delete_replay = service.delete_record(scope, delete_command)
    assert delete_replay is True and replayed_delete == deleted

    added_definition = {
        "key": "note",
        "name": "备注",
        "type": "string",
        "required": False,
        "validation": {},
    }
    added_id = uid()
    add_command = AddProjectFieldCommand(
        uid(),
        1,
        project_id,
        account["tableId"],
        account["datasetGeneration"],
        added_id,
        added_definition,
        False,
        None,
        2,
    )
    added, added_replay = service.add_field(scope, add_command)
    replayed_added, replayed_add = service.add_field(scope, add_command)
    assert added_replay is False and added["field"]["ref"]["fieldId"] == added_id
    assert replayed_add is True and replayed_added == added
    ensure_command = EnsureProjectFieldCommand(
        uid(),
        1,
        project_id,
        account["tableId"],
        account["datasetGeneration"],
        uid(),
        added_definition,
        False,
        None,
        added["tableRevision"],
    )
    ensured, _ = service.ensure_field(
        scope,
        ensure_command,
    )
    assert (
        ensured["created"] is False and ensured["field"]["ref"]["fieldId"] == added_id
    )
    replayed_ensure, ensure_replay = service.ensure_field(scope, ensure_command)
    assert ensure_replay is True and replayed_ensure == ensured
    modified_definition = {**added_definition, "name": "任务备注"}
    impact = service.preview_field_change(
        scope,
        PreviewProjectFieldChangeRequest(
            1,
            project_id,
            account["tableId"],
            account["datasetGeneration"],
            added_id,
            modified_definition,
        ),
    )
    modify_command = ModifyProjectFieldCommand(
        uid(),
        1,
        project_id,
        account["tableId"],
        account["datasetGeneration"],
        added_id,
        modified_definition,
        ensured["tableRevision"],
        ensured["field"]["fieldRevision"],
        impact["impactRevision"],
    )
    modified, _ = service.modify_field(
        scope,
        modify_command,
    )
    assert modified["field"]["name"] == "任务备注"
    replayed_modify, modify_replay = service.modify_field(scope, modify_command)
    assert modify_replay is True and replayed_modify == modified
    factory.dispose()
