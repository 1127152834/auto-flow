from uuid import uuid4

import pytest
from sqlalchemy import event, func, select

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.projects.service import ProjectService
from autoflow.domain.project_data.identity import RecordKey, encode_record_key
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataFieldRow,
    DataRecordRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def uid():
    return str(uuid4())


@pytest.fixture
def ctx(tmp_path):
    factory = create_session_factory(tmp_path / "records.sqlite3")
    migrate_database(tmp_path / "records.sqlite3")
    project = (
        ProjectService(SqlAlchemyProjects(factory))
        .create(uid(), {"name": "p"})[0]
        .project_id
    )
    table = DataTableService(SqlAlchemyProjectData(factory)).create(
        project, uid(), {"name": "t"}
    )[0]
    catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(factory))
    field = catalog.create_field(
        project,
        table["tableId"],
        uid(),
        {
            "definition": {
                "key": "name",
                "name": "Name",
                "type": "string",
                "required": True,
                "validation": {},
            },
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]
    yield (
        DataRecordService(SqlAlchemyProjectDataRecords(factory)),
        catalog,
        factory,
        project,
        table,
        field,
    )
    factory.dispose()


@pytest.mark.parametrize("explicit_null", [False, True])
def test_record_snapshots_preserve_missing_cells_and_operation_history(
    ctx, explicit_null
):
    service, catalog, factory, project, table, required = ctx
    tid, generation = table["tableId"], table["datasetGeneration"]
    required_id = required["ref"]["fieldId"]

    def add_optional(name, revision):
        return catalog.create_field(
            project,
            tid,
            uid(),
            {
                "definition": {
                    "key": name,
                    "name": name,
                    "type": "string",
                    "required": False,
                    "validation": {},
                },
                "expectedTableRevision": revision,
                "sourceColumnPolicy": "localOnly",
            },
        )[0]["field"]["ref"]["fieldId"]

    optional_id = add_optional("optional", 2)
    values = [{"fieldId": required_id, "value": "one"}]
    if explicit_null:
        values.append({"fieldId": optional_id, "value": None})
    payload = {"datasetGeneration": generation, "values": values}
    idem = uid()
    created, operation, _ = service.create(project, tid, idem, payload)
    assert {cell["fieldId"]: cell["value"] for cell in created["values"]} == {
        cell["fieldId"]: cell["value"] for cell in values
    }
    encoded = encode_record_key(RecordKey("uuid", created["ref"]["recordKey"]["value"]))
    added_id = add_optional("later", 3)
    assert service.get(project, tid, generation, encoded, "uuid") == created
    changed, _, _ = service.update(
        project,
        tid,
        encoded,
        uid(),
        {
            "datasetGeneration": generation,
            "recordKeyType": "uuid",
            "expectedContentRevision": 1,
            "values": [{"fieldId": added_id, "value": None}],
        },
    )
    assert changed["contentRevision"] == 2
    assert {cell["fieldId"]: cell["value"] for cell in changed["values"]} == {
        **{cell["fieldId"]: cell["value"] for cell in values},
        added_id: None,
    }
    replayed, old_operation, replay = service.create(project, tid, idem, payload)
    assert replay and replayed == created and old_operation == operation
    with factory() as session:
        assert (
            session.get(ProjectOperationRow, operation.operation_id).result == created
        )
        evidence = session.scalar(
            select(DataChangeRow).where(
                DataChangeRow.operation_id == operation.operation_id
            )
        )
        assert evidence.after == created


def test_create_get_update_replay_and_independent_revisions(ctx):
    service, _, _, project, table, field = ctx
    field_id = field["ref"]["fieldId"]
    created, op, replayed = service.create(
        project,
        table["tableId"],
        uid(),
        {
            "datasetGeneration": table["datasetGeneration"],
            "values": [{"fieldId": field_id, "value": "one"}],
        },
    )
    assert (
        not replayed
        and created["ref"]["recordKey"]["type"] == "uuid"
        and created["contentRevision"]
        == created["statusRevision"]
        == created["linkRevision"]
        == 1
    )
    encoded = encode_record_key(RecordKey("uuid", created["ref"]["recordKey"]["value"]))
    assert (
        service.get(
            project, table["tableId"], table["datasetGeneration"], encoded, "uuid"
        )
        == created
    )
    key = uid()
    changed, _, _ = service.update(
        project,
        table["tableId"],
        encoded,
        key,
        {
            "datasetGeneration": table["datasetGeneration"],
            "recordKeyType": "uuid",
            "values": [{"fieldId": field_id, "value": "two"}],
            "expectedContentRevision": 1,
        },
    )
    assert (
        changed["contentRevision"] == 2
        and changed["statusRevision"] == changed["linkRevision"] == 1
    )
    again, same, replay = service.update(
        project,
        table["tableId"],
        encoded,
        key,
        {
            "datasetGeneration": table["datasetGeneration"],
            "recordKeyType": "uuid",
            "values": [{"fieldId": field_id, "value": "two"}],
            "expectedContentRevision": 1,
        },
    )
    assert replay and again == changed and same.operation_id != op.operation_id


def test_status_clear_always_advances_but_same_nonnull_is_noop(ctx):
    service, catalog, _, project, table, field = ctx
    fid = field["ref"]["fieldId"]
    record = service.create(
        project,
        table["tableId"],
        uid(),
        {
            "datasetGeneration": table["datasetGeneration"],
            "values": [{"fieldId": fid, "value": "x"}],
        },
    )[0]
    encoded = encode_record_key(RecordKey("uuid", record["ref"]["recordKey"]["value"]))
    status = catalog.create_status(
        project,
        table["tableId"],
        uid(),
        {"name": "Ready", "color": "#123456", "order": 0, "expectedTableRevision": 2},
    )[0]["status"]
    set_value = service.set_status(
        project,
        table["tableId"],
        encoded,
        uid(),
        {
            "datasetGeneration": table["datasetGeneration"],
            "recordKeyType": "uuid",
            "statusId": status["statusId"],
            "expectedStatusRevision": 1,
        },
    )[0]
    noop = service.set_status(
        project,
        table["tableId"],
        encoded,
        uid(),
        {
            "datasetGeneration": table["datasetGeneration"],
            "recordKeyType": "uuid",
            "statusId": status["statusId"],
            "expectedStatusRevision": 2,
        },
    )[0]
    cleared = service.set_status(
        project,
        table["tableId"],
        encoded,
        uid(),
        {
            "datasetGeneration": table["datasetGeneration"],
            "recordKeyType": "uuid",
            "statusId": None,
            "expectedStatusRevision": 2,
            "expectedFromStatusId": status["statusId"],
        },
    )[0]
    cleared_again = service.set_status(
        project,
        table["tableId"],
        encoded,
        uid(),
        {
            "datasetGeneration": table["datasetGeneration"],
            "recordKeyType": "uuid",
            "statusId": None,
            "expectedStatusRevision": 3,
        },
    )[0]
    assert (
        set_value["statusRevision"] == noop["statusRevision"] == 2
        and cleared["statusRevision"] == 3
        and cleared_again["statusRevision"] == 4
    )


def test_validation_unknown_duplicate_required_and_old_generation(ctx):
    service, _, _, project, table, field = ctx
    fid = field["ref"]["fieldId"]
    for values in (
        [],
        [{"fieldId": fid, "value": "x"}, {"fieldId": fid, "value": "y"}],
        [{"fieldId": uid(), "value": "x"}],
    ):
        with pytest.raises(ProjectError):
            service.create(
                project,
                table["tableId"],
                uid(),
                {"datasetGeneration": table["datasetGeneration"], "values": values},
            )
    with pytest.raises(ProjectError) as error:
        service.get(project, table["tableId"], uid(), "YQ", "text")
    assert error.value.status == 410


def test_field_identity_preserves_typed_keys_and_is_immutable(ctx):
    service, catalog, factory, project, table, base_field = ctx
    number = catalog.create_field(
        project,
        table["tableId"],
        uid(),
        {
            "definition": {
                "key": "number",
                "name": "Number",
                "type": "number",
                "required": True,
                "validation": {},
            },
            "expectedTableRevision": 2,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]
    number_id = number["ref"]["fieldId"]
    with factory.begin() as session:
        session.get(DataTableRow, table["tableId"]).identity = {
            "mode": "field",
            "fieldId": number_id,
        }
    created = service.create(
        project,
        table["tableId"],
        uid(),
        {
            "datasetGeneration": table["datasetGeneration"],
            "values": [
                {"fieldId": number_id, "value": 1},
                {"fieldId": base_field["ref"]["fieldId"], "value": "x"},
            ],
        },
    )[0]
    assert created["ref"]["recordKey"] == {"type": "integer", "value": "1"}
    encoded = encode_record_key(RecordKey("integer", "1"))
    with pytest.raises(ProjectError) as error:
        service.update(
            project,
            table["tableId"],
            encoded,
            uid(),
            {
                "datasetGeneration": table["datasetGeneration"],
                "recordKeyType": "integer",
                "values": [{"fieldId": number_id, "value": 2}],
                "expectedContentRevision": 1,
            },
        )
    assert error.value.code == "IDENTITY_FIELD_IMMUTABLE"


def test_create_record_fault_rolls_back_record_operation_and_change(ctx):
    service, _, factory, project, table, field = ctx
    baseline = None
    with factory() as session:
        baseline = session.scalar(select(func.count()).select_from(DataChangeRow))
    operation_key = uid()

    def fail_change(mapper, connection, target):
        raise RuntimeError("record change failed")

    event.listen(DataChangeRow, "before_insert", fail_change)
    try:
        with pytest.raises(RuntimeError, match="record change failed"):
            service.create(
                project,
                table["tableId"],
                operation_key,
                {
                    "datasetGeneration": table["datasetGeneration"],
                    "values": [{"fieldId": field["ref"]["fieldId"], "value": "x"}],
                },
            )
    finally:
        event.remove(DataChangeRow, "before_insert", fail_change)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(DataRecordRow)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(ProjectOperationRow)
                .where(ProjectOperationRow.idempotency_key == operation_key)
            )
            == 0
        )
        assert (
            session.scalar(select(func.count()).select_from(DataChangeRow)) == baseline
        )


