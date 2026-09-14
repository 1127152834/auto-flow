from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import event, select

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.projects.service import ProjectService
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataFieldRow,
    DataGenerationRow,
    DataRecordRow,
    DataTableRow,
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
    path = tmp_path / "field-change.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project = (
        ProjectService(SqlAlchemyProjects(factory))
        .create(uid(), {"name": "p"})[0]
        .project_id
    )
    table = DataTableService(SqlAlchemyProjectData(factory)).create(
        project, uid(), {"name": "t"}
    )[0]
    service = DataCatalogService(SqlAlchemyProjectDataCatalog(factory))
    created = service.create_field(
        project,
        table["tableId"],
        uid(),
        {
            "definition": {
                "key": "email",
                "name": "Email",
                "type": "string",
                "required": False,
                "validation": {},
            },
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]
    yield service, factory, project, table, created["field"]
    factory.dispose()


def payload(field, report, **definition):
    return {
        "definition": {
            "key": "email",
            "name": "Email address",
            "type": "string",
            "required": False,
            "validation": {},
            **definition,
        },
        "expectedTableRevision": report["expectedRevisions"]["tableRevision"],
        "expectedFieldRevision": field["fieldRevision"],
        "impactRevision": report["impactRevision"],
    }


def test_preview_update_and_replay_preserve_records(ctx):
    service, factory, project, table, field = ctx
    now = datetime.now(UTC)
    with factory.begin() as session:
        session.add(
            DataRecordRow(
                project_id=project,
                table_id=table["tableId"],
                dataset_generation=table["datasetGeneration"],
                key_type="text",
                key_value="1",
                values_json={field["ref"]["fieldId"]: "x"},
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
    definition = {
        "key": "email",
        "name": "Email address",
        "type": "string",
        "required": False,
        "validation": {},
    }
    report = service.preview_field_update(project, field["ref"], definition)
    key = uid()
    result, operation, replayed = service.update_field(
        project, table["tableId"], field["ref"]["fieldId"], key, payload(field, report)
    )
    again, same, replay = service.update_field(
        project, table["tableId"], field["ref"]["fieldId"], key, payload(field, report)
    )
    assert (
        not replayed
        and replay
        and again == result
        and same.operation_id == operation.operation_id
    )
    assert result["action"] == "update" and result["field"]["name"] == "Email address"
    with factory() as session:
        record = session.scalar(select(DataRecordRow))
        assert (
            record.content_revision,
            record.status_revision,
            record.link_revision,
            record.values_json,
        ) == (1, 1, 1, {field["ref"]["fieldId"]: "x"})
        change = session.scalar(
            select(DataChangeRow).where(
                DataChangeRow.operation_id == operation.operation_id
            )
        )
        assert change.resource == {"type": "field", "fieldRef": field["ref"]}


def test_changed_fact_and_wrong_cas_reject_without_operation(ctx):
    service, factory, project, table, field = ctx
    definition = {
        "key": "email",
        "name": "Changed",
        "type": "string",
        "required": False,
        "validation": {},
    }
    report = service.preview_field_update(project, field["ref"], definition)
    with factory.begin() as session:
        before_count = len(session.scalars(select(ProjectOperationRow)).all())
        session.get(DataTableRow, table["tableId"]).table_revision += 1
    with pytest.raises(ProjectError) as error:
        service.update_field(
            project,
            table["tableId"],
            field["ref"]["fieldId"],
            uid(),
            payload(field, report, name="Changed"),
        )
    assert error.value.status == 409
    with factory() as session:
        assert len(session.scalars(select(ProjectOperationRow)).all()) == before_count


def test_noop_records_operation_without_advancing_revisions(ctx):
    service, _, project, table, field = ctx
    definition = {
        key: field[key] for key in ("key", "name", "type", "required", "validation")
    }
    report = service.preview_field_update(project, field["ref"], definition)
    result, _, _ = service.update_field(
        project,
        table["tableId"],
        field["ref"]["fieldId"],
        uid(),
        payload(field, report, name="Email"),
    )
    assert result["tableRevision"] == 2 and result["field"]["fieldRevision"] == 1


def test_update_requires_exact_safe_payload(ctx):
    service, _, project, table, field = ctx
    with pytest.raises(ProjectError) as error:
        service.update_field(
            project, table["tableId"], field["ref"]["fieldId"], uid(), {}
        )
    assert error.value.status == 422


def _definition(field, **changes):
    return {
        **{
            key: field[key] for key in ("key", "name", "type", "required", "validation")
        },
        **changes,
    }


def _add_record(factory, project, table, field, key="1"):
    now = datetime.now(UTC)
    with factory.begin() as session:
        session.add(
            DataRecordRow(
                project_id=project,
                table_id=table["tableId"],
                dataset_generation=table["datasetGeneration"],
                key_type="text",
                key_value=key,
                values_json={field["ref"]["fieldId"]: "x"},
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


@pytest.mark.parametrize("mutation", ["value", "insert", "delete"])
def test_update_consumption_rejects_changed_record_facts(ctx, mutation):
    service, factory, project, table, field = ctx
    _add_record(factory, project, table, field)
    definition = _definition(field, name="Changed")
    report = service.preview_field_update(project, field["ref"], definition)
    with factory.begin() as session:
        record = session.scalar(select(DataRecordRow))
        if mutation == "value":
            record.values_json = {field["ref"]["fieldId"]: "y"}
        elif mutation == "delete":
            record.deleted = True
        else:
            now = datetime.now(UTC)
            session.add(
                DataRecordRow(
                    project_id=project,
                    table_id=table["tableId"],
                    dataset_generation=table["datasetGeneration"],
                    key_type="text",
                    key_value="2",
                    values_json={field["ref"]["fieldId"]: "x"},
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
    with pytest.raises(ProjectError) as error:
        service.update_field(
            project,
            table["tableId"],
            field["ref"]["fieldId"],
            uid(),
            payload(field, report, name="Changed"),
        )
    assert error.value.status == 412


@pytest.mark.parametrize("guard", ["formula", "identity", "type"])
def test_update_consumption_enforces_field_guards(ctx, guard):
    service, factory, project, table, field = ctx
    definition = _definition(field, name="Changed")
    if guard == "type":
        _add_record(factory, project, table, field)
        definition = _definition(field, type="number")
    else:
        with factory.begin() as session:
            row = session.get(
                DataFieldRow, (field["ref"]["fieldId"], table["datasetGeneration"])
            )
            if guard == "formula":
                row.formula = True
            else:
                session.get(DataTableRow, table["tableId"]).identity = {
                    "mode": "field",
                    "fieldId": row.id,
                }
                definition = _definition(field, type="number")
    report = service.preview_field_update(project, field["ref"], definition)
    with pytest.raises(ProjectError) as error:
        service.update_field(
            project,
            table["tableId"],
            field["ref"]["fieldId"],
            uid(),
            {**payload(field, report), "definition": definition},
        )
    assert error.value.status == 412


def test_update_key_unique_and_same_idempotency_key_different_field(ctx):
    service, _, project, table, field = ctx
    second = service.create_field(
        project,
        table["tableId"],
        uid(),
        {
            "definition": _definition(field, key="other", name="Other"),
            "expectedTableRevision": 2,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]
    duplicate = _definition(field, key="other")
    report = service.preview_field_update(project, field["ref"], duplicate)
    with pytest.raises(ProjectError) as error:
        service.update_field(
            project,
            table["tableId"],
            field["ref"]["fieldId"],
            uid(),
            {**payload(field, report), "definition": duplicate},
        )
    assert error.value.code == "FIELD_KEY_CONFLICT"
    first_change = _definition(field, name="First")
    first_report = service.preview_field_update(project, field["ref"], first_change)
    operation_key = uid()
    service.update_field(
        project,
        table["tableId"],
        field["ref"]["fieldId"],
        operation_key,
        {**payload(field, first_report), "definition": first_change},
    )
    second_change = _definition(second, name="Second")
    second_report = service.preview_field_update(project, second["ref"], second_change)
    with pytest.raises(ProjectError) as mismatch:
        service.update_field(
            project,
            table["tableId"],
            second["ref"]["fieldId"],
            operation_key,
            {**payload(second, second_report), "definition": second_change},
        )
    assert mismatch.value.code == "OPERATION_PAYLOAD_MISMATCH"


def test_change_insert_failure_rolls_back_field_table_and_operation(ctx):
    service, factory, project, table, field = ctx
    definition = _definition(field, name="Changed")
    report = service.preview_field_update(project, field["ref"], definition)

    def fail(*_):
        raise RuntimeError("change insert failed")

    with factory() as session:
        operation_count = len(session.scalars(select(ProjectOperationRow)).all())
        change_count = len(session.scalars(select(DataChangeRow)).all())
    event.listen(DataChangeRow, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            service.update_field(
                project,
                table["tableId"],
                field["ref"]["fieldId"],
                uid(),
                {**payload(field, report), "definition": definition},
            )
    finally:
        event.remove(DataChangeRow, "before_insert", fail)
    with factory() as session:
        stored = session.get(
            DataFieldRow, (field["ref"]["fieldId"], table["datasetGeneration"])
        )
        assert stored.name == "Email" and stored.field_revision == 1
        assert session.get(DataTableRow, table["tableId"]).table_revision == 2
        assert (
            len(session.scalars(select(ProjectOperationRow)).all()) == operation_count
        )
        assert len(session.scalars(select(DataChangeRow)).all()) == change_count


def test_two_updates_from_same_revision_only_one_commits(ctx):
    service, _, project, table, field = ctx
    definitions = [_definition(field, name=name) for name in ("One", "Two")]
    reports = [
        service.preview_field_update(project, field["ref"], item)
        for item in definitions
    ]

    def update(index):
        try:
            service.update_field(
                project,
                table["tableId"],
                field["ref"]["fieldId"],
                uid(),
                {**payload(field, reports[index]), "definition": definitions[index]},
            )
            return "ok"
        except ProjectError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(update, range(2)))
    assert sorted(outcomes, key=str) == [409, "ok"]


def test_generation_replacement_rejects_old_field_target(ctx):
    service, factory, project, table, field = ctx
    definition = _definition(field, name="Changed")
    report = service.preview_field_update(project, field["ref"], definition)
    replacement = uid()
    with factory.begin() as session:
        session.add(
            DataGenerationRow(
                id=replacement,
                project_id=project,
                table_id=table["tableId"],
                identity={"mode": "system"},
                source={"kind": "local"},
                created_at=datetime.now(UTC),
            )
        )
        row = session.get(DataTableRow, table["tableId"])
        row.current_generation = replacement
        row.table_revision += 1
    with pytest.raises(ProjectError) as error:
        service.update_field(
            project,
            table["tableId"],
            field["ref"]["fieldId"],
            uid(),
            {**payload(field, report), "definition": definition},
        )
    assert error.value.status == 404
