from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.deletions import DataDeletionService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.projects.service import ProjectService
from autoflow.domain.project_data.identity import RecordKey, encode_record_key
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_deletions import (
    SqlAlchemyProjectDataDeletions,
)
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataGenerationRow,
    DataImpactRow,
    DataRecordRow,
    DataStatusRow,
)
from autoflow.infrastructure.database.project_data_queries import (
    SqlAlchemyProjectDataQueries,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_run_models import ProjectRecordLeaseRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from tests.integration.test_project_run_data_start import _setup


def uid() -> str:
    return str(uuid4())


@pytest.fixture
def ctx(tmp_path):
    path = tmp_path / "delete.sqlite3"
    factory = create_session_factory(path)
    migrate_database(path)
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
    record_service = DataRecordService(SqlAlchemyProjectDataRecords(factory))
    deletion = DataDeletionService(SqlAlchemyProjectDataDeletions(factory))
    yield factory, project, table, catalog, field, record_service, deletion
    factory.dispose()


def create_record(ctx):
    _, project, table, _, field, records, _ = ctx
    record = records.create(
        project,
        table["tableId"],
        uid(),
        {
            "datasetGeneration": table["datasetGeneration"],
            "values": [{"fieldId": field["ref"]["fieldId"], "value": "one"}],
        },
    )[0]
    key = RecordKey(
        record["ref"]["recordKey"]["type"], record["ref"]["recordKey"]["value"]
    )
    return record, encode_record_key(key)


@pytest.mark.parametrize("lease_state", ["held", "reconciling", "released"])
@pytest.mark.parametrize("claim_before_preview", [True, False])
def test_record_delete_respects_lease_at_preview_and_commit(
    tmp_path, lease_state, claim_before_preview
):
    factory, project, automation, coordinator = _setup(tmp_path)
    try:
        batch = coordinator.start(
            project,
            automation.automation_id,
            uid(),
            {
                "expectedAutomationRevision": automation.management_revision,
                "parameters": {},
                "maxTasks": 1,
                "concurrency": 1,
            },
        )[0]
        source = automation.input_plan["inputs"][0]
        with factory() as session:
            row = session.scalar(
                select(DataRecordRow).where(DataRecordRow.table_id == source["tableId"])
            )
            pk = (row.dataset_generation, row.key_type, row.key_value)
            encoded = encode_record_key(RecordKey(row.key_type, row.key_value))
        ref = {
            "projectId": project,
            "tableId": source["tableId"],
            "datasetGeneration": source["datasetGeneration"],
            "recordKey": {"type": pk[1], "value": pk[2]},
        }

        def claim():
            assert (
                ProjectBatchScheduler.claim_data_task(factory, project, batch.batch_id)
                == "ready"
            )
            with factory.begin() as session:
                lease = session.scalar(
                    select(ProjectRecordLeaseRow).where(
                        ProjectRecordLeaseRow.record_ref == ref
                    )
                )
                assert lease is not None
                lease.state = lease_state
                if lease_state == "released":
                    lease.released_at = datetime.now(UTC)

        deletion = DataDeletionService(SqlAlchemyProjectDataDeletions(factory))
        if claim_before_preview:
            claim()
        preview = deletion.preview_record(
            project, source["tableId"], source["datasetGeneration"], encoded, pk[1]
        )
        active = lease_state in {"held", "reconciling"}
        assert [item["code"] for item in preview["blockers"]] == (
            ["RECORD_IN_USE"] if claim_before_preview and active else []
        )
        assert preview["impacts"][0]["blocking"] is (claim_before_preview and active)
        if not claim_before_preview:
            claim()
        payload = {
            "datasetGeneration": source["datasetGeneration"],
            "recordKeyType": pk[1],
            "expectedContentRevision": 1,
            "expectedStatusRevision": 1,
            "expectedLinkRevision": 1,
            "impactRevision": preview["impactRevision"],
        }
        with factory() as session:
            operations_before = session.scalar(
                select(func.count()).select_from(ProjectOperationRow)
            )
            changes_before = session.scalar(
                select(func.count()).select_from(DataChangeRow)
            )
        if active:
            with pytest.raises(ProjectError) as error:
                deletion.delete_record(
                    project, source["tableId"], encoded, uid(), payload
                )
            assert error.value.code == "PRECONDITION_FAILED"
            assert error.value.status == 412
            assert error.value.details["retryable"] is False
            blockers = error.value.details["blockers"]
            assert [item["code"] for item in blockers] == ["RECORD_IN_USE"]
            assert blockers[0]["resource"] == {"type": "record", "recordRef": ref}
            if claim_before_preview:
                assert blockers == preview["blockers"]
            with factory() as session:
                assert session.get(DataRecordRow, pk).deleted is False
                assert (
                    session.scalar(
                        select(func.count()).select_from(ProjectOperationRow)
                    )
                    == operations_before
                )
                assert (
                    session.scalar(select(func.count()).select_from(DataChangeRow))
                    == changes_before
                )
        else:
            result, _, replayed = deletion.delete_record(
                project, source["tableId"], encoded, uid(), payload
            )
            assert result["deleted"] is True and not replayed
            with factory() as session:
                assert session.get(DataRecordRow, pk).deleted is True
    finally:
        factory.dispose()


def test_record_delete_requires_fresh_impact_and_preserves_revisions(ctx):
    factory, project, table, _, _, records, deletion = ctx
    record, encoded = create_record(ctx)
    preview = deletion.preview_record(
        project, table["tableId"], table["datasetGeneration"], encoded, "uuid"
    )
    assert preview["blockers"] == []
    key = uid()
    payload = {
        "datasetGeneration": table["datasetGeneration"],
        "recordKeyType": "uuid",
        "expectedContentRevision": 1,
        "expectedStatusRevision": 1,
        "expectedLinkRevision": 1,
        "impactRevision": preview["impactRevision"],
    }
    result, operation, replayed = deletion.delete_record(
        project, table["tableId"], encoded, key, payload
    )
    assert not replayed and result["deleted"] is True
    with pytest.raises(ProjectError) as missing:
        records.get(
            project, table["tableId"], table["datasetGeneration"], encoded, "uuid"
        )
    assert missing.value.status == 404
    with factory() as session:
        row = session.get(
            DataRecordRow,
            (table["datasetGeneration"], "uuid", record["ref"]["recordKey"]["value"]),
        )
        assert row.deleted and (
            row.content_revision,
            row.status_revision,
            row.link_revision,
        ) == (1, 1, 1)
        change = session.scalar(
            select(DataChangeRow).where(
                DataChangeRow.operation_id == operation.operation_id
            )
        )
        assert change.before["deleted"] is False and change.after["deleted"] is True
    again, same, replay = deletion.delete_record(
        project, table["tableId"], encoded, key, payload
    )
    assert replay and again == result and same.operation_id == operation.operation_id


def test_status_delete_blocks_current_reference_then_tombstones_and_hides(ctx):
    factory, project, table, catalog, _, records, deletion = ctx
    status_result = catalog.create_status(
        project,
        table["tableId"],
        uid(),
        {"name": "Open", "color": "#AABBCC", "order": 0, "expectedTableRevision": 2},
    )[0]
    status = status_result["status"]
    _, encoded = create_record(ctx)
    records.set_status(
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
    )
    blocked = deletion.preview_status(project, table["tableId"], status["statusId"])
    assert blocked["blockers"][0]["code"] == "STATUS_IN_USE"
    with pytest.raises(ProjectError) as error:
        deletion.delete_status(
            project,
            table["tableId"],
            status["statusId"],
            uid(),
            {
                "expectedStatusRevision": 1,
                "expectedTableRevision": 3,
                "impactRevision": blocked["impactRevision"],
            },
        )
    assert error.value.status == 412
    records.set_status(
        project,
        table["tableId"],
        encoded,
        uid(),
        {
            "datasetGeneration": table["datasetGeneration"],
            "recordKeyType": "uuid",
            "statusId": None,
            "expectedStatusRevision": 2,
        },
    )
    fresh = deletion.preview_status(project, table["tableId"], status["statusId"])
    delete_key = uid()
    delete_payload = {
        "expectedStatusRevision": 1,
        "expectedTableRevision": 3,
        "impactRevision": fresh["impactRevision"],
    }
    result, deleted_operation, _ = deletion.delete_status(
        project,
        table["tableId"],
        status["statusId"],
        delete_key,
        delete_payload,
    )
    assert result == {
        "action": "delete",
        "statusId": status["statusId"],
        "deleted": True,
        "tableRevision": 4,
    }
    assert catalog.statuses(project, table["tableId"])["items"] == []
    with factory() as session:
        assert session.get(DataStatusRow, status["statusId"]).deleted

    replacement = catalog.create_status(
        project,
        table["tableId"],
        uid(),
        {
            "name": "open",
            "color": "#112233",
            "order": 1,
            "expectedTableRevision": 4,
        },
    )[0]["status"]
    assert replacement["statusId"] != status["statusId"]
    replayed_result, replayed_operation, replayed = deletion.delete_status(
        project,
        table["tableId"],
        status["statusId"],
        delete_key,
        delete_payload,
    )
    assert replayed and replayed_result == result
    assert replayed_operation.operation_id == deleted_operation.operation_id
    with pytest.raises(ProjectError) as tombstoned:
        catalog.update_status(
            project,
            table["tableId"],
            status["statusId"],
            uid(),
            {
                "name": "old",
                "expectedTableRevision": 5,
                "expectedStatusRevision": 2,
            },
        )
    assert tombstoned.value.status == 404
    with pytest.raises(ProjectError) as invalid_status:
        records.set_status(
            project,
            table["tableId"],
            encoded,
            uid(),
            {
                "datasetGeneration": table["datasetGeneration"],
                "recordKeyType": "uuid",
                "statusId": status["statusId"],
                "expectedStatusRevision": 3,
            },
        )
    assert invalid_status.value.status == 404
    with pytest.raises(ProjectError) as invalid_filter:
        SqlAlchemyProjectDataQueries(factory).query(
            project,
            table["tableId"],
            table["datasetGeneration"],
            {"type": "status", "operator": "eq", "statusId": status["statusId"]},
            [],
            1,
            50,
        )
    assert invalid_filter.value.status == 422


def test_preview_creates_impact_only_and_stale_facts_reject_atomically(ctx):
    factory, project, table, _, _, _, deletion = ctx
    record, encoded = create_record(ctx)
    preview = deletion.preview_record(
        project, table["tableId"], table["datasetGeneration"], encoded, "uuid"
    )
    with factory.begin() as session:
        row = session.get(
            DataRecordRow,
            (table["datasetGeneration"], "uuid", record["ref"]["recordKey"]["value"]),
        )
        row.current_environment_id = uid()
    with pytest.raises(ProjectError) as error:
        deletion.delete_record(
            project,
            table["tableId"],
            encoded,
            uid(),
            {
                "datasetGeneration": table["datasetGeneration"],
                "recordKeyType": "uuid",
                "expectedContentRevision": 1,
                "expectedStatusRevision": 1,
                "expectedLinkRevision": 1,
                "impactRevision": preview["impactRevision"],
            },
        )
    assert error.value.status == 412
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(DataImpactRow)) == 1
        assert (
            session.scalar(select(func.count()).select_from(ProjectOperationRow)) == 4
        )
        row = session.get(
            DataRecordRow,
            (table["datasetGeneration"], "uuid", record["ref"]["recordKey"]["value"]),
        )
        assert row.deleted is False


