from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.projects.service import ProjectService
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataFieldRow,
    DataRecordRow,
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
    factory = create_session_factory(tmp_path / "catalog.sqlite3")
    migrate_database(tmp_path / "catalog.sqlite3")
    project = (
        ProjectService(SqlAlchemyProjects(factory))
        .create(uid(), {"name": "p"})[0]
        .project_id
    )
    table = DataTableService(SqlAlchemyProjectData(factory)).create(
        project, uid(), {"name": "t"}
    )[0]
    yield (
        DataCatalogService(SqlAlchemyProjectDataCatalog(factory)),
        factory,
        project,
        table,
    )
    factory.dispose()


def test_field_create_lists_and_replays_immutable_result(ctx):
    service, _, project, table = ctx
    key = uid()
    payload = {
        "definition": {
            "key": " customer.id ",
            "name": " Customer ",
            "type": "string",
            "required": False,
            "validation": {},
        },
        "expectedTableRevision": 1,
        "sourceColumnPolicy": "localOnly",
    }
    result, op, replayed = service.create_field(project, table["tableId"], key, payload)
    assert (
        not replayed
        and result["field"]["key"] == "customer.id"
        and result["tableRevision"] == 2
    )
    assert service.fields(project, table["tableId"]) == {
        "items": [result["field"]],
        "tableRevision": 2,
    }
    again, same, replayed = service.create_field(
        project, table["tableId"], key, payload
    )
    assert replayed and again == result and same.operation_id == op.operation_id


