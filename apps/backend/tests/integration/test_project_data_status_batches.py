from concurrent.futures import Executor, Future, ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.status_batches import (
    RecordStatusBatchCoordinator,
    RecordStatusBatchService,
    _batch_operation,
)
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.projects.service import ProjectService
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import Base, ProjectOperationRow
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_deletions import (
    SqlAlchemyProjectDataDeletions,
)
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataRecordRow,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_data_status_batch_models import (
    DataStatusBatchBlockRow,
    DataStatusBatchRow,
)
from autoflow.infrastructure.database.project_data_status_batches import (
    SqlAlchemyRecordStatusBatches,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def uid():
    return str(uuid4())


class DeferredExecutor(Executor):
    def __init__(self):
        self.jobs = []

    def submit(self, fn, /, *args, **kwargs):
        self.jobs.append((fn, args, kwargs))
        return Future()

    def run(self):
        fn, args, kwargs = self.jobs.pop(0)
        fn(*args, **kwargs)


def setup(tmp_path):
    path = tmp_path / "status-batches.sqlite3"
    factory = create_session_factory(path)
    migrate_database(path)
    Base.metadata.create_all(factory.kw["bind"])
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
    status = catalog.create_status(
        project,
        table["tableId"],
        uid(),
        {"name": "Ready", "color": "#123456", "order": 0, "expectedTableRevision": 2},
    )[0]["status"]
    records = DataRecordService(SqlAlchemyProjectDataRecords(factory))
    snapshots = [
        records.create(
            project,
            table["tableId"],
            uid(),
            {
                "datasetGeneration": table["datasetGeneration"],
                "values": [{"fieldId": field["ref"]["fieldId"], "value": str(index)}],
            },
        )[0]
        for index in range(3)
    ]
    repository = SqlAlchemyRecordStatusBatches(factory)
    executor = DeferredExecutor()
    coordinator = RecordStatusBatchCoordinator(repository, QuiesceGate(), executor)
    return (
        factory,
        repository,
        executor,
        RecordStatusBatchService(repository, coordinator),
        project,
        table,
        status,
        snapshots,
    )


def request(table, status, records, block_size=2):
    return {
        "statusId": status,
        "targets": [
            {
                "recordRef": record["ref"],
                "expectedStatusRevision": record["statusRevision"],
            }
            for record in records
        ],
        "blockSize": block_size,
    }


def test_conflicted_block_is_atomic_and_later_blocks_continue(tmp_path):
    factory, _, executor, service, project, table, status, records = setup(tmp_path)
    payload = request(table, status["statusId"], records)
    payload["targets"][1]["expectedStatusRevision"] = 99
    operation, replay = service.start(project, table["tableId"], uid(), payload)
    assert not replay and operation.status == "accepted"
    executor.run()
    with factory() as session:
        stored = session.get(ProjectOperationRow, operation.operation_id)
        blocks = session.scalars(
            select(DataStatusBatchBlockRow)
            .where(DataStatusBatchBlockRow.operation_id == operation.operation_id)
            .order_by(DataStatusBatchBlockRow.block_index)
        ).all()
        rows = [
            session.get(
                DataRecordRow,
                (
                    item["ref"]["datasetGeneration"],
                    item["ref"]["recordKey"]["type"],
                    item["ref"]["recordKey"]["value"],
                ),
            )
            for item in records
        ]
        assert (
            stored.status == "failed"
            and stored.error["code"] == "BATCH_STATUS_CONFLICT"
        )
        assert stored.status_revision == 5
        assert [block.state for block in blocks] == ["conflicted", "committed"]
        assert [row.status_id for row in rows] == [None, None, status["statusId"]]
        assert (
            session.scalar(
                select(func.count())
                .select_from(DataChangeRow)
                .where(DataChangeRow.operation_id == operation.operation_id)
            )
            == 1
        )
    factory.dispose()


def test_clear_advances_and_same_nonnull_is_noop(tmp_path):
    factory, _, executor, service, project, table, status, records = setup(tmp_path)
    first, _ = service.start(
        project, table["tableId"], uid(), request(table, status["statusId"], records, 3)
    )
    executor.run()
    with factory() as session:
        result = session.get(ProjectOperationRow, first.operation_id).result
    revised = [
        {**record, "statusRevision": item["statusRevision"]}
        for record, item in zip(
            records, result["blocks"][0]["committedRevisions"], strict=True
        )
    ]
    same, _ = service.start(
        project, table["tableId"], uid(), request(table, status["statusId"], revised, 3)
    )
    executor.run()
    cleared, _ = service.start(
        project, table["tableId"], uid(), request(table, None, revised, 3)
    )
    executor.run()
    with factory() as session:
        same_result = session.get(ProjectOperationRow, same.operation_id).result
        clear_result = session.get(ProjectOperationRow, cleared.operation_id).result
        assert [
            x["statusRevision"] for x in same_result["blocks"][0]["committedRevisions"]
        ] == [2, 2, 2]
        assert same_result["changedCount"] == 0
        assert [
            x["statusRevision"] for x in clear_result["blocks"][0]["committedRevisions"]
        ] == [3, 3, 3]
        assert (
            session.scalar(
                select(func.count())
                .select_from(DataChangeRow)
                .where(DataChangeRow.operation_id == same.operation_id)
            )
            == 0
        )
    factory.dispose()


def test_cancel_closes_unstarted_blocks_and_resume_discovers_work(tmp_path):
    factory, repository, executor, service, project, table, status, records = setup(
        tmp_path
    )
    operation, _ = service.start(
        project, table["tableId"], uid(), request(table, status["statusId"], records, 1)
    )
    assert repository.pending_operation_ids() == [operation.operation_id]
    command, replay = service.cancel(
        project,
        table["tableId"],
        operation.operation_id,
        uid(),
        {"expectedOperationRevision": 1},
    )
    assert not replay and command.status == "succeeded"
    assert command.kind == "cancelRecordStatuses" and command.result == {
        "operationId": operation.operation_id,
        "subsequentBlocksClosed": True,
    }
    executor.run()
    with factory() as session:
        original = session.get(ProjectOperationRow, operation.operation_id)
        assert (
            original.status == "failed"
            and original.error["code"] == "BATCH_STATUS_CANCELLED"
        )
        assert original.result["notStartedCount"] == 3
    factory.dispose()


def test_failed_block_transaction_is_resumed_without_replaying_commits(tmp_path):
    factory, _, executor, service, project, table, status, records = setup(tmp_path)
    operation, _ = service.start(
        project,
        table["tableId"],
        uid(),
        request(table, status["statusId"], records[:2], 2),
    )

    failures = 0

    def fail_second_change(_mapper, _connection, target):
        nonlocal failures
        if (
            target.operation_id == operation.operation_id
            and target.sequence == 2
            and failures == 0
        ):
            failures += 1
            raise RuntimeError("simulated crash")

    event.listen(DataChangeRow, "before_insert", fail_second_change)
    try:
        executor.run()
    finally:
        event.remove(DataChangeRow, "before_insert", fail_second_change)
    with factory() as session:
        block = session.get(DataStatusBatchBlockRow, (operation.operation_id, 0))
        assert block.state == "committed"
        assert (
            session.scalar(
                select(func.count())
                .select_from(DataChangeRow)
                .where(DataChangeRow.operation_id == operation.operation_id)
            )
            == 2
        )
        stored = session.get(ProjectOperationRow, operation.operation_id)
        assert stored.status == "succeeded" and stored.result["changedCount"] == 2
    factory.dispose()


def test_repeated_unexpected_failure_becomes_durable_terminal_error(tmp_path):
    factory, _, executor, service, project, table, status, records = setup(tmp_path)
    operation, _ = service.start(
        project,
        table["tableId"],
        uid(),
        request(table, status["statusId"], records[:2], 2),
    )

    def always_fail(_mapper, _connection, target):
        if target.operation_id == operation.operation_id:
            raise RuntimeError("simulated persistent failure")

    event.listen(DataChangeRow, "before_insert", always_fail)
    try:
        executor.run()
    finally:
        event.remove(DataChangeRow, "before_insert", always_fail)
    with factory() as session:
        stored = session.get(ProjectOperationRow, operation.operation_id)
        block = session.get(DataStatusBatchBlockRow, (operation.operation_id, 0))
        assert stored.status == "failed"
        assert stored.error["code"] == "BATCH_STATUS_EXECUTION_FAILED"
        assert stored.error["details"]["exceptionType"] == "RuntimeError"
        assert stored.result["outcome"] == "failed"
        assert block.state == "notStarted"
    factory.dispose()


def test_concurrent_workers_commit_each_block_once(tmp_path):
    factory, repository, _, _, project, table, status, records = setup(tmp_path)
    operation = repository.accept(
        project,
        table["tableId"],
        request(table, status["statusId"], records, 3),
        _batch_operation(
            project,
            table["tableId"],
            uid(),
            "setRecordStatuses",
            request(table, status["statusId"], records, 3),
        ),
    )[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(repository.process_block, [operation.operation_id] * 2))
    assert results == [False, False]
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(DataChangeRow)
                .where(DataChangeRow.operation_id == operation.operation_id)
            )
            == 3
        )
    factory.dispose()


