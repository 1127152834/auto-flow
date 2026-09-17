import base64
import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, inspect, select, text

from autoflow.application.project_data.capabilities import ProjectDataCapabilityService
from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.tables import DataTableService
from autoflow.domain.project_data.capabilities import (
    QueryProjectRecordsRequest,
    TableCapabilityGrant,
    TaskCapabilityScope,
)
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_capabilities import (
    SqlAlchemyProjectDataCapabilities,
)
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_run_models import ProjectTaskRecordReadRow
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.integration.test_project_capability_field_impacts import _activate_task
from tests.integration.test_project_run_data_start import _setup, uid


def _context(tmp_path):
    factory, project_id, automation, _coordinator = _setup(tmp_path)
    table = DataTableService(SqlAlchemyProjectData(factory)).create(
        project_id, uid(), {"name": "查询快照"}
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
    records = DataRecordService(SqlAlchemyProjectDataRecords(factory))
    created = [
        records.create(
            project_id,
            table["tableId"],
            uid(),
            {
                "datasetGeneration": table["datasetGeneration"],
                "values": [{"fieldId": field["ref"]["fieldId"], "value": value}],
            },
        )[0]
        for value in ("A", "B", "C", "D")
    ]
    grant = {
        "tableId": table["tableId"],
        "datasetGeneration": table["datasetGeneration"],
        "operations": ["queryRecords"],
        "fieldIds": [field["ref"]["fieldId"]],
        "readPurposes": ["workflow"],
    }
    task = _activate_task(factory, project_id, automation, [grant])
    _run(factory, task.run_id, 1)
    scope = _scope(project_id, task.id, task.run_id, table, field, 1)
    service = ProjectDataCapabilityService(SqlAlchemyProjectDataCapabilities(factory))
    return (
        factory,
        project_id,
        automation,
        grant,
        table,
        field,
        created,
        task,
        scope,
        service,
    )


def _run(factory, run_id: str, generation: int) -> None:
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, run_id)
        assert run is not None
        run.execution_generation = generation
        run.status = "running"
        run.status_revision += 1


def _scope(project_id, task_id, run_id, table, field, generation):
    return TaskCapabilityScope(
        project_id,
        task_id,
        run_id,
        generation,
        frozenset(),
        frozenset(),
        table_grants=frozenset(
            {
                TableCapabilityGrant(
                    table["tableId"],
                    table["datasetGeneration"],
                    frozenset({"queryRecords"}),
                    frozenset({field["ref"]["fieldId"]}),
                    frozenset({"workflow"}),
                )
            }
        ),
    )


def _query(
    project_id,
    table,
    field,
    *,
    cursor=None,
    generation=1,
    limit=2,
    filter_value=None,
    order_by=None,
):
    return QueryProjectRecordsRequest(
        generation,
        project_id,
        table["tableId"],
        table["datasetGeneration"],
        [field["ref"]["fieldId"]],
        "workflow",
        filter_value,
        order_by
        if order_by is not None
        else [{"fieldId": field["ref"]["fieldId"], "direction": "asc"}],
        cursor,
        limit,
    )


def _values(page: dict) -> list[str]:
    return [item["values"][0]["value"] for item in page["items"]]


def _evidence_counts(factory, task_id: str) -> tuple[int, int]:
    with factory() as session:
        queries = session.scalar(
            text(
                "SELECT count(*) FROM project_task_record_queries WHERE task_id = :task_id"
            ),
            {"task_id": task_id},
        )
        reads = session.scalar(
            select(func.count())
            .select_from(ProjectTaskRecordReadRow)
            .where(ProjectTaskRecordReadRow.task_id == task_id)
        )
    return int(queries or 0), int(reads or 0)