def test_required_field_backfills_existing_records_atomically(ctx):
    service, factory, project, table = ctx
    now = datetime.now(UTC)
    with factory.begin() as session:
        session.add(
            DataRecordRow(
                project_id=project,
                table_id=table["tableId"],
                dataset_generation=table["datasetGeneration"],
                key_type="text",
                key_value="one",
                values_json={},
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
        "name": "Email",
        "type": "string",
        "required": True,
        "validation": {"minLength": 3},
    }
    with pytest.raises(ProjectError):
        service.create_field(
            project,
            table["tableId"],
            uid(),
            {
                "definition": definition,
                "expectedTableRevision": 1,
                "sourceColumnPolicy": "localOnly",
            },
        )
    result, _, _ = service.create_field(
        project,
        table["tableId"],
        uid(),
        {
            "definition": definition,
            "existingRecordDefault": "a@b",
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    )
    with factory() as session:
        row = session.get(DataRecordRow, (table["datasetGeneration"], "text", "one"))
    assert (
        row.values_json[result["field"]["ref"]["fieldId"]] == "a@b"
        and row.content_revision == 2
        and row.status_revision == row.link_revision == 1
    )


def test_mapped_field_is_deferred_and_duplicate_keys_are_case_sensitive(ctx):
    service, _, project, table = ctx
    definition = {
        "key": "Key",
        "name": "K",
        "type": "string",
        "required": False,
        "validation": {},
    }
    with pytest.raises(ProjectError) as error:
        service.create_field(
            project,
            table["tableId"],
            uid(),
            {
                "definition": definition,
                "expectedTableRevision": 1,
                "sourceColumnPolicy": "mapped",
            },
        )
    assert error.value.status == 412
    service.create_field(
        project,
        table["tableId"],
        uid(),
        {
            "definition": definition,
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    )
    service.create_field(
        project,
        table["tableId"],
        uid(),
        {
            "definition": {**definition, "key": "key"},
            "expectedTableRevision": 2,
            "sourceColumnPolicy": "localOnly",
        },
    )


def test_status_create_sort_update_noop_and_cas(ctx):
    service, _, project, table = ctx
    second, _, _ = service.create_status(
        project,
        table["tableId"],
        uid(),
        {"name": " Later ", "color": "#AABBCC", "order": 2, "expectedTableRevision": 1},
    )
    first, _, _ = service.create_status(
        project,
        table["tableId"],
        uid(),
        {"name": "First", "color": "#112233", "order": 1, "expectedTableRevision": 2},
    )
    assert service.statuses(project, table["tableId"])["items"] == [
        first["status"],
        second["status"],
    ]
    noop, _, _ = service.update_status(
        project,
        table["tableId"],
        first["status"]["statusId"],
        uid(),
        {"name": "First", "expectedStatusRevision": 1, "expectedTableRevision": 3},
    )
    assert noop["tableRevision"] == 3 and noop["status"]["statusRevision"] == 1
    changed, _, _ = service.update_status(
        project,
        table["tableId"],
        first["status"]["statusId"],
        uid(),
        {"color": "#FFFFFF", "expectedStatusRevision": 1, "expectedTableRevision": 3},
    )
    assert (
        changed["tableRevision"] == 4
        and changed["status"]["statusRevision"] == 2
        and changed["status"]["color"] == "#ffffff"
    )


def test_update_status_same_key_for_different_target_conflicts(ctx):
    service, _, project, table = ctx
    one, _, _ = service.create_status(
        project,
        table["tableId"],
        uid(),
        {"name": "one", "color": "#111111", "order": 1, "expectedTableRevision": 1},
    )
    two, _, _ = service.create_status(
        project,
        table["tableId"],
        uid(),
        {"name": "two", "color": "#222222", "order": 2, "expectedTableRevision": 2},
    )
    key = uid()
    payload = {
        "color": "#abcdef",
        "expectedStatusRevision": 1,
        "expectedTableRevision": 3,
    }
    service.update_status(
        project, table["tableId"], one["status"]["statusId"], key, payload
    )
    with pytest.raises(ProjectError) as error:
        service.update_status(
            project, table["tableId"], two["status"]["statusId"], key, payload
        )
    assert error.value.code == "OPERATION_PAYLOAD_MISMATCH"


def test_field_and_record_changes_use_complete_typed_refs(ctx):
    service, factory, project, table = ctx
    now = datetime.now(UTC)
    with factory.begin() as session:
        session.add(
            DataRecordRow(
                project_id=project,
                table_id=table["tableId"],
                dataset_generation=table["datasetGeneration"],
                key_type="text",
                key_value="a/b",
                values_json={},
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
    result, operation, _ = service.create_field(
        project,
        table["tableId"],
        uid(),
        {
            "definition": {
                "key": "x",
                "name": "X",
                "type": "string",
                "required": False,
                "validation": {},
            },
            "existingRecordDefault": "v",
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    )
    ref = result["field"]["ref"]
    assert ref == {
        "projectId": project,
        "tableId": table["tableId"],
        "datasetGeneration": table["datasetGeneration"],
        "fieldId": ref["fieldId"],
    }
    assert operation.resource == {"type": "field", "fieldRef": ref}
    with factory() as session:
        changes = session.scalars(
            select(DataChangeRow)
            .where(DataChangeRow.operation_id == operation.operation_id)
            .order_by(DataChangeRow.sequence)
        ).all()
    assert changes[0].resource == {"type": "field", "fieldRef": ref}
    assert changes[1].resource == {
        "type": "record",
        "recordRef": {
            "projectId": project,
            "tableId": table["tableId"],
            "datasetGeneration": table["datasetGeneration"],
            "recordKey": {"type": "text", "value": "a/b"},
        },
    }


@pytest.mark.parametrize(
    "revision", [True, 0, 10**5000], ids=["boolean", "zero", "huge-integer"]
)
def test_revisions_must_be_positive_json_safe_integers(ctx, revision):
    service, _, project, table = ctx
    with pytest.raises(ProjectError) as error:
        service.create_status(
            project,
            table["tableId"],
            uid(),
            {
                "name": "state",
                "color": "#abcdef",
                "order": 0,
                "expectedTableRevision": revision,
            },
        )
    assert error.value.status == 422


def test_catalog_scope_lifecycle_and_operation_history_are_immutable(ctx):
    service, factory, project, table = ctx
    projects = ProjectService(SqlAlchemyProjects(factory))
    other_project = projects.create(uid(), {"name": "other"})[0].project_id
    other_table = DataTableService(SqlAlchemyProjectData(factory)).create(
        other_project, uid(), {"name": "other"}
    )[0]
    with pytest.raises(ProjectError) as error:
        service.fields(project, other_table["tableId"])
    assert error.value.status == 404
    with pytest.raises(ProjectError) as error:
        service.create_status(
            project,
            other_table["tableId"],
            uid(),
            {
                "name": "cross",
                "color": "#111111",
                "order": 0,
                "expectedTableRevision": 1,
            },
        )
    assert error.value.status == 404
    created, _, _ = service.create_status(
        project,
        table["tableId"],
        uid(),
        {"name": "draft", "color": "#111111", "order": 0, "expectedTableRevision": 1},
    )
    status_id = created["status"]["statusId"]
    sibling = DataTableService(SqlAlchemyProjectData(factory)).create(
        project, uid(), {"name": "sibling"}
    )[0]
    with pytest.raises(ProjectError) as error:
        service.update_status(
            project,
            sibling["tableId"],
            status_id,
            uid(),
            {"name": "leak", "expectedStatusRevision": 1, "expectedTableRevision": 1},
        )
    assert error.value.status == 404
    historical_key = uid()
    historical, operation, _ = service.update_status(
        project,
        table["tableId"],
        status_id,
        historical_key,
        {"name": "ready", "expectedStatusRevision": 1, "expectedTableRevision": 2},
    )
    service.update_status(
        project,
        table["tableId"],
        status_id,
        uid(),
        {"name": "done", "expectedStatusRevision": 2, "expectedTableRevision": 3},
    )
    replayed, same_operation, replay = service.update_status(
        project,
        table["tableId"],
        status_id,
        historical_key,
        {"name": "ready", "expectedStatusRevision": 1, "expectedTableRevision": 2},
    )
    assert replay and replayed == historical and replayed["status"]["name"] == "ready"
    assert same_operation.operation_id == operation.operation_id
    assert (
        projects.operation(key=historical_key, project_id=project).result == historical
    )
    with factory.begin() as session:
        session.get(ProjectRow, project).lifecycle_state = "archived"
    assert service.statuses(project, table["tableId"])["items"][0]["name"] == "done"
    with pytest.raises(ProjectError) as error:
        service.create_status(
            project,
            table["tableId"],
            uid(),
            {
                "name": "blocked",
                "color": "#ffffff",
                "order": 1,
                "expectedTableRevision": 4,
            },
        )
    assert error.value.status == 409


def test_field_default_failure_rolls_back_all_transaction_participants(ctx):
    service, factory, project, table = ctx
    now = datetime.now(UTC)
    with factory.begin() as session:
        for key in ("one", "two"):
            session.add(
                DataRecordRow(
                    project_id=project,
                    table_id=table["tableId"],
                    dataset_generation=table["datasetGeneration"],
                    key_type="text",
                    key_value=key,
                    values_json={},
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
    with factory() as session:
        baseline_changes = session.scalar(
            select(func.count()).select_from(DataChangeRow)
        )
    operation_key = uid()

    def fail_second_record(mapper, connection, target):
        if target.sequence == 3:
            raise RuntimeError("injected change failure")

    event.listen(DataChangeRow, "before_insert", fail_second_record)
    try:
        with pytest.raises(RuntimeError, match="injected"):
            service.create_field(
                project,
                table["tableId"],
                operation_key,
                {
                    "definition": {
                        "key": "email",
                        "name": "Email",
                        "type": "string",
                        "required": True,
                        "validation": {},
                    },
                    "existingRecordDefault": "x",
                    "expectedTableRevision": 1,
                    "sourceColumnPolicy": "localOnly",
                },
            )
    finally:
        event.remove(DataChangeRow, "before_insert", fail_second_record)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(DataFieldRow)) == 0
        assert (
            session.scalar(select(func.count()).select_from(DataChangeRow))
            == baseline_changes
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ProjectOperationRow)
                .where(ProjectOperationRow.idempotency_key == operation_key)
            )
            == 0
        )
        records = session.scalars(select(DataRecordRow)).all()
        assert all(
            record.values_json == {} and record.content_revision == 1
            for record in records
        )


def test_concurrent_status_writes_serialize_name_and_table_cas(ctx):
    service, _, project, table = ctx

    def create_status(name):
        try:
            return service.create_status(
                project,
                table["tableId"],
                uid(),
                {
                    "name": name,
                    "color": "#123456",
                    "order": 0,
                    "expectedTableRevision": 1,
                },
            )[0]
        except ProjectError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(create_status, ["Duplicate", " duplicate "]))
    successes = [value for value in outcomes if isinstance(value, dict)]
    failures = [value for value in outcomes if isinstance(value, ProjectError)]
    assert len(successes) == len(failures) == 1
    assert failures[0].status == 409
    listed = service.statuses(project, table["tableId"])
    assert len(listed["items"]) == 1 and listed["tableRevision"] == 2


def test_field_paths_without_default_do_not_materialize_records(ctx):
    service, factory, project, table = ctx
    now = datetime.now(UTC)
    with factory.begin() as session:
        session.add(
            DataRecordRow(
                project_id=project,
                table_id=table["tableId"],
                dataset_generation=table["datasetGeneration"],
                key_type="text",
                key_value="one",
                values_json={},
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
    loaded = 0

    def count_load(target, context):
        nonlocal loaded
        loaded += 1

    event.listen(DataRecordRow, "load", count_load)
    try:
        service.create_field(
            project,
            table["tableId"],
            uid(),
            {
                "definition": {
                    "key": "optional",
                    "name": "Optional",
                    "type": "string",
                    "required": False,
                    "validation": {},
                },
                "expectedTableRevision": 1,
                "sourceColumnPolicy": "localOnly",
            },
        )
        assert loaded == 0
        with pytest.raises(ProjectError) as error:
            service.create_field(
                project,
                table["tableId"],
                uid(),
                {
                    "definition": {
                        "key": "required",
                        "name": "Required",
                        "type": "string",
                        "required": True,
                        "validation": {},
                    },
                    "expectedTableRevision": 2,
                    "sourceColumnPolicy": "localOnly",
                },
            )
        assert error.value.code == "EXISTING_RECORD_DEFAULT_REQUIRED"
        assert loaded == 0
    finally:
        event.remove(DataRecordRow, "load", count_load)