def test_stale_generation_conflicts_whole_block_and_reaches_terminal(tmp_path):
    factory, _, executor, service, project, table, status, records = setup(tmp_path)
    payload = request(table, status["statusId"], records[:2], 2)
    payload["targets"][0]["recordRef"]["datasetGeneration"] = uid()
    operation, _ = service.start(project, table["tableId"], uid(), payload)
    executor.run()
    with factory() as session:
        stored = session.get(ProjectOperationRow, operation.operation_id)
        block = session.get(DataStatusBatchBlockRow, (operation.operation_id, 0))
        assert stored.status == "failed" and block.state == "conflicted"
        assert block.blockers[0]["code"] == "DATASET_GENERATION_GONE"
        current = session.get(
            DataRecordRow,
            (
                records[1]["ref"]["datasetGeneration"],
                records[1]["ref"]["recordKey"]["type"],
                records[1]["ref"]["recordKey"]["value"],
            ),
        )
        assert current.status_id is None
    factory.dispose()


def test_terminal_cancel_still_requires_current_operation_revision(tmp_path):
    factory, _, executor, service, project, table, status, records = setup(tmp_path)
    operation, _ = service.start(
        project, table["tableId"], uid(), request(table, status["statusId"], records, 3)
    )
    executor.run()
    with pytest.raises(ProjectError) as caught:
        service.cancel(
            project,
            table["tableId"],
            operation.operation_id,
            uid(),
            {"expectedOperationRevision": 1},
        )
    assert caught.value.code == "REVISION_CONFLICT"
    with factory() as session:
        revision = session.get(
            ProjectOperationRow, operation.operation_id
        ).status_revision
    with pytest.raises(ProjectError) as terminal:
        service.cancel(
            project,
            table["tableId"],
            operation.operation_id,
            uid(),
            {"expectedOperationRevision": revision},
        )
    assert terminal.value.code == "OPERATION_NOT_CANCELLABLE"
    with factory() as session:
        assert (
            session.get(DataStatusBatchRow, operation.operation_id).cancel_requested
            is False
        )
    factory.dispose()


