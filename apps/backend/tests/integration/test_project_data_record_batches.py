from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
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
def batch(tmp_path):
    path = tmp_path / "batch.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project = (
        ProjectService(SqlAlchemyProjects(factory))
        .create(uid(), {"name": "grid"})[0]
        .project_id
    )
    table = DataTableService(SqlAlchemyProjectData(factory)).create(
        project, uid(), {"name": "t"}
    )[0]
    field = DataCatalogService(SqlAlchemyProjectDataCatalog(factory)).create_field(
        project,
        table["tableId"],
        uid(),
        {
            "definition": {
                "key": "title",
                "name": "标题",
                "type": "string",
                "required": True,
                "validation": {},
            },
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]["ref"]["fieldId"]
    payload = {
        "datasetGeneration": table["datasetGeneration"],
        "expectedTableRevision": 2,
        "rows": [
            {"clientRowId": uid(), "values": [{"fieldId": field, "value": value}]}
            for value in ["001", "1"]
        ],
    }
    yield (
        DataRecordService(SqlAlchemyProjectDataRecords(factory)),
        factory,
        project,
        table["tableId"],
        payload,
    )
    factory.dispose()


def call(batch, payload=None, key=None):
    service, _, project, table, default = batch
    return service.create_many(
        project, table, key or uid(), payload if payload is not None else default
    )


def count(batch):
    with batch[1]() as session:
        return session.scalar(select(func.count()).select_from(DataRecordRow))


def test_invalid_second_row_leaves_no_records_or_operation(batch):
    payload = deepcopy(batch[4])
    payload["rows"][1]["values"] = []
    key = uid()
    with pytest.raises(ProjectError) as error:
        call(batch, payload, key)
    assert error.value.status == 422
    assert (
        error.value.details["rowErrors"][0]["clientRowId"]
        == payload["rows"][1]["clientRowId"]
    )
    assert count(batch) == 0
    with batch[1]() as session:
        assert (
            session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == key
                )
            )
            is None
        )


def test_batch_replay_keeps_original_rows_and_snapshot(batch):
    key = uid()
    result, op, replay = call(batch, key=key)
    assert not replay and len(result["records"]) == 2
    record = result["records"][0]["record"]
    ref = record["ref"]
    service = batch[0]
    service.update(
        batch[2],
        batch[3],
        encode_record_key(RecordKey(**ref["recordKey"])),
        uid(),
        {
            "datasetGeneration": ref["datasetGeneration"],
            "recordKeyType": ref["recordKey"]["type"],
            "expectedContentRevision": 1,
            "values": [
                {
                    "fieldId": batch[4]["rows"][0]["values"][0]["fieldId"],
                    "value": "edited",
                }
            ],
        },
    )
    again, same, replay = call(batch, key=key)
    assert replay and result == again and same == op and count(batch) == 2
    assert all(
        r["record"]["statusId"] is None and r["record"]["contentRevision"] == 1
        for r in result["records"]
    )
    with batch[1]() as session:
        evidence = session.scalars(
            select(DataChangeRow)
            .where(DataChangeRow.operation_id == op.operation_id)
            .order_by(DataChangeRow.sequence)
        ).all()
        assert [e.sequence for e in evidence] == [1, 2]
        assert [e.resource["recordRef"] for e in evidence] == [
            r["record"]["ref"] for r in result["records"]
        ]


def test_different_payload_same_key_is_rejected_before_revision(batch):
    key = uid()
    call(batch, key=key)
    payload = deepcopy(batch[4])
    payload["expectedTableRevision"] = 100
    with pytest.raises(ProjectError) as error:
        call(batch, payload, key)
    assert error.value.code == "OPERATION_PAYLOAD_MISMATCH"


def test_structure_conflict_and_old_generation_do_not_write(batch):
    for field, value in [("expectedTableRevision", 1), ("datasetGeneration", uid())]:
        payload = deepcopy(batch[4])
        payload[field] = value
        with pytest.raises(ProjectError):
            call(batch, payload)
    assert count(batch) == 0


def test_typed_identity_duplicates_and_concurrent_conflict(batch):
    with batch[1].begin() as session:
        session.get(DataTableRow, batch[3]).identity = {
            "mode": "field",
            "fieldId": batch[4]["rows"][0]["values"][0]["fieldId"],
        }

    def attempt(_):
        try:
            return call(batch)[0]
        except ProjectError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))
    assert sum(isinstance(r, dict) for r in results) == 1 and count(batch) == 2
    error = next(r for r in results if isinstance(r, ProjectError))
    assert (
        error.code == "RECORD_ALREADY_EXISTS" and len(error.details["rowErrors"]) == 2
    )
    result = next(r for r in results if isinstance(r, dict))
    assert [r["record"]["ref"]["recordKey"] for r in result["records"]] == [
        {"type": "text", "value": "001"},
        {"type": "text", "value": "1"},
    ]


def test_duplicate_within_batch_is_atomic(batch):
    with batch[1].begin() as session:
        session.get(DataTableRow, batch[3]).identity = {
            "mode": "field",
            "fieldId": batch[4]["rows"][0]["values"][0]["fieldId"],
        }
    payload = deepcopy(batch[4])
    payload["rows"][1]["values"] = payload["rows"][0]["values"]
    with pytest.raises(ProjectError) as error:
        call(batch, payload)
    assert error.value.code == "RECORD_ALREADY_EXISTS" and count(batch) == 0


def test_evidence_fault_rolls_back_every_row(batch):
    def fail(mapper, connection, row):
        if row.sequence == 2:
            raise RuntimeError("second evidence failed")

    event.listen(DataChangeRow, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="second evidence"):
            call(batch)
    finally:
        event.remove(DataChangeRow, "before_insert", fail)
    assert count(batch) == 0


@pytest.mark.parametrize("n", [0, 101])
def test_row_limits(batch, n):
    payload = deepcopy(batch[4])
    payload["rows"] = [
        {"clientRowId": uid(), "values": batch[4]["rows"][0]["values"]}
        for _ in range(n)
    ]
    with pytest.raises(ProjectError) as error:
        call(batch, payload)
    assert error.value.status == 422 and count(batch) == 0


def test_hundred_rows_and_payload_limit(batch):
    payload = deepcopy(batch[4])
    payload["rows"] = [
        {"clientRowId": uid(), "values": batch[4]["rows"][0]["values"]}
        for _ in range(100)
    ]
    assert len(call(batch, payload)[0]["records"]) == 100
    payload = deepcopy(batch[4])
    payload["rows"][0]["values"][0]["value"] = "界" * (1024 * 1024 // 3 + 1)
    with pytest.raises(ProjectError) as error:
        call(batch, payload)
    assert error.value.status == 413 and count(batch) == 100


def test_duplicate_client_row_id_rejected(batch):
    payload = deepcopy(batch[4])
    payload["rows"][1]["clientRowId"] = payload["rows"][0]["clientRowId"]
    with pytest.raises(ProjectError) as error:
        call(batch, payload)
    assert error.value.status == 422 and count(batch) == 0
