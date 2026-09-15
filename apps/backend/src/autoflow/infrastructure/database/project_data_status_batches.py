from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_claims import active_record_lease
from autoflow.infrastructure.database.project_data import _operation, _operation_row
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataRecordRow,
    DataStatusRow,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_data_status_batch_models import (
    DataStatusBatchBlockRow,
    DataStatusBatchRow,
)


class SqlAlchemyRecordStatusBatches:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def preview(
        self, project_id: str, table_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            self._validate_destination(
                session, project_id, table_id, request["statusId"]
            )
            blocks = []
            for index, targets in enumerate(_chunks(request)):
                blockers, _ = self._check_targets(
                    session, project_id, table_id, targets
                )
                blocks.append(_block(index, targets, "notStarted", blockers, []))
            return {
                "request": request,
                "blocks": blocks,
                "checkedAt": datetime.now(UTC).isoformat(),
            }

    def accept(
        self,
        project_id: str,
        table_id: str,
        request: dict[str, Any],
        operation: ProjectOperation,
    ) -> tuple[ProjectOperation, bool]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = SqlAlchemyProjectDataCatalog._existing(session, operation)
            if existing is not None:
                session.rollback()
                return _operation(existing), True
            self._validate_destination(
                session, project_id, table_id, request["statusId"]
            )
            blocks = [
                _block(index, targets, "notStarted", [], [])
                for index, targets in enumerate(_chunks(request))
            ]
            operation = _with_outcome(operation, request, blocks)
            session.add(_operation_row(operation))
            session.flush()
            session.add(
                DataStatusBatchRow(
                    operation_id=operation.operation_id,
                    project_id=project_id,
                    table_id=table_id,
                    status_id=request["statusId"],
                    request=request,
                    block_size=request["blockSize"],
                    cancel_requested=False,
                )
            )
            session.flush()
            session.add_all(
                DataStatusBatchBlockRow(
                    operation_id=operation.operation_id,
                    block_index=block["blockIndex"],
                    targets=block["targets"],
                    state="notStarted",
                    blockers=[],
                    committed_revisions=[],
                )
                for block in blocks
            )
            session.commit()
            return operation, False

    def process_block(self, operation_id: str) -> bool:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            batch = session.get(DataStatusBatchRow, operation_id)
            operation = session.get(ProjectOperationRow, operation_id)
            if (
                batch is None
                or operation is None
                or operation.status in {"succeeded", "failed"}
            ):
                session.rollback()
                return False
            if batch.cancel_requested:
                self._finish(session, batch, operation, cancelled=True)
                session.commit()
                return False
            block = session.scalar(
                select(DataStatusBatchBlockRow)
                .where(
                    DataStatusBatchBlockRow.operation_id == operation_id,
                    DataStatusBatchBlockRow.state == "notStarted",
                )
                .order_by(DataStatusBatchBlockRow.block_index)
                .limit(1)
            )
            if block is None:
                self._finish(session, batch, operation)
                session.commit()
                return False
            if operation.status == "accepted":
                operation.status = "running"
                operation.status_revision += 1
            try:
                self._validate_destination(
                    session, batch.project_id, batch.table_id, batch.status_id
                )
                blockers, rows = self._check_targets(
                    session, batch.project_id, batch.table_id, block.targets
                )
            except ProjectError as error:
                blockers = [
                    _blocker(
                        error.code,
                        {"type": "record", "recordRef": target["recordRef"]},
                        error.message,
                    )
                    for target in block.targets
                ]
                rows = []
            committed: list[dict[str, Any]] = []
            if blockers:
                block.state, block.blockers = "conflicted", blockers
            else:
                fields = SqlAlchemyProjectDataRecords._fields(
                    session,
                    SqlAlchemyProjectDataRecords._table(
                        session,
                        batch.project_id,
                        batch.table_id,
                        batch.request["targets"][0]["recordRef"]["datasetGeneration"],
                        True,
                    ),
                )
                for offset, (target, row) in enumerate(
                    zip(block.targets, rows, strict=True)
                ):
                    before = SqlAlchemyProjectDataRecords._snapshot(row, fields)
                    changed = (
                        batch.status_id is None or batch.status_id != row.status_id
                    )
                    if changed:
                        row.status_id = batch.status_id
                        row.status_revision += 1
                        row.updated_at = datetime.now(UTC)
                    after = SqlAlchemyProjectDataRecords._snapshot(row, fields)
                    committed.append(
                        {
                            "recordRef": target["recordRef"],
                            "statusRevision": row.status_revision,
                        }
                    )
                    if changed:
                        session.add(
                            DataChangeRow(
                                id=str(uuid4()),
                                project_id=batch.project_id,
                                operation_id=operation_id,
                                sequence=block.block_index * batch.block_size
                                + offset
                                + 1,
                                resource={
                                    "type": "record",
                                    "recordRef": target["recordRef"],
                                },
                                origin="manual",
                                before=before,
                                after=after,
                                created_at=datetime.now(UTC),
                            )
                        )
                block.state, block.committed_revisions = "committed", committed
            operation.updated_at = datetime.now(UTC)
            operation.result = self._outcome(session, batch)
            operation.status_revision += 1
            session.flush()
            if not session.scalar(
                select(DataStatusBatchBlockRow.operation_id)
                .where(
                    DataStatusBatchBlockRow.operation_id == operation_id,
                    DataStatusBatchBlockRow.state == "notStarted",
                )
                .limit(1)
            ):
                self._finish(session, batch, operation)
                session.commit()
                return False
            session.commit()
            return True

    def cancel(
        self,
        project_id: str,
        table_id: str,
        operation_id: str,
        expected_revision: int,
        command: ProjectOperation,
    ) -> tuple[ProjectOperation, bool]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = SqlAlchemyProjectDataCatalog._existing(session, command)
            if existing is not None:
                session.rollback()
                return _operation(existing), True
            batch = session.get(DataStatusBatchRow, operation_id)
            original = session.get(ProjectOperationRow, operation_id)
            if (
                batch is None
                or original is None
                or batch.project_id != project_id
                or batch.table_id != table_id
            ):
                raise ProjectError(
                    "OPERATION_NOT_FOUND", "Operation was not found", 404
                )
            if original.status_revision != expected_revision:
                raise ProjectError(
                    "REVISION_CONFLICT",
                    "Operation was modified",
                    409,
                    {
                        "expectedRevision": expected_revision,
                        "currentRevision": original.status_revision,
                        "retryable": False,
                    },
                )
            if original.status in {"succeeded", "failed"}:
                raise ProjectError(
                    "OPERATION_NOT_CANCELLABLE",
                    "Operation is already terminal",
                    409,
                    {"retryable": False},
                )
            batch.cancel_requested = True
            self._finish(session, batch, original, cancelled=True)
            now = datetime.now(UTC)
            command = replace(
                command,
                status="succeeded",
                status_revision=2,
                result={
                    "operationId": operation_id,
                    "subsequentBlocksClosed": True,
                },
                updated_at=now,
                completed_at=now,
            )
            session.add(_operation_row(command))
            session.commit()
            return command, False

    def pending_operation_ids(self) -> list[str]:
        with self._session_factory() as session:
            return list(
                session.scalars(
                    select(ProjectOperationRow.id)
                    .join(
                        DataStatusBatchRow,
                        DataStatusBatchRow.operation_id == ProjectOperationRow.id,
                    )
                    .where(
                        ProjectOperationRow.status.in_(
                            ("accepted", "running", "reconciling")
                        )
                    )
                ).all()
            )

    def fail(self, operation_id: str, error: Exception) -> None:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            batch = session.get(DataStatusBatchRow, operation_id)
            operation = session.get(ProjectOperationRow, operation_id)
            if (
                batch is None
                or operation is None
                or operation.status in {"succeeded", "failed"}
            ):
                session.rollback()
                return
            now = datetime.now(UTC)
            result = self._outcome(session, batch)
            result["outcome"] = "failed"
            operation.status = "failed"
            operation.status_revision += 1
            operation.result = result
            operation.error = {
                "code": "BATCH_STATUS_EXECUTION_FAILED",
                "message": "Batch status execution failed",
                "details": {
                    "retryable": True,
                    "exceptionType": type(error).__name__,
                },
            }
            operation.updated_at = operation.completed_at = now
            session.commit()

    def references_pending(self, record_ref: dict[str, Any]) -> bool:
        with self._session_factory() as session:
            blocks = session.scalars(
                select(DataStatusBatchBlockRow).where(
                    DataStatusBatchBlockRow.state == "notStarted"
                )
            ).all()
            return any(
                target["recordRef"] == record_ref
                for block in blocks
                for target in block.targets
            )

    @staticmethod
    def _validate_destination(
        session: Session, project_id: str, table_id: str, status_id: str | None
    ) -> None:
        SqlAlchemyProjectDataRecords._table(
            session,
            project_id,
            table_id,
            _current_generation(session, project_id, table_id),
            True,
        )
        if (
            status_id is not None
            and session.scalar(
                select(DataStatusRow.id).where(
                    DataStatusRow.project_id == project_id,
                    DataStatusRow.table_id == table_id,
                    DataStatusRow.id == status_id,
                    DataStatusRow.deleted.is_(False),
                )
            )
            is None
        ):
            raise ProjectError("STATUS_NOT_FOUND", "Status was not found", 404)

    @staticmethod
    def _check_targets(
        session: Session, project_id: str, table_id: str, targets: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[DataRecordRow]]:
        blockers, rows = [], []
        current_generation = _current_generation(session, project_id, table_id)
        for target in targets:
            ref, expected = target["recordRef"], target["expectedStatusRevision"]
            key = ref["recordKey"]
            row = session.get(
                DataRecordRow, (ref["datasetGeneration"], key["type"], key["value"])
            )
            resource = {"type": "record", "recordRef": ref}
            if ref["datasetGeneration"] != current_generation:
                blockers.append(
                    _blocker(
                        "DATASET_GENERATION_GONE",
                        resource,
                        "Dataset generation is no longer current",
                    )
                )
            elif (
                row is None
                or row.deleted
                or row.project_id != project_id
                or row.table_id != table_id
            ):
                blockers.append(
                    _blocker("RECORD_NOT_FOUND", resource, "Record was not found")
                )
            elif active_record_lease(
                session,
                project_id,
                table_id,
                ref["datasetGeneration"],
                RecordKey(key["type"], key["value"]),
            ) is not None:
                blockers.append(
                    _blocker(
                        "RECORD_IN_USE",
                        resource,
                        "Record is currently used by a running task",
                    )
                )
            elif row.status_revision != expected:
                blockers.append(
                    _blocker(
                        "REVISION_CONFLICT",
                        resource,
                        "Record status was modified",
                        {
                            "expectedRevision": expected,
                            "currentRevision": row.status_revision,
                        },
                    )
                )
            else:
                rows.append(row)
        return blockers, rows

    def _outcome(self, session: Session, batch: DataStatusBatchRow) -> dict[str, Any]:
        blocks = [
            _block(
                row.block_index,
                row.targets,
                row.state,
                row.blockers,
                row.committed_revisions,
            )
            for row in session.scalars(
                select(DataStatusBatchBlockRow)
                .where(DataStatusBatchBlockRow.operation_id == batch.operation_id)
                .order_by(DataStatusBatchBlockRow.block_index)
            ).all()
        ]
        conflicts = sum(
            len(block["targets"]) for block in blocks if block["state"] == "conflicted"
        )
        changed = (
            session.scalar(
                select(func.count())
                .select_from(DataChangeRow)
                .where(DataChangeRow.operation_id == batch.operation_id)
            )
            or 0
        )
        not_started = sum(
            len(block["targets"]) for block in blocks if block["state"] == "notStarted"
        )
        outcome = (
            "cancelled"
            if batch.cancel_requested
            else "processing"
            if not_started
            else "conflicted"
            if conflicts
            else "completed"
        )
        return {
            "outcome": outcome,
            "request": batch.request,
            "blocks": blocks,
            "changedCount": changed,
            "conflictCount": conflicts,
            "notStartedCount": not_started,
            "cancelled": batch.cancel_requested,
        }

    def _finish(
        self,
        session: Session,
        batch: DataStatusBatchRow,
        operation: ProjectOperationRow,
        cancelled: bool = False,
    ) -> None:
        if cancelled:
            batch.cancel_requested = True
        result = self._outcome(session, batch)
        failed = result["cancelled"] or result["conflictCount"] > 0
        operation.status = "failed" if failed else "succeeded"
        operation.status_revision += 1
        operation.result = result
        operation.error = (
            {
                "code": "BATCH_STATUS_CANCELLED"
                if result["cancelled"]
                else "BATCH_STATUS_CONFLICT",
                "message": "Batch status operation was cancelled"
                if result["cancelled"]
                else "One or more blocks conflicted",
                "details": {"retryable": False},
            }
            if failed
            else None
        )
        operation.updated_at = operation.completed_at = datetime.now(UTC)


def _current_generation(session: Session, project_id: str, table_id: str) -> str:
    from autoflow.infrastructure.database.project_data_models import DataTableRow

    row = session.scalar(
        select(DataTableRow).where(
            DataTableRow.published.is_(True),
            DataTableRow.project_id == project_id,
            DataTableRow.id == table_id,
        )
    )
    if row is None:
        raise ProjectError("TABLE_NOT_FOUND", "Table was not found", 404)
    return row.current_generation


def _chunks(request: dict[str, Any]):
    targets, size = request["targets"], request["blockSize"]
    for start in range(0, len(targets), size):
        yield targets[start : start + size]


def _block(
    index: int,
    targets: list[dict[str, Any]],
    state: str,
    blockers: list[dict[str, Any]],
    committed: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "blockIndex": index,
        "targets": targets,
        "state": state,
        "blockers": blockers,
        "committedRevisions": committed,
    }


def _blocker(
    code: str,
    resource: dict[str, Any],
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "resource": resource,
        "state": "blocked",
        "message": message,
        **({"details": details} if details else {}),
    }


def _with_outcome(
    operation: ProjectOperation, request: dict[str, Any], blocks: list[dict[str, Any]]
) -> ProjectOperation:
    return replace(
        operation,
        result={
            "outcome": "processing",
            "request": request,
            "blocks": blocks,
            "changedCount": 0,
            "conflictCount": 0,
            "notStartedCount": len(request["targets"]),
            "cancelled": False,
        },
    )
