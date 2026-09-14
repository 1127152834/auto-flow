"""Field confirmations bind the actual dataset, not only a UI confirmation flag."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from autoflow.application.project_data.tables import DataTableService
from autoflow.application.projects.service import ProjectService
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataImpactRow,
    DataRecordRow,
    DataTableRow,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def key():
    return str(uuid4())


@pytest.fixture
def context(tmp_path):
    from autoflow.infrastructure.database.project_data_impacts import (
        SqlAlchemyProjectDataImpacts,
    )

    path = tmp_path / "impacts.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    projects = ProjectService(SqlAlchemyProjects(factory))
    project = projects.create(key(), {"name": "P"})[0].project_id
    other = projects.create(key(), {"name": "Q"})[0].project_id
    table, _, _ = DataTableService(SqlAlchemyProjectData(factory)).create(
        project, key(), {"name": "Data"}
    )
    ref = {
        "projectId": project,
        "tableId": table["tableId"],
        "datasetGeneration": table["datasetGeneration"],
        "fieldId": key(),
    }
    definition = {
        "key": "mail",
        "name": "Email",
        "type": "string",
        "required": False,
        "validation": {},
    }
    now = datetime.now(UTC)
    with factory.begin() as session:
        session.add(
            DataFieldRow(
                id=ref["fieldId"],
                project_id=project,
                table_id=ref["tableId"],
                dataset_generation=ref["datasetGeneration"],
                key="mail",
                name="Email",
                type="string",
                required=False,
                writable=True,
                formula=False,
                validation={},
                field_revision=1,
                position=0,
            )
        )
        session.flush()
        session.add(
            DataRecordRow(
                project_id=project,
                table_id=ref["tableId"],
                dataset_generation=ref["datasetGeneration"],
                key_type="text",
                key_value="001",
                values_json={ref["fieldId"]: "abc"},
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
        SqlAlchemyProjectDataImpacts(factory),
        factory,
        project,
        other,
        ref,
        definition,
    )
    factory.dispose()


def confirm(context, report, definition=None):
    store, factory, project, _, ref, original = context
    with factory.begin() as session:
        return store.require_field_update(
            session, project, ref, definition or original, report["impactRevision"]
        )


def test_preview_is_durable_and_not_a_business_operation(context):
    store, factory, project, _, ref, definition = context
    with factory() as session:
        operations = session.scalar(
            select(func.count()).select_from(ProjectOperationRow)
        )
    report = store.preview_field_update(project, ref, definition)
    assert report["target"] == {"type": "field", "fieldRef": ref}
    assert report["expectedRevisions"] == {"tableRevision": 1, "fieldRevision": 1}
    assert report["blockers"] == []
    assert report["impactRevision"] > 0
    assert confirm(context, report) == report
    with factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(ProjectOperationRow))
            == operations
        )
        assert (
            session.get(DataImpactRow, report["impactRevision"]).expires_at is not None
        )


@pytest.mark.parametrize(
    "changed", ["projectId", "tableId", "datasetGeneration", "fieldId"]
)
def test_scope_and_generation_checked_before_confirmation(context, changed):
    store, _, project, other, ref, definition = context
    altered = {**ref, changed: other if changed == "projectId" else key()}
    with pytest.raises(ProjectError) as error:
        store.preview_field_update(project, altered, definition)
    assert error.value.status == (410 if changed == "datasetGeneration" else 404)


@pytest.mark.parametrize(
    "mutation", ["value", "revision", "insert", "delete", "table", "field"]
)
def test_changed_facts_invalidate_original_confirmation(context, mutation):
    store, factory, project, _, ref, definition = context
    report = store.preview_field_update(project, ref, definition)
    with factory.begin() as session:
        row = session.scalar(select(DataRecordRow))
        if mutation == "value":
            row.values_json = {ref["fieldId"]: "new"}
        elif mutation == "revision":
            row.content_revision += 1
        elif mutation == "delete":
            row.deleted = True
        elif mutation == "table":
            session.get(DataTableRow, ref["tableId"]).table_revision += 1
        elif mutation == "field":
            session.get(
                DataFieldRow, (ref["fieldId"], ref["datasetGeneration"])
            ).field_revision += 1
        else:
            session.add(
                DataRecordRow(
                    project_id=project,
                    table_id=ref["tableId"],
                    dataset_generation=ref["datasetGeneration"],
                    key_type="text",
                    key_value="002",
                    values_json={ref["fieldId"]: "abc"},
                    record_slots=[],
                    status_id=None,
                    current_environment_id=None,
                    content_revision=1,
                    status_revision=1,
                    link_revision=1,
                    deleted=False,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
    with pytest.raises(ProjectError) as error:
        confirm(context, report)
    assert error.value.code == "PRECONDITION_FAILED" and error.value.status == 412


def test_expiry_and_change_binding(context):
    store, factory, project, _, ref, definition = context
    report = store.preview_field_update(project, ref, definition)
    with pytest.raises(ProjectError) as error:
        confirm(context, report, {**definition, "name": "Different"})
    assert error.value.status == 412
    with factory.begin() as session:
        session.get(DataImpactRow, report["impactRevision"]).expires_at = datetime.now(
            UTC
        ) - timedelta(seconds=1)
    with pytest.raises(ProjectError) as error:
        confirm(context, report)
    assert error.value.status == 412


def test_normalized_definition_matches_and_confirmation_does_not_consume(context):
    store, _, project, _, ref, definition = context
    report = store.preview_field_update(project, ref, {**definition, "name": " Email "})
    assert confirm(context, report) == report
    assert confirm(context, report) == report


def test_incompatible_values_are_reported_and_never_authorized(context):
    store, factory, project, _, ref, definition = context
    change = {**definition, "type": "number"}
    report = store.preview_field_update(project, ref, change)
    blocker = next(
        item
        for item in report["blockers"]
        if item["code"] == "FIELD_VALUES_INCOMPATIBLE"
    )
    assert blocker["resource"]["recordRef"]["recordKey"] == {
        "type": "text",
        "value": "001",
    }
    with pytest.raises(ProjectError) as error:
        confirm(context, report, change)
    assert error.value.status == 412
    with factory() as session:
        assert session.scalar(select(DataRecordRow)).values_json == {
            ref["fieldId"]: "abc"
        }


@pytest.mark.parametrize("guard", ["formula", "identity"])
def test_protected_field_changes_are_visible_blockers(context, guard):
    store, factory, project, _, ref, definition = context
    with factory.begin() as session:
        if guard == "formula":
            session.get(
                DataFieldRow, (ref["fieldId"], ref["datasetGeneration"])
            ).formula = True
        else:
            session.get(DataTableRow, ref["tableId"]).identity = {
                "mode": "field",
                "fieldId": ref["fieldId"],
            }
    report = store.preview_field_update(project, ref, {**definition, "type": "number"})
    assert any(
        item["code"]
        == ("FIELD_READ_ONLY" if guard == "formula" else "IDENTITY_FIELD_PROTECTED")
        for item in report["blockers"]
    )


def test_caller_rollback_keeps_business_data_and_confirmation(context):
    store, factory, project, _, ref, definition = context
    report = store.preview_field_update(project, ref, definition)
    with factory() as session:
        store.require_field_update(
            session, project, ref, definition, report["impactRevision"]
        )
        session.get(DataTableRow, ref["tableId"]).name = "rolled back"
        session.rollback()
    assert confirm(context, report) == report
    with factory() as session:
        assert session.get(DataTableRow, ref["tableId"]).name == "Data"


def test_preview_validation_does_not_hold_database_write_lock(context, monkeypatch):
    import autoflow.infrastructure.database.project_data_impacts as module

    store, factory, project, _, ref, definition = context
    original = module.validate_value
    changed = False

    def concurrent_write(definition, value):
        nonlocal changed
        if not changed:
            changed = True
            with factory.begin() as session:
                row = session.scalar(select(DataRecordRow))
                row.values_json = {ref["fieldId"]: "new"}
                row.content_revision += 1
        return original(definition, value)

    monkeypatch.setattr(module, "validate_value", concurrent_write)
    report = store.preview_field_update(project, ref, definition)
    assert changed
    with pytest.raises(ProjectError) as error:
        confirm(context, report)
    assert error.value.status == 412