def test_record_delete_blocks_real_slot_targets_but_not_empty_slots(ctx):
    factory, project, table, _, _, _, deletion = ctx
    target, encoded = create_record(ctx)
    source, _ = create_record(ctx)
    source_pk = (
        table["datasetGeneration"],
        "uuid",
        source["ref"]["recordKey"]["value"],
    )
    with factory.begin() as session:
        source_row = session.get(DataRecordRow, source_pk)
        source_row.record_slots = [
            {"slotId": uid(), "target": None},
            {"slotId": uid(), "target": target["ref"]},
        ]
    report = deletion.preview_record(
        project, table["tableId"], table["datasetGeneration"], encoded, "uuid"
    )
    assert [item["code"] for item in report["blockers"]] == ["RECORD_REFERENCED"]


def test_unknown_record_slot_is_an_explicit_blocker(ctx):
    factory, project, table, _, _, _, deletion = ctx
    record, encoded = create_record(ctx)
    pk = (
        table["datasetGeneration"],
        "uuid",
        record["ref"]["recordKey"]["value"],
    )
    with factory.begin() as session:
        session.get(DataRecordRow, pk).record_slots = [
            {"slotId": uid(), "target": "opaque-external-binding"}
        ]
    report = deletion.preview_record(
        project, table["tableId"], table["datasetGeneration"], encoded, "uuid"
    )
    assert [item["code"] for item in report["blockers"]] == ["RECORD_SLOT_UNSUPPORTED"]
    with factory.begin() as session:
        session.get(DataRecordRow, pk).record_slots = [
            {
                "slotId": uid(),
                "target": {
                    "projectId": project,
                    "tableId": table["tableId"],
                    "datasetGeneration": table["datasetGeneration"],
                    "recordKey": {"type": [], "value": "x"},
                },
            }
        ]
    malformed = deletion.preview_record(
        project, table["tableId"], table["datasetGeneration"], encoded, "uuid"
    )
    assert [item["code"] for item in malformed["blockers"]] == [
        "RECORD_SLOT_UNSUPPORTED"
    ]