def test_query_cursor_reads_the_frozen_result_after_live_rows_change(tmp_path):
    (
        factory,
        project_id,
        _automation,
        _grant,
        table,
        field,
        created,
        _task,
        scope,
        service,
    ) = _context(tmp_path)
    try:
        first = service.query_records(scope, _query(project_id, table, field))
        assert _values(first) == ["A", "B"]
        assert first["nextCursor"]

        DataRecordService(SqlAlchemyProjectDataRecords(factory)).create(
            project_id,
            table["tableId"],
            uid(),
            {
                "datasetGeneration": table["datasetGeneration"],
                "values": [{"fieldId": field["ref"]["fieldId"], "value": "AA"}],
            },
        )
        by_value = {item["values"][0]["value"]: item for item in created}
        with factory.begin() as session:
            deleted = session.scalar(
                select(DataRecordRow).where(
                    DataRecordRow.dataset_generation == table["datasetGeneration"],
                    DataRecordRow.key_type == by_value["C"]["ref"]["recordKey"]["type"],
                    DataRecordRow.key_value
                    == by_value["C"]["ref"]["recordKey"]["value"],
                )
            )
            reordered = session.scalar(
                select(DataRecordRow).where(
                    DataRecordRow.dataset_generation == table["datasetGeneration"],
                    DataRecordRow.key_type == by_value["D"]["ref"]["recordKey"]["type"],
                    DataRecordRow.key_value
                    == by_value["D"]["ref"]["recordKey"]["value"],
                )
            )
            assert deleted is not None and reordered is not None
            deleted.deleted = True
            reordered.values_json = {field["ref"]["fieldId"]: "0"}
            reordered.content_revision += 1

        second = service.query_records(
            scope,
            _query(project_id, table, field, cursor=first["nextCursor"]),
        )

        assert _values(second) == ["C", "D"]
        assert second["nextCursor"] is None
        assert second["hasMore"] is False
        with factory() as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(ProjectTaskRecordReadRow)
                    .where(ProjectTaskRecordReadRow.task_id == scope.task_id)
                )
                == 4
            )
    finally:
        factory.dispose()


def test_empty_query_persists_query_evidence_without_record_read_evidence(tmp_path):
    (
        factory,
        project_id,
        _automation,
        _grant,
        table,
        field,
        _created,
        task,
        scope,
        service,
    ) = _context(tmp_path)
    try:
        page = service.query_records(
            scope,
            _query(
                project_id,
                table,
                field,
                filter_value={
                    "type": "compare",
                    "fieldId": field["ref"]["fieldId"],
                    "operator": "eq",
                    "value": "不存在",
                },
            ),
        )
        assert page == {"items": [], "nextCursor": None, "hasMore": False}
        engine = factory.kw["bind"]
        assert inspect(engine).has_table("project_task_record_queries")
        with factory() as session:
            evidence = (
                session.execute(
                    text(
                        "SELECT task_id, run_id, execution_generation, result_count "
                        "FROM project_task_record_queries"
                    )
                )
                .mappings()
                .one()
            )
            assert dict(evidence) == {
                "task_id": task.id,
                "run_id": task.run_id,
                "execution_generation": 1,
                "result_count": 0,
            }
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(ProjectTaskRecordReadRow)
                    .where(ProjectTaskRecordReadRow.task_id == task.id)
                )
                == 0
            )
    finally:
        factory.dispose()


def test_query_cursor_cannot_cross_task_boundary(tmp_path):
    (
        factory,
        project_id,
        automation,
        grant,
        table,
        field,
        _created,
        _task,
        scope,
        service,
    ) = _context(tmp_path)
    try:
        first = service.query_records(scope, _query(project_id, table, field))
        assert first["nextCursor"]
        second_task = _activate_task(factory, project_id, automation, [grant])
        _run(factory, second_task.run_id, 1)
        second_scope = _scope(
            project_id, second_task.id, second_task.run_id, table, field, 1
        )

        with pytest.raises(ProjectError) as invalid:
            service.query_records(
                second_scope,
                _query(project_id, table, field, cursor=first["nextCursor"]),
            )
        assert invalid.value.code == "QUERY_CURSOR_INVALID"
    finally:
        factory.dispose()


def test_query_cursor_cannot_cross_execution_generation(tmp_path):
    (
        factory,
        project_id,
        _automation,
        _grant,
        table,
        field,
        _created,
        task,
        scope,
        service,
    ) = _context(tmp_path)
    try:
        first = service.query_records(scope, _query(project_id, table, field))
        assert first["nextCursor"]
        _run(factory, task.run_id, 2)
        current_scope = _scope(project_id, task.id, task.run_id, table, field, 2)

        with pytest.raises(ProjectError) as invalid:
            service.query_records(
                current_scope,
                _query(
                    project_id,
                    table,
                    field,
                    cursor=first["nextCursor"],
                    generation=2,
                ),
            )
        assert invalid.value.code == "QUERY_CURSOR_INVALID"
    finally:
        factory.dispose()


