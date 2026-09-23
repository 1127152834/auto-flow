from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from autoflow.application.project_data.capabilities import ProjectDataCapabilityService
from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.domain.project_data.capabilities import (
    AddProjectFieldCommand,
    ModifyProjectFieldCommand,
    QueryProjectRecordsRequest,
    ReadProjectRecordRequest,
    RecordReadGrant,
    TableCapabilityGrant,
    TaskCapabilityScope,
    UpdateProjectRecordCommand,
)
from autoflow.domain.project_data.identity import RecordKey
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
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataGenerationRow,
    DataRecordRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectRecordLeaseRow,
    ProjectTaskRecordReadRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.integration.test_project_run_data_start import _setup, uid


@pytest.fixture
def capability_context(tmp_path):
    targets: list[tuple[str, str]] = []
    factory, project_id, automation, coordinator = _setup(
        tmp_path,
        resolve_create_record_targets=lambda _session, _automation: targets,
    )
    table = DataTableService(SqlAlchemyProjectData(factory)).create(
        project_id, uid(), {"name": "能力边界"}
    )[0]
    field = DataCatalogService(SqlAlchemyProjectDataCatalog(factory)).create_field(
        project_id,
        table["tableId"],
        uid(),
        {
            "definition": {
                "key": "value",
                "name": "值",
                "type": "string",
                "required": True,
                "validation": {},
            },
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]
    record = DataRecordService(SqlAlchemyProjectDataRecords(factory)).create(
        project_id,
        table["tableId"],
        uid(),
        {
            "datasetGeneration": table["datasetGeneration"],
            "values": [{"fieldId": field["ref"]["fieldId"], "value": "original"}],
        },
    )[0]
    targets.append((table["tableId"], table["datasetGeneration"]))
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
    try:
        yield factory, project_id, task, table, field, record
    finally:
        factory.dispose()


def _service(factory):
    return ProjectDataCapabilityService(SqlAlchemyProjectDataCapabilities(factory))


def _record_ref(project_id: str, record: dict) -> RecordRef:
    ref = record["ref"]
    key = ref["recordKey"]
    return RecordRef(
        project_id,
        ref["tableId"],
        ref["datasetGeneration"],
        RecordKey(key["type"], key["value"]),
    )


def _scope(
    project_id: str, task, table: dict, field: dict, ref: RecordRef, generation: int
):
    return TaskCapabilityScope(
        project_id,
        task.task_id,
        task.run_id,
        generation,
        frozenset(),
        frozenset(),
        frozenset(
            {
                RecordReadGrant(
                    ref,
                    frozenset({field["ref"]["fieldId"]}),
                    frozenset({"workflow"}),
                )
            }
        ),
        frozenset(),
        frozenset(
            {
                TableCapabilityGrant(
                    table["tableId"],
                    table["datasetGeneration"],
                    frozenset(
                        {
                            "queryRecords",
                            "updateRecord",
                            "deleteRecord",
                            "setRecordStatus",
                            "createRecord",
                            "addField",
                            "ensureField",
                            "modifyField",
                        }
                    ),
                    frozenset({field["ref"]["fieldId"]}),
                    frozenset({"workflow"}),
                )
            }
        ),
    )


def _advance_execution_generation(factory, task, generation: int) -> None:
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        assert run is not None
        binding = dict(run.capability_bindings[0])
        binding["executionGeneration"] = generation
        run.capability_bindings = [binding]
        run.execution_generation = generation
        run.status_revision += 1


def test_opposing_dynamic_writes_return_conflicts_without_stealing_leases(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from autoflow.infrastructure.database.project_run_models import (
        ProjectTaskInputSnapshotRow,
        ProjectTaskRecordCursorRow,
    )
    from tests.integration.test_project_capability_field_impacts import _activate_task
    from tests.integration.test_project_run_data_start import _table

    factory, project, automation, _ = _setup(tmp_path)
    try:
        table, field = _table(factory, project, "动态写入", "first")
        field_id = field["ref"]["fieldId"]
        DataRecordService(SqlAlchemyProjectDataRecords(factory)).create(
            project, table["tableId"], uid(), {
                "datasetGeneration": table["datasetGeneration"],
                "values": [{"fieldId": field_id, "value": "second"}],
            },
        )
        grants = [{
            "tableId": table["tableId"], "datasetGeneration": table["datasetGeneration"],
            "operations": ["queryRecords", "updateRecord"],
            "fieldIds": [field_id], "readPurposes": ["workflow"],
        }]
        tasks = [_activate_task(factory, project, automation, grants) for _ in range(2)]
        with factory.begin() as session:
            for task in tasks:
                run = session.get(WorkflowRunRow, task.run_id)
                run.status, run.execution_generation = "running", 1
                run.status_revision += 1
        service = _service(factory)
        scopes = [service.scope(project, task.id, task.run_id) for task in tasks]
        query = QueryProjectRecordsRequest(
            1, project, table["tableId"], table["datasetGeneration"],
            [field_id], "workflow", None, [], None, 10,
        )
        records = service.query_records(scopes[0], query)["items"]
        assert len(records) == 2
        assert service.query_records(scopes[1], query)["items"] == records
        refs = [_record_ref(project, record) for record in records]
        for index, scope in enumerate(scopes):
            service.update_record(scope, UpdateProjectRecordCommand(
                uid(), 1, refs[index], {field_id: f"owned-{index}"},
                records[index]["contentRevision"],
            ))

        def facts():
            with factory() as session:
                return (
                    [(r.key_value, r.values_json, r.content_revision, r.status_revision, r.link_revision)
                     for r in session.scalars(select(DataRecordRow).order_by(DataRecordRow.key_value))],
                    [(r.id, r.task_id, r.record_ref, r.state, r.lease_generation)
                     for r in session.scalars(select(ProjectRecordLeaseRow).order_by(ProjectRecordLeaseRow.id))],
                    [(r.id, r.content_revision, r.status_revision, r.link_revision)
                     for r in session.scalars(select(ProjectTaskRecordCursorRow).order_by(ProjectTaskRecordCursorRow.id))],
                    [(r.task_id, r.inputs) for r in session.scalars(select(ProjectTaskInputSnapshotRow).order_by(ProjectTaskInputSnapshotRow.id))],
                )

        before = facts()
        assert {(lease[1], lease[3]) for lease in before[1]} == {(task.id, "held") for task in tasks}
        assert len(before[1]) == 2
        barrier = Barrier(2, timeout=5)
        operation_ids = [uid(), uid()]

        def cross_write(index):
            other = 1 - index
            barrier.wait()
            with pytest.raises(ProjectError) as denied:
                service.update_record(scopes[index], UpdateProjectRecordCommand(
                    operation_ids[index], 1, refs[other], {field_id: "must-not-write"},
                    records[other]["contentRevision"],
                ))
            return denied.value.code, denied.value.status, denied.value.details

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(cross_write, index) for index in range(2)]
            assert [future.result(timeout=5) for future in futures] == [
                ("LEASE_BUSY", 409, {"retryable": True}),
                ("LEASE_BUSY", 409, {"retryable": True}),
            ]
        assert facts() == before
        with factory() as session:
            assert all(session.get(ProjectOperationRow, op) is None for op in operation_ids)
    finally:
        factory.dispose()


def test_old_execution_generation_read_evidence_cannot_authorize_dynamic_write(
    capability_context,
):
    factory, project_id, task, table, field, record = capability_context
    first = _service(factory)
    ref = _record_ref(project_id, record)
    first_scope = _scope(project_id, task, table, field, ref, 1)
    first.read_record(
        first_scope,
        ReadProjectRecordRequest(1, ref, [field["ref"]["fieldId"]], "workflow"),
    )
    _advance_execution_generation(factory, task, 2)

    second = _service(factory)
    second_scope = _scope(project_id, task, table, field, ref, 2)
    operation_id = uid()
    with pytest.raises(ProjectError) as denied:
        second.update_record(
            second_scope,
            UpdateProjectRecordCommand(
                operation_id,
                2,
                ref,
                {field["ref"]["fieldId"]: "must-not-write"},
                record["contentRevision"],
            ),
        )

    assert denied.value.code == "CAPABILITY_SCOPE_DENIED"
    with factory() as session:
        persisted = SqlAlchemyProjectDataRecords(factory)._required_record(
            session,
            project_id,
            ref.table_id,
            ref.dataset_generation,
            ref.record_key,
        )
        assert persisted.values_json[field["ref"]["fieldId"]] == "original"
        assert session.get(ProjectOperationRow, operation_id) is None
        assert (
            session.scalar(
                select(func.count())
                .select_from(ProjectRecordLeaseRow)
                .where(ProjectRecordLeaseRow.task_id == task.task_id)
            )
            == 2
        )


def test_old_execution_generation_field_creation_cannot_authorize_modify(
    capability_context,
):
    factory, project_id, task, table, field, record = capability_context
    first = _service(factory)
    ref = _record_ref(project_id, record)
    first_scope = _scope(project_id, task, table, field, ref, 1)
    created_field_id = uid()
    created = first.add_field(
        first_scope,
        AddProjectFieldCommand(
            uid(),
            1,
            project_id,
            table["tableId"],
            table["datasetGeneration"],
            created_field_id,
            {
                "key": "note",
                "name": "备注",
                "type": "string",
                "required": False,
                "validation": {},
            },
            False,
            None,
            2,
        ),
    )[0]
    _advance_execution_generation(factory, task, 2)

    definition = {
        "key": "note",
        "name": "新执行代次不得修改",
        "type": "string",
        "required": False,
        "validation": {},
    }
    impact = DataCatalogService(
        SqlAlchemyProjectDataCatalog(factory)
    ).preview_field_update(
        project_id,
        {
            "projectId": project_id,
            "tableId": table["tableId"],
            "datasetGeneration": table["datasetGeneration"],
            "fieldId": created_field_id,
        },
        definition,
    )
    second = _service(factory)
    operation_id = uid()
    with pytest.raises(ProjectError) as denied:
        second.modify_field(
            _scope(project_id, task, table, field, ref, 2),
            ModifyProjectFieldCommand(
                operation_id,
                2,
                project_id,
                table["tableId"],
                table["datasetGeneration"],
                created_field_id,
                definition,
                created["tableRevision"],
                created["field"]["fieldRevision"],
                impact["impactRevision"],
            ),
        )

    assert denied.value.code == "CAPABILITY_SCOPE_DENIED"
    with factory() as session:
        current = session.get(
            DataFieldRow, (created_field_id, table["datasetGeneration"])
        )
        assert current is not None and current.name == "备注"
        assert session.get(ProjectOperationRow, operation_id) is None


def test_replaced_dataset_rejects_query_write_and_field_without_partial_facts(
    capability_context,
):
    factory, project_id, task, table, field, record = capability_context
    service = _service(factory)
    ref = _record_ref(project_id, record)
    scope = _scope(project_id, task, table, field, ref, 1)
    service.read_record(
        scope,
        ReadProjectRecordRequest(1, ref, [field["ref"]["fieldId"]], "workflow"),
    )
    replacement_generation = uid()
    with factory.begin() as session:
        table_row = session.get(DataTableRow, table["tableId"])
        assert table_row is not None
        session.add(
            DataGenerationRow(
                id=replacement_generation,
                project_id=project_id,
                table_id=table["tableId"],
                identity=table_row.identity,
                source={"kind": "local"},
                created_at=datetime.now(UTC),
            )
        )
        session.flush()
        table_row.current_generation = replacement_generation

    query = QueryProjectRecordsRequest(
        1,
        project_id,
        table["tableId"],
        table["datasetGeneration"],
        [field["ref"]["fieldId"]],
        "workflow",
        None,
        [],
        None,
        10,
    )
    update_id, field_id = uid(), uid()
    calls = (
        lambda: service.query_records(scope, query),
        lambda: service.update_record(
            scope,
            UpdateProjectRecordCommand(
                update_id,
                1,
                ref,
                {field["ref"]["fieldId"]: "must-not-write"},
                record["contentRevision"],
            ),
        ),
        lambda: service.add_field(
            scope,
            AddProjectFieldCommand(
                field_id,
                1,
                project_id,
                table["tableId"],
                table["datasetGeneration"],
                uid(),
                {
                    "key": "stale",
                    "name": "过期字段",
                    "type": "string",
                    "required": False,
                    "validation": {},
                },
                False,
                None,
                2,
            ),
        ),
    )
    for call in calls:
        with pytest.raises(ProjectError) as gone:
            call()
        assert gone.value.code == "DATASET_GENERATION_GONE"

    with factory() as session:
        persisted = SqlAlchemyProjectDataRecords(factory)._required_record(
            session,
            project_id,
            ref.table_id,
            ref.dataset_generation,
            ref.record_key,
        )
        assert persisted.values_json[field["ref"]["fieldId"]] == "original"
        assert session.get(ProjectOperationRow, update_id) is None
        assert session.get(ProjectOperationRow, field_id) is None
        assert (
            session.scalar(
                select(func.count())
                .select_from(ProjectRecordLeaseRow)
                .where(ProjectRecordLeaseRow.task_id == task.task_id)
            )
            == 2
        )


def test_read_evidence_persists_across_service_instances_for_dynamic_write(
    capability_context,
):
    factory, project_id, task, _table, field, record = capability_context
    ref = _record_ref(project_id, record)
    first = _service(factory)
    table = _table
    scope = _scope(project_id, task, table, field, ref, 1)
    first.read_record(
        scope,
        ReadProjectRecordRequest(1, ref, [field["ref"]["fieldId"]], "workflow"),
    )
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ProjectTaskRecordReadRow)
                .where(ProjectTaskRecordReadRow.task_id == task.task_id)
            )
            == 1
        )

    second = _service(factory)
    changed, replayed = second.update_record(
        _scope(project_id, task, table, field, ref, 1),
        UpdateProjectRecordCommand(
            uid(),
            1,
            ref,
            {field["ref"]["fieldId"]: "updated-after-restart"},
            record["contentRevision"],
        ),
    )

    assert replayed is False
    assert changed["contentRevision"] == record["contentRevision"] + 1
    assert changed["values"][0]["fieldId"] == field["ref"]["fieldId"]
    assert changed["values"][0]["value"] == "updated-after-restart"