def test_impact_binds_project_lifecycle_and_management_revision(ctx):
    factory, project, table, _, _, _, deletion = ctx
    _, encoded = create_record(ctx)
    with factory.begin() as session:
        row = session.get(ProjectRow, project)
        row.lifecycle_state = "archived"
        row.management_revision += 1
    preview = deletion.preview_record(
        project, table["tableId"], table["datasetGeneration"], encoded, "uuid"
    )
    assert [item["code"] for item in preview["blockers"]] == ["PROJECT_READ_ONLY"]
    with factory.begin() as session:
        row = session.get(ProjectRow, project)
        row.lifecycle_state = "active"
        row.management_revision += 1
    payload = {
        "datasetGeneration": table["datasetGeneration"],
        "recordKeyType": "uuid",
        "expectedContentRevision": 1,
        "expectedStatusRevision": 1,
        "expectedLinkRevision": 1,
        "impactRevision": preview["impactRevision"],
    }
    with pytest.raises(ProjectError) as stale:
        deletion.delete_record(project, table["tableId"], encoded, uid(), payload)
    assert stale.value.status == 412


def test_record_delete_rolls_back_record_operation_and_change_on_failure(ctx):
    factory, project, table, _, _, _, deletion = ctx
    record, encoded = create_record(ctx)
    preview = deletion.preview_record(
        project, table["tableId"], table["datasetGeneration"], encoded, "uuid"
    )
    with factory() as session:
        operations_before = session.scalar(
            select(func.count()).select_from(ProjectOperationRow)
        )
    operation_key = uid()

    def fail_change(_mapper, _connection, _target):
        raise RuntimeError("injected failure")

    event.listen(DataChangeRow, "before_insert", fail_change)
    try:
        with pytest.raises(RuntimeError, match="injected failure"):
            deletion.delete_record(
                project,
                table["tableId"],
                encoded,
                operation_key,
                {
                    "datasetGeneration": table["datasetGeneration"],
                    "recordKeyType": "uuid",
                    "expectedContentRevision": 1,
                    "expectedStatusRevision": 1,
                    "expectedLinkRevision": 1,
                    "impactRevision": preview["impactRevision"],
                },
            )
    finally:
        event.remove(DataChangeRow, "before_insert", fail_change)
    with factory() as session:
        row = session.get(
            DataRecordRow,
            (
                table["datasetGeneration"],
                "uuid",
                record["ref"]["recordKey"]["value"],
            ),
        )
        assert row.deleted is False
        assert (
            session.scalar(select(func.count()).select_from(ProjectOperationRow))
            == operations_before
        )


