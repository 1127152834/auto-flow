from uuid import uuid4

import pytest
from sqlalchemy import select

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.schema import DataSchemaService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.projects.service import ProjectService
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataImpactRow,
    DataRecordRow,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_data_schema import (
    SqlAlchemyProjectDataSchema,
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
    path = tmp_path / "schema.sqlite3"
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
    catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(factory))
    for revision, key in enumerate(("name", "other"), 1):
        catalog.create_field(
            project,
            table["tableId"],
            uid(),
            {
                "definition": {
                    "key": key,
                    "name": key,
                    "type": "string",
                    "required": False,
                    "validation": {},
                },
                "expectedTableRevision": revision,
                "sourceColumnPolicy": "localOnly",
            },
        )
    fields = catalog.fields(project, table["tableId"])["items"]
    records = DataRecordService(SqlAlchemyProjectDataRecords(factory))
    for value in ("one", "two"):
        records.create(
            project,
            table["tableId"],
            uid(),
            {
                "datasetGeneration": table["datasetGeneration"],
                "values": [{"fieldId": fields[0]["ref"]["fieldId"], "value": value}],
            },
        )
    service = DataSchemaService(SqlAlchemyProjectDataSchema(factory))
    yield service, factory, project, table, fields
    factory.dispose()


def candidate(ctx):
    _, _, _, table, fields = ctx
    return {
        "datasetGeneration": table["datasetGeneration"],
        "expectedTableRevision": 3,
        "fields": [
            {
                "kind": "existing",
                "fieldId": field["ref"]["fieldId"],
                "expectedFieldRevision": field["fieldRevision"],
                "definition": {
                    key: field[key]
                    for key in ("key", "name", "type", "required", "validation")
                },
            }
            for field in fields
        ],
    }


def add_field(draft, **changes):
    entry = {
        "kind": "new",
        "clientId": uid(),
        "sourceColumnPolicy": "localOnly",
        "definition": {
            "key": "new",
            "name": "New",
            "type": "boolean",
            "required": False,
            "validation": {},
        },
        **changes,
    }
    draft["fields"].append(entry)
    return entry


def preview(ctx, draft):
    service, _, project, table, _ = ctx
    return service.preview(project, table["tableId"], draft)


def test_preview_has_durable_bounded_internal_evidence_without_business_writes(ctx):
    _, factory, _, _, _ = ctx
    draft = candidate(ctx)
    new = add_field(draft, existingRecordDefault=False)
    report = preview(ctx, draft)
    assert report["affectedRecords"] == 2 and report["backfillBytes"] > 0
    assert report["blockers"] == [] and "prepared" not in report
    assert report["referenceAvailability"] == {
        "automations": "notImplemented",
        "sync": "notImplemented",
    }
    with factory() as session:
        saved = session.get(DataImpactRow, report["impactRevision"])
        assert saved.action == "saveTableSchema"
        assert saved.report["prepared"]["createdFieldIds"][new["clientId"]]
        assert len(session.scalars(select(DataFieldRow)).all()) == 2
        assert all(
            row.content_revision == 1 for row in session.scalars(select(DataRecordRow))
        )


def test_new_required_default_and_changed_invalid_fields_block(ctx):
    draft = candidate(ctx)
    add_field(
        draft,
        definition={
            "key": "new",
            "name": "New",
            "type": "string",
            "required": True,
            "validation": {},
        },
    )
    assert (
        preview(ctx, draft)["blockers"][0]["code"] == "EXISTING_RECORD_DEFAULT_REQUIRED"
    )
    draft = candidate(ctx)
    draft["fields"][0]["definition"]["type"] = "number"
    assert preview(ctx, draft)["blockers"][0]["affectedRecords"] == 2


def test_unchanged_invalid_values_are_not_revalidated(ctx):
    _, factory, _, _, fields = ctx
    with factory() as session:
        row = session.scalar(select(DataRecordRow))
        row.values_json = {**row.values_json, fields[1]["ref"]["fieldId"]: 42}
        session.commit()
    report = preview(ctx, candidate(ctx))
    assert not report["blockers"]
    assert report["warnings"] == []


def test_unchanged_pattern_timeout_cannot_block_label_or_new_field(ctx, monkeypatch):
    from autoflow.infrastructure.database import project_data_schema as module

    draft = candidate(ctx)
    draft["fields"][0]["definition"]["name"] = "Label only"
    add_field(draft, existingRecordDefault=False)

    def timeout(*args):
        raise ProjectError("PATTERN_VALIDATION_TIMEOUT", "old pattern", 422)

    monkeypatch.setattr(module, "validate_value", timeout)
    report = preview(ctx, draft)
    assert not report["blockers"] and not report["warnings"]
    result = ctx[0].commit(
        ctx[2],
        ctx[3]["tableId"],
        uid(),
        {"candidate": draft, "impactRevision": report["impactRevision"]},
    )[0]
    assert result["backfilledRecords"] == 2


