import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.queries import DataRecordQueryService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.projects.service import ProjectService
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectRow
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.project_data_queries import (
    SqlAlchemyProjectDataQueries,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def uid():
    return str(uuid4())


def enc(value):
    return (
        base64.urlsafe_b64encode(
            json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        )
        .decode()
        .rstrip("=")
    )


@pytest.fixture
def ctx(tmp_path):
    path = tmp_path / "query.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    projects = ProjectService(SqlAlchemyProjects(factory))
    project = projects.create(uid(), {"name": "p"})[0].project_id
    table = DataTableService(SqlAlchemyProjectData(factory)).create(
        project, uid(), {"name": "t"}
    )[0]
    catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(factory))
    fields = []
    for index, kind in enumerate(("string", "number", "boolean", "date")):
        fields.append(
            catalog.create_field(
                project,
                table["tableId"],
                uid(),
                {
                    "definition": {
                        "key": kind,
                        "name": kind,
                        "type": kind,
                        "required": False,
                        "validation": {},
                    },
                    "expectedTableRevision": index + 1,
                    "sourceColumnPolicy": "localOnly",
                },
            )[0]["field"]["ref"]["fieldId"]
        )
    now = datetime.now(UTC)
    with factory.begin() as session:
        rows = [
            (
                "text",
                "001",
                {
                    fields[0]: "b",
                    fields[1]: 2,
                    fields[2]: False,
                    fields[3]: {
                        "kind": "date",
                        "precision": "datetime",
                        "value": "2026-01-01T08:00:00",
                        "offset": "+08:00",
                    },
                },
            ),
            (
                "text",
                "1",
                {
                    fields[0]: "a",
                    fields[1]: None,
                    fields[3]: {
                        "kind": "date",
                        "precision": "datetime",
                        "value": "2026-01-01T00:00:00",
                        "offset": "Z",
                    },
                },
            ),
            (
                "integer",
                "1",
                {
                    fields[0]: "a",
                    fields[1]: 1,
                    fields[2]: True,
                    fields[3]: {
                        "kind": "date",
                        "precision": "date",
                        "value": "2026-01-01",
                        "offset": None,
                    },
                },
            ),
            ("uuid", uid(), {}),
        ]
        for kt, kv, values in rows:
            session.add(
                DataRecordRow(
                    project_id=project,
                    table_id=table["tableId"],
                    dataset_generation=table["datasetGeneration"],
                    key_type=kt,
                    key_value=kv,
                    values_json=values,
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
    yield (
        DataRecordQueryService(SqlAlchemyProjectDataQueries(factory)),
        factory,
        project,
        table,
        fields,
    )
    factory.dispose()


def query(ctx, expression, order, page=1, size=50):
    service, _, project, table, _ = ctx
    return service.query(
        project,
        table["tableId"],
        table["datasetGeneration"],
        enc(expression),
        enc(order),
        page,
        size,
    )


def test_filter_null_typed_and_date_awareness(ctx):
    *_, fields = ctx
    nulls = query(
        ctx, {"type": "compare", "fieldId": fields[1], "operator": "isNull"}, []
    )
    assert nulls["total"] == 2
    missing = next(
        item for item in nulls["items"] if item["ref"]["recordKey"]["type"] == "uuid"
    )
    assert all(cell["fieldId"] != fields[1] for cell in missing["values"])
    neq = query(
        ctx,
        {"type": "compare", "fieldId": fields[1], "operator": "neq", "value": 1},
        [],
    )
    assert [x["ref"]["recordKey"]["value"] for x in neq["items"]] == ["001"]
    wanted = {
        "kind": "date",
        "precision": "datetime",
        "value": "2026-01-01T00:00:00",
        "offset": "Z",
    }
    dates = query(
        ctx,
        {"type": "compare", "fieldId": fields[3], "operator": "eq", "value": wanted},
        [],
    )
    assert dates["total"] == 2


def test_desc_null_last_and_typed_key_stable_across_pages(ctx):
    *_, fields = ctx
    order = [{"fieldId": fields[0], "direction": "desc"}]
    all_items = []
    for page in (1, 2):
        all_items += query(ctx, {"type": "all", "items": []}, order, page, 2)["items"]
    keys = [
        (x["ref"]["recordKey"]["type"], x["ref"]["recordKey"]["value"])
        for x in all_items
    ]
    assert keys[:3] == [("text", "001"), ("text", "1"), ("integer", "1")]
    assert keys[-1][0] == "uuid"
    assert json.loads(query(ctx, {"type": "all", "items": []}, [], 1, 2)["sort"]) == [
        {"systemField": "recordKey", "direction": "asc"}
    ]


def test_scope_generation_archive_and_only_page_materialized(ctx):
    service, _, project, table, _ = ctx
    with pytest.raises(ProjectError) as error:
        service.query(
            uid(),
            table["tableId"],
            table["datasetGeneration"],
            enc({"type": "all", "items": []}),
            enc([]),
        )
    assert error.value.status == 404
    with pytest.raises(ProjectError) as error:
        service.query(
            project, table["tableId"], uid(), enc({"type": "all", "items": []}), enc([])
        )
    assert error.value.status == 410
    _, factory, _, _, _ = ctx
    now = datetime.now(UTC)
    with factory.begin() as session:
        session.get(ProjectRow, project).lifecycle_state = "archived"
        for index in range(500):
            session.add(
                DataRecordRow(
                    project_id=project,
                    table_id=table["tableId"],
                    dataset_generation=table["datasetGeneration"],
                    key_type="text",
                    key_value=f"bulk-{index:04}",
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

    def count(*_):
        nonlocal loaded
        loaded += 1

    event.listen(DataRecordRow, "load", count)
    try:
        result = query(ctx, {"type": "all", "items": []}, [], 1, 2)
    finally:
        event.remove(DataRecordRow, "load", count)
    assert result["total"] == 504 and len(result["items"]) == 2 and loaded == 2


def test_default_key_query_does_not_decode_large_unreferenced_values(ctx, monkeypatch):
    import autoflow.infrastructure.database.project_data_queries as module

    service, factory, project, table, fields = ctx
    now = datetime.now(UTC)
    with factory.begin() as session:
        for index in range(400):
            session.add(
                DataRecordRow(
                    project_id=project,
                    table_id=table["tableId"],
                    dataset_generation=table["datasetGeneration"],
                    key_type="text",
                    key_value=f"payload-{index:04}",
                    values_json={fields[0]: "x" * 16384},
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
    monkeypatch.setattr(
        module,
        "_collation",
        lambda *_: (_ for _ in ()).throw(AssertionError("sort payload decoded")),
    )
    monkeypatch.setattr(
        module,
        "matches",
        lambda *_: (_ for _ in ()).throw(AssertionError("filter payload decoded")),
    )
    result = service.query(
        project,
        table["tableId"],
        table["datasetGeneration"],
        enc({"type": "all", "items": []}),
        enc([]),
        2,
        2,
    )
    assert result["total"] == 404 and len(result["items"]) == 2


def test_query_cleans_callbacks_before_pooled_connection_can_be_reused(ctx):
    from threading import Event, Thread, current_thread

    service, factory, project, table, fields = ctx
    ready, resume = Event(), Event()
    second_result = []
    started = False

    def second_query():
        try:
            second_result.append(
                service.query(
                    project,
                    table["tableId"],
                    table["datasetGeneration"],
                    enc(
                        {
                            "type": "compare",
                            "fieldId": fields[0],
                            "operator": "isNotNull",
                        }
                    ),
                    enc([]),
                    1,
                    50,
                )
            )
        except SQLAlchemyError as error:
            second_result.append(error)

    thread = Thread(target=second_query, name="query-second")

    def after_transaction_end(_session, _transaction):
        nonlocal started
        if not started and current_thread().name != "query-second":
            started = True
            thread.start()
            assert ready.wait(5)

    def before_cursor_execute(
        _connection, _cursor, statement, _parameters, _context, _many
    ):
        if current_thread().name == "query-second" and "count(" in statement.lower():
            ready.set()
            assert resume.wait(5)

    event.listen(factory.class_, "after_transaction_end", after_transaction_end)
    event.listen(factory.kw["bind"], "before_cursor_execute", before_cursor_execute)
    try:
        first = query(
            ctx, {"type": "compare", "fieldId": fields[0], "operator": "isNotNull"}, []
        )
    finally:
        resume.set()
        thread.join(5)
        event.remove(factory.class_, "after_transaction_end", after_transaction_end)
        event.remove(factory.kw["bind"], "before_cursor_execute", before_cursor_execute)
    assert first["total"] == 3
    assert len(second_result) == 1 and isinstance(second_result[0], dict)
    assert second_result[0]["total"] == 3


def test_count_and_items_share_wal_snapshot_when_row_is_deleted(ctx):
    import sqlite3

    service, factory, project, table, _ = ctx
    changed = False
    database = factory.kw["bind"].url.database
    with sqlite3.connect(database) as outside:
        outside.execute("PRAGMA journal_mode=WAL")

    def delete_after_count(
        _connection, _cursor, statement, _parameters, _context, _many
    ):
        nonlocal changed
        if not changed and "count(" in statement.lower():
            changed = True
            with sqlite3.connect(database) as outside:
                outside.execute(
                    "UPDATE project_data_records SET deleted=1 WHERE key_type='text' AND key_value='001'"
                )
                outside.commit()

    event.listen(factory.kw["bind"], "after_cursor_execute", delete_after_count)
    try:
        result = service.query(
            project,
            table["tableId"],
            table["datasetGeneration"],
            enc({"type": "all", "items": []}),
            enc([]),
            1,
            50,
        )
    finally:
        event.remove(factory.kw["bind"], "after_cursor_execute", delete_after_count)
    assert changed and result["total"] == 4 and len(result["items"]) == 4
    assert query(ctx, {"type": "all", "items": []}, [])["total"] == 3