def test_concurrent_same_record_delete_commits_once_and_replays(ctx):
    _, project, table, _, _, _, deletion = ctx
    _, encoded = create_record(ctx)
    preview = deletion.preview_record(
        project, table["tableId"], table["datasetGeneration"], encoded, "uuid"
    )
    operation_key = uid()
    payload = {
        "datasetGeneration": table["datasetGeneration"],
        "recordKeyType": "uuid",
        "expectedContentRevision": 1,
        "expectedStatusRevision": 1,
        "expectedLinkRevision": 1,
        "impactRevision": preview["impactRevision"],
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                deletion.delete_record,
                project,
                table["tableId"],
                encoded,
                operation_key,
                payload,
            )
            for _ in range(2)
        ]
    results = [future.result() for future in futures]
    assert sorted(result[2] for result in results) == [False, True]
    assert results[0][0] == results[1][0]
    assert results[0][1].operation_id == results[1][1].operation_id


def test_same_key_different_record_target_is_payload_conflict(ctx):
    _, project, table, _, _, _, deletion = ctx
    _, first = create_record(ctx)
    _, second = create_record(ctx)
    preview = deletion.preview_record(
        project, table["tableId"], table["datasetGeneration"], first, "uuid"
    )
    operation_key = uid()
    payload = {
        "datasetGeneration": table["datasetGeneration"],
        "recordKeyType": "uuid",
        "expectedContentRevision": 1,
        "expectedStatusRevision": 1,
        "expectedLinkRevision": 1,
        "impactRevision": preview["impactRevision"],
    }
    deletion.delete_record(project, table["tableId"], first, operation_key, payload)
    with pytest.raises(ProjectError) as mismatch:
        deletion.delete_record(
            project, table["tableId"], second, operation_key, payload
        )
    assert mismatch.value.code == "OPERATION_PAYLOAD_MISMATCH"


