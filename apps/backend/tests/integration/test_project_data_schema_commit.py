from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, select

from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataFieldRow,
    DataImpactRow,
    DataRecordRow,
    DataTableRow,
)

from .test_project_data_schema_preview import add_field, candidate, preview, uid
from .test_project_data_schema_preview import (
    ctx as ctx,  # noqa: PLC0414 -- pytest fixture export
)


def commit(ctx, draft, report, key=None):
    return ctx[0].commit(
        ctx[2],
        ctx[3]["tableId"],
        key or uid(),
        {"candidate": draft, "impactRevision": report["impactRevision"]},
    )


def test_atomic_backfill_and_frozen_replay(ctx):
    draft = candidate(ctx)
    draft["fields"][0]["definition"]["name"] = "Changed"
    entry = add_field(draft, existingRecordDefault=False)
    report = preview(ctx, draft)
    key = uid()
    result, operation, replayed = commit(ctx, draft, report, key)
    assert (
        not replayed
        and result["tableRevision"] == 4
        and result["backfilledRecords"] == 2
    )
    field_id = result["createdFieldIds"][entry["clientId"]]
    with ctx[1]() as session:
        for row in session.scalars(select(DataRecordRow)):
            assert row.values_json[field_id] is False
            assert (row.content_revision, row.status_revision, row.link_revision) == (
                2,
                1,
                1,
            )
        assert (
            len(
                session.scalars(
                    select(DataChangeRow).where(
                        DataChangeRow.operation_id == operation.operation_id
                    )
                ).all()
            )
            == 4
        )
        table = session.scalar(select(DataTableRow))
        table.table_revision += 1
        session.commit()
    assert commit(ctx, draft, report, key) == (result, operation, True)
    altered = deepcopy(draft)
    altered["fields"][0]["definition"]["name"] = "Another"
    with pytest.raises(ProjectError) as caught:
        commit(ctx, altered, report, key)
    assert caught.value.code == "OPERATION_PAYLOAD_MISMATCH"


def test_noop_keeps_revisions_and_writes_operation(ctx):
    draft = candidate(ctx)
    result, op, _ = commit(ctx, draft, preview(ctx, draft))
    assert result["tableRevision"] == 3 and result["backfilledRecords"] == 0
    with ctx[1]() as session:
        assert session.get(ProjectOperationRow, op.operation_id)
        assert not session.scalars(
            select(DataChangeRow).where(DataChangeRow.operation_id == op.operation_id)
        ).all()


@pytest.mark.parametrize("mutation", ["content", "status", "delete", "table"])
def test_stale_preview_never_writes_operation(ctx, mutation):
    draft = candidate(ctx)
    add_field(draft, existingRecordDefault=False)
    report = preview(ctx, draft)
    with ctx[1]() as session:
        if mutation == "table":
            session.scalar(select(DataTableRow)).table_revision += 1
        else:
            row = session.scalar(select(DataRecordRow))
            if mutation == "content":
                row.content_revision += 1
            if mutation == "status":
                row.status_revision += 1
            if mutation == "delete":
                row.deleted = True
        session.commit()
    key = uid()
    with pytest.raises(ProjectError):
        commit(ctx, draft, report, key)
    with ctx[1]() as session:
        assert (
            session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == key
                )
            )
            is None
        )
        assert len(session.scalars(select(DataFieldRow)).all()) == 2


@pytest.mark.parametrize(
    "model,event_name",
    [
        (DataFieldRow, "before_insert"),
        (DataRecordRow, "before_update"),
        (ProjectOperationRow, "before_insert"),
        (DataChangeRow, "before_insert"),
    ],
)
def test_failure_rolls_back_fields_records_guard_operation(ctx, model, event_name):
    draft = candidate(ctx)
    add_field(draft, existingRecordDefault=False)
    report = preview(ctx, draft)
    with ctx[1]() as session:
        before_guard = session.scalar(select(DataTableRow)).schema_guard_revision

    def fail(*args):
        raise RuntimeError("injected change failure")

    event.listen(model, event_name, fail)
    try:
        with pytest.raises(RuntimeError):
            commit(ctx, draft, report)
    finally:
        event.remove(model, event_name, fail)
    with ctx[1]() as session:
        assert (
            session.scalar(select(DataTableRow)).schema_guard_revision == before_guard
        )
        assert len(session.scalars(select(DataFieldRow)).all()) == 2
        assert all(
            row.content_revision == 1 for row in session.scalars(select(DataRecordRow))
        )


@pytest.mark.parametrize(
    "mutation", ["expired", "action", "target", "candidate", "blocker"]
)
def test_preview_evidence_binding(ctx, mutation):
    draft = candidate(ctx)
    add_field(draft, existingRecordDefault=False)
    report = preview(ctx, draft)
    with ctx[1]() as session:
        saved = session.get(DataImpactRow, report["impactRevision"])
        if mutation == "expired":
            saved.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        if mutation == "action":
            saved.action = "updateField"
        if mutation == "target":
            saved.target = {**saved.target, "tableId": uid()}
        if mutation == "blocker":
            saved.report = {
                **saved.report,
                "public": {**saved.report["public"], "blockers": [{"code": "blocked"}]},
            }
        if mutation == "candidate":
            draft["fields"][-1]["existingRecordDefault"] = True
        session.commit()
    with pytest.raises(ProjectError) as caught:
        commit(ctx, draft, report)
    assert caught.value.code == "IMPACT_STALE"