def test_validation_runs_without_read_transaction_and_rechecks_guard(ctx, monkeypatch):
    from autoflow.infrastructure.database import project_data_schema as module

    original = module.validate_value
    changed = False

    def concurrent(definition, value):
        nonlocal changed
        if not changed:
            changed = True
            with ctx[1]() as session:
                row = session.scalar(select(DataRecordRow))
                row.status_revision += 1
                session.commit()
        return original(definition, value)

    monkeypatch.setattr(module, "validate_value", concurrent)
    draft = candidate(ctx)
    draft["fields"][0]["definition"]["required"] = True
    with pytest.raises(ProjectError) as caught:
        preview(ctx, draft)
    assert caught.value.code == "IMPACT_STALE"


@pytest.mark.parametrize("count", [1000, 1001])
def test_backfill_row_boundary_is_real_and_prepared_remains_bounded(ctx, count):
    _, factory, project, table, fields = ctx
    with factory() as session:
        sample = session.scalar(select(DataRecordRow))
        for index in range(count - 2):
            session.add(
                DataRecordRow(
                    project_id=project,
                    table_id=table["tableId"],
                    dataset_generation=table["datasetGeneration"],
                    key_type="text",
                    key_value=f"boundary-{index}",
                    values_json={fields[0]["ref"]["fieldId"]: "x"},
                    record_slots=[],
                    status_id=None,
                    current_environment_id=None,
                    content_revision=1,
                    status_revision=1,
                    link_revision=1,
                    deleted=False,
                    created_at=sample.created_at,
                    updated_at=sample.updated_at,
                )
            )
        session.commit()
    draft = candidate(ctx)
    add_field(draft, existingRecordDefault=False)
    report = preview(ctx, draft)
    assert report["affectedRecords"] == count
    assert bool(report["blockers"]) == (count > 1000)
    with factory() as session:
        entries = session.get(DataImpactRow, report["impactRevision"]).report[
            "prepared"
        ]["records"]
        assert len(entries) == (1000 if count == 1000 else 0)
    if count == 1000:
        result, _, _ = ctx[0].commit(
            project,
            table["tableId"],
            uid(),
            {"candidate": draft, "impactRevision": report["impactRevision"]},
        )
        assert result["backfilledRecords"] == 1000


@pytest.mark.parametrize("extra", [0, 1])
def test_backfill_byte_boundary_uses_complete_postwrite_utf8_json(ctx, extra):
    from autoflow.domain.project_data.schema import canonical_bytes

    _, factory, project, table, fields = ctx
    field_id = fields[0]["ref"]["fieldId"]
    overhead = len(canonical_bytes({field_id: "", "0" * 36: False}))
    with factory() as session:
        first, second = session.scalars(select(DataRecordRow)).all()
        session.delete(second)
        first.values_json = {field_id: "a" * (4 * 1024 * 1024 - overhead + extra)}
        session.commit()
    draft = candidate(ctx)
    add_field(draft, existingRecordDefault=False)
    report = preview(ctx, draft)
    assert report["backfillBytes"] == 4 * 1024 * 1024 + extra
    assert bool(report["blockers"]) == bool(extra)
    if not extra:
        assert (
            ctx[0].commit(
                project,
                table["tableId"],
                uid(),
                {"candidate": draft, "impactRevision": report["impactRevision"]},
            )[0]["backfilledRecords"]
            == 1
        )


def test_optional_missing_does_not_backfill_but_explicit_null_does(ctx):
    draft = candidate(ctx)
    add_field(draft)
    assert preview(ctx, draft)["backfillBytes"] == 0
    draft["fields"][-1]["existingRecordDefault"] = None
    assert preview(ctx, draft)["affectedRecords"] == 2


def test_single_row_validation_checks_deadline_between_fields(ctx, monkeypatch):
    from autoflow.infrastructure.database import project_data_schema as module

    with ctx[1]() as session:
        rows = session.scalars(select(DataRecordRow)).all()
        session.delete(rows[1])
        session.commit()
    draft = candidate(ctx)
    for item in draft["fields"]:
        item["definition"]["validation"] = {"maxLength": 100}
    clock = [0.0]
    calls = []
    original = module.validate_value

    def slow_validation(definition, value):
        calls.append(definition["key"])
        result = original(definition, value)
        clock[0] += 70
        return result

    monkeypatch.setattr(module, "monotonic", lambda: clock[0])
    monkeypatch.setattr(module, "validate_value", slow_validation)
    with pytest.raises(ProjectError) as caught:
        preview(ctx, draft)
    assert caught.value.code == "FIELD_VALIDATION_TIMEOUT"
    assert calls == ["name", "other"]
    with ctx[1]() as session:
        assert not session.scalars(select(DataImpactRow)).all()