def test_expired_impact_and_readonly_lifecycle_reject_without_mutation(ctx):
    factory, project, table, _, _, _, deletion = ctx
    record, encoded = create_record(ctx)
    preview = deletion.preview_record(
        project, table["tableId"], table["datasetGeneration"], encoded, "uuid"
    )
    with factory.begin() as session:
        impact = session.get(DataImpactRow, preview["impactRevision"])
        impact.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    payload = {
        "datasetGeneration": table["datasetGeneration"],
        "recordKeyType": "uuid",
        "expectedContentRevision": 1,
        "expectedStatusRevision": 1,
        "expectedLinkRevision": 1,
        "impactRevision": preview["impactRevision"],
    }
    with pytest.raises(ProjectError) as expired:
        deletion.delete_record(project, table["tableId"], encoded, uid(), payload)
    assert expired.value.status == 412
    fresh = deletion.preview_record(
        project, table["tableId"], table["datasetGeneration"], encoded, "uuid"
    )
    payload["impactRevision"] = fresh["impactRevision"]
    with factory.begin() as session:
        session.get(ProjectRow, project).lifecycle_state = "archived"
    with pytest.raises(ProjectError) as readonly:
        deletion.delete_record(project, table["tableId"], encoded, uid(), payload)
    assert readonly.value.status == 409
    with factory() as session:
        row = session.get(
            DataRecordRow,
            (
                table["datasetGeneration"],
                "uuid",
                record["ref"]["recordKey"]["value"],
            ),
        )
        assert row.deleted is False


def test_scope_old_generation_and_new_status_reference_are_rechecked(ctx):
    factory, project, table, catalog, _, records, deletion = ctx
    other_project = (
        ProjectService(SqlAlchemyProjects(factory))
        .create(uid(), {"name": "other"})[0]
        .project_id
    )
    status = catalog.create_status(
        project,
        table["tableId"],
        uid(),
        {
            "name": "Open",
            "color": "#abcdef",
            "order": 0,
            "expectedTableRevision": 2,
        },
    )[0]["status"]
    with pytest.raises(ProjectError) as scoped:
        deletion.preview_status(other_project, table["tableId"], status["statusId"])
    assert scoped.value.status == 404
    with pytest.raises(ProjectError) as gone:
        deletion.preview_record(project, table["tableId"], uid(), "MQ", "integer")
    assert gone.value.status == 410
    preview = deletion.preview_status(project, table["tableId"], status["statusId"])
    _, encoded = create_record(ctx)
    records.set_status(
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
    )
    with pytest.raises(ProjectError) as changed:
        deletion.delete_status(
            project,
            table["tableId"],
            status["statusId"],
            uid(),
            {
                "expectedStatusRevision": 1,
                "expectedTableRevision": 3,
                "impactRevision": preview["impactRevision"],
            },
        )
    assert changed.value.status == 412


def test_old_generation_and_deleted_record_references_do_not_block_status(ctx):
    factory, project, table, catalog, _, _, deletion = ctx
    status = catalog.create_status(
        project,
        table["tableId"],
        uid(),
        {
            "name": "Historical",
            "color": "#123456",
            "order": 0,
            "expectedTableRevision": 2,
        },
    )[0]["status"]
    old_generation = uid()
    now = datetime.now(UTC)
    with factory.begin() as session:
        session.add(
            DataGenerationRow(
                id=old_generation,
                project_id=project,
                table_id=table["tableId"],
                identity={"mode": "system"},
                source={"kind": "local"},
                created_at=now,
            )
        )
        for generation, key, deleted in (
            (old_generation, "old", False),
            (table["datasetGeneration"], "deleted", True),
        ):
            session.add(
                DataRecordRow(
                    project_id=project,
                    table_id=table["tableId"],
                    dataset_generation=generation,
                    key_type="text",
                    key_value=key,
                    values_json={},
                    record_slots=[],
                    status_id=status["statusId"],
                    current_environment_id=None,
                    content_revision=1,
                    status_revision=1,
                    link_revision=1,
                    deleted=deleted,
                    created_at=now,
                    updated_at=now,
                )
            )
    preview = deletion.preview_status(project, table["tableId"], status["statusId"])
    assert preview["blockers"] == []
    deletion.delete_status(
        project,
        table["tableId"],
        status["statusId"],
        uid(),
        {
            "expectedStatusRevision": 1,
            "expectedTableRevision": 3,
            "impactRevision": preview["impactRevision"],
        },
    )
    with factory() as session:
        historic = session.get(DataRecordRow, (old_generation, "text", "old"))
        assert historic.status_id == status["statusId"] and not historic.deleted