def test_lost_create_response_replays_and_same_key_cannot_target_another_record(ctx):
    service, _, _, project, table, field = ctx
    field_id = field["ref"]["fieldId"]
    create_key = uid()
    payload = {
        "datasetGeneration": table["datasetGeneration"],
        "values": [{"fieldId": field_id, "value": "one"}],
    }
    first, operation, _ = service.create(project, table["tableId"], create_key, payload)
    replayed, same, replay = service.create(
        project, table["tableId"], create_key, payload
    )
    assert replay and replayed == first and same.operation_id == operation.operation_id
    second = service.create(
        project,
        table["tableId"],
        uid(),
        {
            "datasetGeneration": table["datasetGeneration"],
            "values": [{"fieldId": field_id, "value": "two"}],
        },
    )[0]
    first_encoded = encode_record_key(
        RecordKey("uuid", first["ref"]["recordKey"]["value"])
    )
    second_encoded = encode_record_key(
        RecordKey("uuid", second["ref"]["recordKey"]["value"])
    )
    key = uid()
    patch = {
        "datasetGeneration": table["datasetGeneration"],
        "recordKeyType": "uuid",
        "values": [{"fieldId": field_id, "value": "changed"}],
        "expectedContentRevision": 1,
    }
    service.update(project, table["tableId"], first_encoded, key, patch)
    with pytest.raises(ProjectError) as error:
        service.update(project, table["tableId"], second_encoded, key, patch)
    assert error.value.code == "OPERATION_PAYLOAD_MISMATCH"