@pytest.mark.parametrize("reference", ["filter", "order"])
def test_query_rejects_ungranted_filter_and_order_fields_without_evidence(
    tmp_path, reference
):
    (
        factory,
        project_id,
        _automation,
        _grant,
        table,
        field,
        _created,
        task,
        scope,
        service,
    ) = _context(tmp_path)
    try:
        hidden = DataCatalogService(SqlAlchemyProjectDataCatalog(factory)).create_field(
            project_id,
            table["tableId"],
            uid(),
            {
                "definition": {
                    "key": "hidden",
                    "name": "未授权字段",
                    "type": "string",
                    "required": False,
                    "validation": {},
                },
                "expectedTableRevision": 2,
                "sourceColumnPolicy": "localOnly",
            },
        )[0]["field"]
        query = _query(
            project_id,
            table,
            field,
            filter_value=(
                {
                    "type": "compare",
                    "fieldId": hidden["ref"]["fieldId"],
                    "operator": "eq",
                    "value": "secret",
                }
                if reference == "filter"
                else None
            ),
            order_by=(
                [
                    {
                        "fieldId": hidden["ref"]["fieldId"],
                        "direction": "asc",
                    }
                ]
                if reference == "order"
                else []
            ),
        )

        with pytest.raises(ProjectError) as denied:
            service.query_records(scope, query)

        assert denied.value.code == "CAPABILITY_SCOPE_DENIED"
        assert _evidence_counts(factory, task.id) == (0, 0)
    finally:
        factory.dispose()


def test_query_cursor_rejects_offset_past_frozen_result(tmp_path):
    (
        factory,
        project_id,
        _automation,
        _grant,
        table,
        field,
        _created,
        task,
        scope,
        service,
    ) = _context(tmp_path)
    try:
        first = service.query_records(scope, _query(project_id, table, field))
        cursor = first["nextCursor"]
        assert cursor
        decoded = json.loads(
            base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        )
        decoded["offset"] = 5
        invalid_cursor = (
            base64.urlsafe_b64encode(
                json.dumps(decoded, separators=(",", ":"), sort_keys=True).encode()
            )
            .decode()
            .rstrip("=")
        )

        with pytest.raises(ProjectError) as invalid:
            service.query_records(
                scope,
                _query(project_id, table, field, cursor=invalid_cursor),
            )

        assert invalid.value.code == "QUERY_CURSOR_INVALID"
        assert _evidence_counts(factory, task.id) == (1, 2)
    finally:
        factory.dispose()


def test_query_rejects_tables_above_scan_budget_without_partial_evidence(tmp_path):
    (
        factory,
        project_id,
        _automation,
        _grant,
        table,
        field,
        _created,
        task,
        scope,
        service,
    ) = _context(tmp_path)
    now = datetime.now(UTC)
    try:
        with factory.begin() as session:
            session.add_all(
                DataRecordRow(
                    project_id=project_id,
                    table_id=table["tableId"],
                    dataset_generation=table["datasetGeneration"],
                    key_type="text",
                    key_value=f"bulk-{index:05d}",
                    values_json={field["ref"]["fieldId"]: "value"},
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
                for index in range(9_997)
            )

        with pytest.raises(ProjectError) as limited:
            service.query_records(scope, _query(project_id, table, field))

        assert limited.value.code == "QUERY_SNAPSHOT_BUDGET_EXCEEDED"
        assert limited.value.details["reason"] == "recordCount"
        assert _evidence_counts(factory, task.id) == (0, 0)
    finally:
        factory.dispose()


def test_query_rejects_snapshot_bytes_above_budget_without_partial_evidence(tmp_path):
    (
        factory,
        project_id,
        _automation,
        _grant,
        table,
        field,
        created,
        task,
        scope,
        service,
    ) = _context(tmp_path)
    first_ref = created[0]["ref"]["recordKey"]
    try:
        with factory.begin() as session:
            row = session.scalar(
                select(DataRecordRow).where(
                    DataRecordRow.dataset_generation == table["datasetGeneration"],
                    DataRecordRow.key_type == first_ref["type"],
                    DataRecordRow.key_value == first_ref["value"],
                )
            )
            assert row is not None
            row.values_json = {
                field["ref"]["fieldId"]: "界" * (4 * 1024 * 1024 // 3 + 1)
            }

        with pytest.raises(ProjectError) as limited:
            service.query_records(scope, _query(project_id, table, field))

        assert limited.value.code == "QUERY_SNAPSHOT_BUDGET_EXCEEDED"
        assert limited.value.details["reason"] == "snapshotBytes"
        assert _evidence_counts(factory, task.id) == (0, 0)
    finally:
        factory.dispose()