def test_status_deletion_reports_pending_batch_destination(tmp_path):
    factory, repository, _, _, project, table, status, records = setup(tmp_path)
    frozen = request(table, status["statusId"], records, 3)
    repository.accept(
        project,
        table["tableId"],
        frozen,
        _batch_operation(project, table["tableId"], uid(), "setRecordStatuses", frozen),
    )
    report = SqlAlchemyProjectDataDeletions(factory).preview_status(
        project, table["tableId"], status["statusId"]
    )
    assert "STATUS_BATCH_DESTINATION_PENDING" in {
        blocker["code"] for blocker in report["blockers"]
    }
    factory.dispose()


@pytest.mark.parametrize(
    ("key_type", "value"),
    [
        ("integer", "001"),
        ("integer", "1.0"),
        ("uuid", "4CC4BD80-8F6A-48A7-A989-748E43A45389"),
        ("text", "bad\ud800text"),
    ],
)
def test_request_rejects_noncanonical_typed_record_keys(tmp_path, key_type, value):
    factory, _, _, service, project, table, _, records = setup(tmp_path)
    target = {
        "recordRef": {
            **records[0]["ref"],
            "recordKey": {"type": key_type, "value": value},
        },
        "expectedStatusRevision": 1,
    }
    with pytest.raises(ProjectError) as caught:
        service.preview(
            project,
            table["tableId"],
            {"statusId": None, "targets": [target]},
        )
    assert caught.value.status == 422
    factory.dispose()