def test_concurrent_candidates_have_one_winner(ctx):
    draft = candidate(ctx)
    add_field(draft, existingRecordDefault=False)
    reports = [preview(ctx, draft), preview(ctx, draft)]

    def attempt(report):
        try:
            return commit(ctx, draft, report)[0]
        except ProjectError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, reports))
    assert sum(isinstance(result, dict) for result in outcomes) == 1
    assert sum(isinstance(result, ProjectError) for result in outcomes) == 1


def test_recovery_after_restart_uses_same_key_and_archived_project(ctx):
    from autoflow.application.project_data.schema import DataSchemaService
    from autoflow.application.projects.service import ProjectService
    from autoflow.infrastructure.database.project_data_schema import (
        SqlAlchemyProjectDataSchema,
    )
    from autoflow.infrastructure.database.projects import SqlAlchemyProjects

    draft = candidate(ctx)
    entry = add_field(draft, existingRecordDefault=False)
    report, key = preview(ctx, draft), uid()
    result, operation, _ = commit(ctx, draft, report, key)
    with ctx[1]() as session:
        session.get(ProjectRow, ctx[2]).lifecycle_state = "archived"
        session.commit()
    fresh = DataSchemaService(SqlAlchemyProjectDataSchema(ctx[1]))
    replay = fresh.commit(
        ctx[2],
        ctx[3]["tableId"],
        key,
        {"candidate": draft, "impactRevision": report["impactRevision"]},
    )
    assert replay == (result, operation, True)
    assert (
        replay[0]["createdFieldIds"][entry["clientId"]]
        == result["createdFieldIds"][entry["clientId"]]
    )
    recovered = ProjectService(SqlAlchemyProjects(ctx[1])).operation(
        key=key, project_id=ctx[2]
    )
    assert recovered.result == result


def test_cross_project_preview_and_operation_cannot_be_reused(ctx):
    from autoflow.application.projects.service import ProjectService
    from autoflow.infrastructure.database.projects import SqlAlchemyProjects

    projects = ProjectService(SqlAlchemyProjects(ctx[1]))
    other = projects.create(uid(), {"name": "other"})[0].project_id
    draft = candidate(ctx)
    report, key = preview(ctx, draft), uid()
    commit(ctx, draft, report, key)
    with pytest.raises(ProjectError):
        ctx[0].preview(other, ctx[3]["tableId"], draft)
    with pytest.raises(ProjectError):
        ctx[0].commit(
            other,
            ctx[3]["tableId"],
            key,
            {"candidate": draft, "impactRevision": report["impactRevision"]},
        )
    with pytest.raises(ProjectError):
        projects.operation(key=key, project_id=other)


@pytest.mark.parametrize("aggregate_first", [False, True])
def test_old_single_field_and_aggregate_cas_interoperate(ctx, aggregate_first):
    from autoflow.application.project_data.catalog import DataCatalogService
    from autoflow.infrastructure.database.project_data_catalog import (
        SqlAlchemyProjectDataCatalog,
    )

    catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(ctx[1]))
    field = ctx[4][0]
    definition = {
        key: field[key] for key in ("key", "name", "type", "required", "validation")
    }
    definition["name"] = "Single"
    old_report = catalog.preview_field_update(ctx[2], field["ref"], definition)
    draft = candidate(ctx)
    draft["fields"][0]["definition"]["name"] = "Aggregate"
    report = preview(ctx, draft)

    def single():
        return catalog.update_field(
            ctx[2],
            ctx[3]["tableId"],
            field["ref"]["fieldId"],
            uid(),
            {
                "definition": definition,
                "expectedTableRevision": 3,
                "expectedFieldRevision": 1,
                "impactRevision": old_report["impactRevision"],
            },
        )

    if aggregate_first:
        commit(ctx, draft, report)
        with pytest.raises(ProjectError):
            single()
    else:
        single()
        with pytest.raises(ProjectError):
            commit(ctx, draft, report)


def test_generation_replacement_rejects_old_preview(ctx):
    from autoflow.infrastructure.database.project_data_models import DataGenerationRow

    draft = candidate(ctx)
    report = preview(ctx, draft)
    replacement = uid()
    with ctx[1]() as session:
        session.add(
            DataGenerationRow(
                id=replacement,
                project_id=ctx[2],
                table_id=ctx[3]["tableId"],
                identity={"mode": "system"},
                source={"kind": "local"},
                created_at=datetime.now(UTC),
            )
        )
        table = session.get(DataTableRow, ctx[3]["tableId"])
        table.current_generation = replacement
        table.table_revision += 1
        session.commit()
    with pytest.raises(ProjectError) as caught:
        commit(ctx, draft, report)
    assert caught.value.code == "DATASET_GENERATION_GONE"