def test_typed_identity_updates_only_text_one_when_integer_one_exists(
    capability_context,
):
    factory, project_id, task, table, field, _record = capability_context
    now = datetime.now(UTC)
    with factory.begin() as session:
        for key_type, value in (
            ("text", "text-original"),
            ("integer", "integer-original"),
        ):
            session.add(
                DataRecordRow(
                    project_id=project_id,
                    table_id=table["tableId"],
                    dataset_generation=table["datasetGeneration"],
                    key_type=key_type,
                    key_value="1",
                    values_json={field["ref"]["fieldId"]: value},
                    record_slots=[],
                    status_id=None,
                    current_environment_id=None,
                    content_revision=1,
                    status_revision=1,
                    link_revision=1,
                    deleted=False,
                    created_at=now,
                    updated_at=now,
                )
            )

    service = _service(factory)
    text_ref = RecordRef(
        project_id,
        table["tableId"],
        table["datasetGeneration"],
        RecordKey("text", "1"),
    )
    scope = _scope(project_id, task, table, field, text_ref, 1)
    service.read_record(
        scope,
        ReadProjectRecordRequest(1, text_ref, [field["ref"]["fieldId"]], "workflow"),
    )
    service.update_record(
        scope,
        UpdateProjectRecordCommand(
            uid(),
            1,
            text_ref,
            {field["ref"]["fieldId"]: "text-updated"},
            1,
        ),
    )

    with factory() as session:
        rows = {
            row.key_type: row
            for row in session.scalars(
                select(DataRecordRow).where(
                    DataRecordRow.dataset_generation == table["datasetGeneration"],
                    DataRecordRow.key_value == "1",
                )
            )
        }
        assert rows["text"].values_json[field["ref"]["fieldId"]] == "text-updated"
        assert rows["text"].content_revision == 2
        assert (
            rows["integer"].values_json[field["ref"]["fieldId"]] == "integer-original"
        )
        assert rows["integer"].content_revision == 1
