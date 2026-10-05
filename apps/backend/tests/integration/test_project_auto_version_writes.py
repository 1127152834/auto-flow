"""Remediation M2 R2-24: a Task may write its rows without naming a version; conflicts are per field."""

import pytest

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.domain.project_data.capabilities import (
    ReadProjectRecordRequest,
    RecordReadGrant,
    TableCapabilityGrant,
    TaskCapabilityScope,
    UpdateProjectRecordCommand,
)
from autoflow.domain.project_data.identity import encode_record_key
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from tests.integration.test_project_capability_fencing import (  # noqa: F401
    _record_ref,
    _service,
    capability_context,
)
from tests.integration.test_project_run_data_start import uid


@pytest.fixture
def two_fields(capability_context):  # noqa: F811
    factory, project_id, task, table, field, record = capability_context
    second = DataCatalogService(SqlAlchemyProjectDataCatalog(factory)).create_field(
        project_id, table["tableId"], uid(),
        {"definition": {"key": "note", "name": "备注", "type": "string", "required": False, "validation": {}},
         "expectedTableRevision": 2, "sourceColumnPolicy": "localOnly"},
    )[0]["field"]
    ref = _record_ref(project_id, record)
    ids = (field["ref"]["fieldId"], second["ref"]["fieldId"])
    scope = TaskCapabilityScope(
        project_id, task.task_id, task.run_id, 1, frozenset(), frozenset(),
        frozenset({RecordReadGrant(ref, frozenset(ids), frozenset({"workflow"}))}), frozenset(),
        frozenset({TableCapabilityGrant(table["tableId"], table["datasetGeneration"], frozenset({"updateRecord"}),
                                        frozenset(ids), frozenset({"workflow"}))}),
    )
    service = _service(factory)
    service.read_record(scope, ReadProjectRecordRequest(1, ref, list(ids), "workflow"))
    return factory, project_id, table, ref, ids, scope, service


def person_edits(factory, project_id, table, ref, values):
    records = DataRecordService(SqlAlchemyProjectDataRecords(factory))
    with factory() as session:
        current = SqlAlchemyProjectDataRecords(factory)._required_record(
            session, project_id, ref.table_id, ref.dataset_generation, ref.record_key)
        revision = current.content_revision
    records.update(project_id, table["tableId"], encode_record_key(ref.record_key), uid(), {
        "datasetGeneration": ref.dataset_generation, "recordKeyType": ref.record_key.type,
        "values": [{"fieldId": field_id, "value": value} for field_id, value in values.items()],
        "expectedContentRevision": revision,
    })


def value_of(result, field_id):
    return next(item["value"] for item in result["values"] if item["fieldId"] == field_id)


def test_versionless_writes_by_the_same_task_never_conflict_with_themselves(two_fields):
    _factory, _project, _table, ref, (value, _note), scope, service = two_fields
    first, _ = service.update_record(scope, UpdateProjectRecordCommand(uid(), 1, ref, {value: "第一次"}))
    second, _ = service.update_record(scope, UpdateProjectRecordCommand(uid(), 1, ref, {value: "第二次"}))
    assert value_of(second, value) == "第二次"
    assert second["contentRevision"] == first["contentRevision"] + 1


def test_someone_else_changing_another_field_does_not_block_the_task(two_fields):
    factory, project_id, table, ref, (value, note), scope, service = two_fields
    person_edits(factory, project_id, table, ref, {note: "人工备注"})
    result, _ = service.update_record(scope, UpdateProjectRecordCommand(uid(), 1, ref, {value: "任务写入"}))
    assert value_of(result, value) == "任务写入"
    assert value_of(result, note) == "人工备注", "the other person's field is kept"


def test_someone_else_changing_the_same_field_is_a_field_conflict(two_fields):
    factory, project_id, table, ref, (value, _note), scope, service = two_fields
    person_edits(factory, project_id, table, ref, {value: "人工修改"})
    with pytest.raises(ProjectError) as conflict:
        service.update_record(scope, UpdateProjectRecordCommand(uid(), 1, ref, {value: "任务写入"}))
    assert conflict.value.code == "FIELD_CONFLICT" and conflict.value.status == 409
    assert conflict.value.details["fields"] == [{"fieldId": value, "currentValue": "人工修改", "attemptedValue": "任务写入"}]


def test_an_explicit_old_version_keeps_the_strict_whole_record_check(two_fields):
    factory, project_id, table, ref, (value, note), scope, service = two_fields
    person_edits(factory, project_id, table, ref, {note: "人工备注"})
    with pytest.raises(ProjectError) as conflict:
        service.update_record(scope, UpdateProjectRecordCommand(uid(), 1, ref, {value: "任务写入"}, 1))
    assert conflict.value.code == "REVISION_CONFLICT"


def test_replaying_the_same_versionless_command_returns_the_original_result(two_fields):
    _factory, _project, _table, ref, (value, _note), scope, service = two_fields
    command = UpdateProjectRecordCommand(uid(), 1, ref, {value: "一次"})
    first, replayed_first = service.update_record(scope, command)
    again, replayed = service.update_record(scope, command)
    assert (replayed_first, replayed) == (False, True) and again == first


def test_a_claimed_row_written_through_a_table_grant_uses_the_claim_as_its_baseline(capability_context):  # noqa: F811
    """Found by G1 (M4): a cycle run rewriting a claimed row's field was refused as a field conflict."""
    from sqlalchemy import select

    from autoflow.infrastructure.database.project_run_models import (
        ProjectTaskInputSnapshotRow,
    )

    factory, project_id, task, *_rest = capability_context
    with factory() as session:
        snapshot = session.scalar(select(ProjectTaskInputSnapshotRow).where(ProjectTaskInputSnapshotRow.task_id == task.task_id))
        claimed = snapshot.inputs[0]
    ref = _record_ref(project_id, {"ref": claimed["recordRef"]})
    field_id = claimed["values"][0]["fieldId"]
    scope = TaskCapabilityScope(
        project_id, task.task_id, task.run_id, 1, frozenset(), frozenset(), frozenset(), frozenset(),
        frozenset({TableCapabilityGrant(ref.table_id, ref.dataset_generation, frozenset({"updateRecord"}),
                                        frozenset({field_id}), frozenset({"workflow"}))}),
    )
    result, _ = _service(factory).update_record(scope, UpdateProjectRecordCommand(uid(), 1, ref, {field_id: "第二轮"}))
    assert value_of(result, field_id) == "第二轮"