def test_backfill_preserves_typed_keys_slots_status_environment_and_invalid_values(ctx):
    from autoflow.application.project_data.catalog import DataCatalogService
    from autoflow.infrastructure.database.project_data_catalog import (
        SqlAlchemyProjectDataCatalog,
    )

    catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(ctx[1]))
    status = catalog.create_status(
        ctx[2],
        ctx[3]["tableId"],
        uid(),
        {"name": "Active", "color": "#336699", "order": 0, "expectedTableRevision": 3},
    )[0]["status"]
    with ctx[1]() as session:
        for index, row in enumerate(session.scalars(select(DataRecordRow))):
            row.key_type, row.key_value = (
                ("text", "001") if not index else ("integer", "1")
            )
            row.record_slots = [{"key": "retained", "value": "original"}]
            row.current_environment_id = "existing-environment"
            row.status_id = status["statusId"]
            row.values_json = {**row.values_json, ctx[4][1]["ref"]["fieldId"]: 42}
        session.commit()
    draft = candidate(ctx)
    draft["expectedTableRevision"] = 4
    add_field(draft, existingRecordDefault=False)
    report = preview(ctx, draft)
    assert not report["blockers"] and not report["warnings"]
    commit(ctx, draft, report)
    with ctx[1]() as session:
        rows = session.scalars(select(DataRecordRow)).all()
        assert {(row.key_type, row.key_value) for row in rows} == {
            ("text", "001"),
            ("integer", "1"),
        }
        for row in rows:
            assert row.record_slots == [{"key": "retained", "value": "original"}]
            assert row.current_environment_id == "existing-environment"
            assert row.status_id == status["statusId"]
            assert row.values_json[ctx[4][1]["ref"]["fieldId"]] == 42


def test_changed_second_field_invalid_rejects_entire_candidate(ctx):
    draft = candidate(ctx)
    draft["fields"][0]["definition"]["name"] = "Must not persist"
    draft["fields"][1]["definition"]["required"] = True
    report = preview(ctx, draft)
    assert report["blockers"]
    with pytest.raises(ProjectError):
        commit(ctx, draft, report)
    with ctx[1]() as session:
        assert (
            session.get(
                DataFieldRow, (ctx[4][0]["ref"]["fieldId"], ctx[3]["datasetGeneration"])
            ).name
            == "name"
        )


def test_multiple_new_fields_backfill_each_record_only_once(ctx):
    draft = candidate(ctx)
    add_field(draft, existingRecordDefault=False)
    second = add_field(draft, existingRecordDefault=None)
    second["definition"]["key"] = "second"
    result, _, _ = commit(ctx, draft, preview(ctx, draft))
    assert result["backfilledRecords"] == 2
    with ctx[1]() as session:
        assert all(
            row.content_revision == 2 for row in session.scalars(select(DataRecordRow))
        )


def test_schema_on_real_excel_import_preserves_source_file_and_identity(tmp_path):
    import hashlib

    from fastapi.testclient import TestClient

    from autoflow.application.project_data.catalog import DataCatalogService
    from autoflow.application.project_data.schema import DataSchemaService
    from autoflow.infrastructure.database.project_data_catalog import (
        SqlAlchemyProjectDataCatalog,
    )
    from autoflow.infrastructure.database.project_data_schema import (
        SqlAlchemyProjectDataSchema,
    )
    from tests.contract.test_pm2_excel_imports import inspected, request_for
    from tests.contract.test_settings_dashboard import _app

    app = _app(tmp_path)
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        project, proof, inspection = inspected(client, tmp_path)
        key = uid()
        response = client.post(
            f"/api/v1/projects/{project}/table-imports/excel",
            json=request_for(inspection),
            headers={**proof, "Idempotency-Key": key},
        )
        assert response.status_code == 202, response.text
        operation = client.get(
            f"/api/v1/projects/{project}/operations/by-idempotency-key/{key}"
        ).json()
        assert operation["status"] == "succeeded", operation
        table = operation["result"]["table"]
        path = tmp_path / "source.xlsx"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        factory = app.state.session_factory
        catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(factory))
        fields = catalog.fields(project, table["tableId"])["items"]
        context = (
            DataSchemaService(SqlAlchemyProjectDataSchema(factory)),
            factory,
            project,
            table,
            fields,
        )
        draft = candidate(context)
        draft["expectedTableRevision"] = table["tableRevision"]
        draft["fields"][0]["definition"]["name"] = "编号显示名"
        add_field(draft, existingRecordDefault=False)
        result, _, _ = commit(context, draft, preview(context, draft))
        assert result["backfilledRecords"] == 1
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        with factory() as session:
            record = session.scalar(select(DataRecordRow))
            assert (record.key_type, record.key_value) == ("text", "001")
        current = client.get(
            f"/api/v1/projects/{project}/tables/{table['tableId']}"
        ).json()
        assert (
            current["source"] == table["source"]
            and current["identity"] == table["identity"]
        )