def test_text_identity_keeps_001_distinct_from_text_1(ctx):
    service, catalog, factory, project, _, _ = ctx
    table = DataTableService(SqlAlchemyProjectData(factory)).create(
        project, uid(), {"name": "text identity"}
    )[0]
    field = catalog.create_field(
        project,
        table["tableId"],
        uid(),
        {
            "definition": {
                "key": "identity",
                "name": "Identity",
                "type": "string",
                "required": True,
                "validation": {},
            },
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]
    field_id = field["ref"]["fieldId"]
    with factory.begin() as session:
        session.get(DataTableRow, table["tableId"]).identity = {
            "mode": "field",
            "fieldId": field_id,
        }
    keys = []
    for value in ("001", "1"):
        record = service.create(
            project,
            table["tableId"],
            uid(),
            {
                "datasetGeneration": table["datasetGeneration"],
                "values": [{"fieldId": field_id, "value": value}],
            },
        )[0]
        keys.append(record["ref"]["recordKey"])
    assert keys == [{"type": "text", "value": "001"}, {"type": "text", "value": "1"}]


def test_formula_fields_and_unsupported_sources_are_not_writable(ctx):
    service, _, factory, project, table, field = ctx
    field_id = field["ref"]["fieldId"]
    with factory.begin() as session:
        session.get(DataFieldRow, (field_id, table["datasetGeneration"])).formula = True
    with pytest.raises(ProjectError) as error:
        service.create(
            project,
            table["tableId"],
            uid(),
            {
                "datasetGeneration": table["datasetGeneration"],
                "values": [{"fieldId": field_id, "value": "x"}],
            },
        )
    assert error.value.code == "FIELD_NOT_WRITABLE"
    # "unconfigured" is a present source kind whose source is gone, so it is the
    # one kind that still refuses record writes outright. A Sheets table is not
    # in that group: PM6 keeps bound tables locally editable and turns the edit
    # into an outbound push intent.
    with factory.begin() as session:
        session.get(DataTableRow, table["tableId"]).source_kind = "unconfigured"
    with pytest.raises(ProjectError) as error:
        service.create(
            project,
            table["tableId"],
            uid(),
            {
                "datasetGeneration": table["datasetGeneration"],
                "values": [{"fieldId": field_id, "value": "x"}],
            },
        )
    assert error.value.status == 412


def test_sheets_sourced_tables_accept_local_writes(ctx):
    service, _, factory, project, table, field = ctx
    field_id = field["ref"]["fieldId"]
    with factory.begin() as session:
        session.get(DataTableRow, table["tableId"]).source_kind = "sheets"
    record = service.create(
        project,
        table["tableId"],
        uid(),
        {
            "datasetGeneration": table["datasetGeneration"],
            "values": [{"fieldId": field_id, "value": "本地编辑"}],
        },
    )[0]
    assert [cell["value"] for cell in record["values"]] == ["本地编辑"]


@pytest.mark.parametrize(
    "value",
    ["bad\ud800", 10**5000, float("nan"), float("inf"), ["not", "scalar"]],
    ids=["surrogate", "huge-int", "nan", "infinity", "array"],
)
def test_invalid_wire_scalars_fail_before_operation_digest(ctx, value):
    service, _, _, project, table, field = ctx
    with pytest.raises(ProjectError) as error:
        service.create(
            project,
            table["tableId"],
            uid(),
            {
                "datasetGeneration": table["datasetGeneration"],
                "values": [{"fieldId": field["ref"]["fieldId"], "value": value}],
            },
        )
    assert error.value.status == 422


def test_status_rejects_unhashable_record_key_type_as_validation(ctx):
    service, _, _, project, table, field = ctx
    record = service.create(
        project,
        table["tableId"],
        uid(),
        {
            "datasetGeneration": table["datasetGeneration"],
            "values": [{"fieldId": field["ref"]["fieldId"], "value": "x"}],
        },
    )[0]
    encoded = encode_record_key(RecordKey("uuid", record["ref"]["recordKey"]["value"]))
    with pytest.raises(ProjectError) as error:
        service.set_status(
            project,
            table["tableId"],
            encoded,
            uid(),
            {
                "datasetGeneration": table["datasetGeneration"],
                "recordKeyType": [],
                "statusId": None,
                "expectedStatusRevision": 1,
            },
        )
    assert error.value.status == 422
