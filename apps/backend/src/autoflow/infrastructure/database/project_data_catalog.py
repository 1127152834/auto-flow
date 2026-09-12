from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_data import (
    SqlAlchemyProjectData,
    _completed,
    _operation,
    _operation_result,
    _operation_row,
)
from autoflow.infrastructure.database.project_data_impacts import (
    SqlAlchemyProjectDataImpacts,
)
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataFieldRow,
    DataRecordRow,
    DataStatusRow,
    DataTableRow,
)


class SqlAlchemyProjectDataCatalog:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory
        self._impacts = SqlAlchemyProjectDataImpacts(session_factory)

    def preview_field_update(
        self, project_id: str, ref: dict[str, Any], definition: dict[str, Any]
    ) -> dict[str, Any]:
        return self._impacts.preview_field_update(project_id, ref, definition)

    def fields(self, project_id: str, table_id: str) -> dict[str, Any]:
        with self._session_factory() as session:
            table = self._table(session, project_id, table_id, False)
            rows = session.scalars(
                select(DataFieldRow)
                .where(
                    DataFieldRow.project_id == project_id,
                    DataFieldRow.table_id == table_id,
                    DataFieldRow.dataset_generation == table.current_generation,
                )
                .order_by(DataFieldRow.position, DataFieldRow.id)
            ).all()
            return {
                "items": [_field(row) for row in rows],
                "tableRevision": table.table_revision,
            }

    def create_field(
        self,
        project_id: str,
        table_id: str,
        field_id: str,
        definition: dict[str, Any],
        has_default: bool,
        default: object,
        expected_revision: int,
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = self._existing(session, operation)
            if existing is not None:
                session.rollback()
                return _operation_result(existing), _operation(existing), True
            table = self._table(session, project_id, table_id, True)
            self._cas(table.table_revision, expected_revision)
            record_filter = (
                DataRecordRow.project_id == project_id,
                DataRecordRow.table_id == table_id,
                DataRecordRow.dataset_generation == table.current_generation,
                DataRecordRow.deleted.is_(False),
            )
            if (
                definition["required"]
                and not has_default
                and session.scalar(
                    select(DataRecordRow.key_value).where(*record_filter).limit(1)
                )
                is not None
            ):
                session.rollback()
                raise ProjectError(
                    "EXISTING_RECORD_DEFAULT_REQUIRED",
                    "A valid default is required for existing records",
                    422,
                    {
                        "domainCode": "existing_record_default_required",
                        "retryable": False,
                    },
                )
            position = (
                session.scalar(
                    select(func.count())
                    .select_from(DataFieldRow)
                    .where(DataFieldRow.dataset_generation == table.current_generation)
                )
                or 0
            )
            row = DataFieldRow(
                id=field_id,
                project_id=project_id,
                table_id=table_id,
                dataset_generation=table.current_generation,
                key=definition["key"],
                name=definition["name"],
                type=definition["type"],
                required=definition["required"],
                writable=True,
                formula=False,
                validation=definition["validation"],
                field_revision=1,
                position=position,
            )
            table.table_revision += 1
            table.updated_at = datetime.now(UTC)
            snapshot = _field(row)
            result = {
                "action": "create",
                "field": snapshot,
                "tableRevision": table.table_revision,
            }
            operation = replace(
                operation,
                resource={"type": "field", "fieldRef": snapshot["ref"]},
            )
            done = _completed(operation, result)
            try:
                session.add(row)
                session.add(_operation_row(done))
                session.flush()
                session.add(_change(done, 1, None, snapshot))
                if has_default:
                    records = session.scalars(
                        select(DataRecordRow)
                        .where(*record_filter)
                        .order_by(DataRecordRow.key_type, DataRecordRow.key_value)
                        .execution_options(yield_per=200)
                    )
                    batch: list[DataRecordRow] = []
                    for sequence, record in enumerate(records, 2):
                        before = {
                            "values": record.values_json,
                            "contentRevision": record.content_revision,
                        }
                        record.values_json = {**record.values_json, field_id: default}
                        record.content_revision += 1
                        record.updated_at = table.updated_at
                        session.add(
                            _change(
                                done,
                                sequence,
                                before,
                                {
                                    "values": record.values_json,
                                    "contentRevision": record.content_revision,
                                },
                                _record_resource(project_id, table_id, record),
                            )
                        )
                        batch.append(record)
                        if len(batch) == 200:
                            session.flush()
                            for materialized in batch:
                                session.expunge(materialized)
                            batch.clear()
                    if batch:
                        session.flush()
                        for materialized in batch:
                            session.expunge(materialized)
                session.commit()
                return result, done, False
            except IntegrityError as error:
                session.rollback()
                raise ProjectError(
                    "FIELD_KEY_CONFLICT",
                    "Field key is already in use",
                    409,
                    {"domainCode": "field_key_conflict", "retryable": False},
                ) from error

    def update_field(
        self,
        project_id: str,
        table_id: str,
        field_id: str,
        definition: dict[str, Any],
        expected_table_revision: int,
        expected_field_revision: int,
        impact_revision: int,
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = self._existing(session, operation)
            if existing is not None:
                session.rollback()
                return _operation_result(existing), _operation(existing), True
            table = self._table(session, project_id, table_id, True)
            row = session.scalar(
                select(DataFieldRow).where(
                    DataFieldRow.project_id == project_id,
                    DataFieldRow.table_id == table_id,
                    DataFieldRow.dataset_generation == table.current_generation,
                    DataFieldRow.id == field_id,
                )
            )
            if row is None:
                session.rollback()
                raise ProjectError("FIELD_NOT_FOUND", "Field was not found", 404)
            self._cas(table.table_revision, expected_table_revision)
            self._cas(row.field_revision, expected_field_revision, "Field")
            ref = {
                "projectId": project_id,
                "tableId": table_id,
                "datasetGeneration": table.current_generation,
                "fieldId": field_id,
            }
            self._impacts.require_field_update(
                session, project_id, ref, definition, impact_revision
            )
            before = _field(row)
            changed = any(
                before[key] != definition[key]
                for key in ("key", "name", "type", "required", "validation")
            )
            if changed:
                row.key = definition["key"]
                row.name = definition["name"]
                row.type = definition["type"]
                row.required = definition["required"]
                row.validation = definition["validation"]
                row.field_revision += 1
                table.table_revision += 1
                table.updated_at = datetime.now(UTC)
            snapshot = _field(row)
            resource = {"type": "field", "fieldRef": ref}
            operation = replace(operation, resource=resource)
            result = {
                "action": "update",
                "field": snapshot,
                "tableRevision": table.table_revision,
            }
            done = _completed(operation, result)
            try:
                session.add(_operation_row(done))
                session.flush()
                if changed:
                    session.add(_change(done, 1, before, snapshot, resource))
                session.commit()
                return result, done, False
            except IntegrityError as error:
                session.rollback()
                raise ProjectError(
                    "FIELD_KEY_CONFLICT",
                    "Field key is already in use",
                    409,
                    {"domainCode": "field_key_conflict", "retryable": False},
                ) from error

    def statuses(self, project_id: str, table_id: str) -> dict[str, Any]:
        with self._session_factory() as session:
            table = self._table(session, project_id, table_id, False)
            rows = session.scalars(
                select(DataStatusRow)
                .where(
                    DataStatusRow.project_id == project_id,
                    DataStatusRow.table_id == table_id,
                )
                .order_by(DataStatusRow.position, DataStatusRow.id)
            ).all()
            return {
                "items": [_status(row) for row in rows],
                "tableRevision": table.table_revision,
            }

    def create_status(
        self,
        project_id: str,
        table_id: str,
        status_id: str,
        value: dict[str, Any],
        expected_revision: int,
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = self._existing(session, operation)
            if existing is not None:
                session.rollback()
                return _operation_result(existing), _operation(existing), True
            table = self._table(session, project_id, table_id, True)
            self._cas(table.table_revision, expected_revision)
            row = DataStatusRow(
                id=status_id,
                project_id=project_id,
                table_id=table_id,
                name=value["name"],
                name_key=value["name"].casefold(),
                color=value["color"],
                position=value["order"],
                status_revision=1,
            )
            table.table_revision += 1
            table.updated_at = datetime.now(UTC)
            snapshot = _status(row)
            result = {
                "action": "create",
                "status": snapshot,
                "tableRevision": table.table_revision,
            }
            done = _completed(operation, result)
            try:
                session.add(row)
                session.add(_operation_row(done))
                session.flush()
                session.add(_change(done, 1, None, snapshot))
                session.commit()
                return result, done, False
            except IntegrityError as error:
                session.rollback()
                raise _status_conflict() from error

    def update_status(
        self,
        project_id: str,
        table_id: str,
        status_id: str,
        patch: dict[str, Any],
        expected_table_revision: int,
        expected_status_revision: int,
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = self._existing(session, operation)
            if existing is not None:
                session.rollback()
                return _operation_result(existing), _operation(existing), True
            table = self._table(session, project_id, table_id, True)
            row = session.scalar(
                select(DataStatusRow).where(
                    DataStatusRow.project_id == project_id,
                    DataStatusRow.table_id == table_id,
                    DataStatusRow.id == status_id,
                )
            )
            if row is None:
                session.rollback()
                raise ProjectError("STATUS_NOT_FOUND", "Status was not found", 404)
            self._cas(table.table_revision, expected_table_revision)
            self._cas(row.status_revision, expected_status_revision, "Status")
            before = _status(row)
            changed = any(
                before[{"position": "order"}.get(key, key)] != value
                for key, value in patch.items()
            )
            if changed:
                if "name" in patch:
                    row.name = patch["name"]
                    row.name_key = row.name.casefold()
                if "color" in patch:
                    row.color = patch["color"]
                if "order" in patch:
                    row.position = patch["order"]
                row.status_revision += 1
                table.table_revision += 1
                table.updated_at = datetime.now(UTC)
            snapshot = _status(row)
            result = {
                "action": "update",
                "status": snapshot,
                "tableRevision": table.table_revision,
            }
            done = _completed(operation, result)
            try:
                session.add(_operation_row(done))
                session.flush()
                if changed:
                    session.add(_change(done, 1, before, snapshot))
                session.commit()
                return result, done, False
            except IntegrityError as error:
                session.rollback()
                raise _status_conflict() from error

    @staticmethod
    def _existing(
        session: Session, operation: ProjectOperation
    ) -> ProjectOperationRow | None:
        existing = session.scalar(
            select(ProjectOperationRow).where(
                ProjectOperationRow.idempotency_key == operation.idempotency_key
            )
        )
        if existing is not None and (
            existing.kind != operation.kind
            or existing.request_digest != operation.request_digest
        ):
            raise ProjectError(
                "OPERATION_PAYLOAD_MISMATCH",
                "Idempotency key was used for another request",
                409,
                {"domainCode": "operation_payload_mismatch", "retryable": False},
            )
        return existing

    @staticmethod
    def _table(
        session: Session, project_id: str, table_id: str, write: bool
    ) -> DataTableRow:
        (
            SqlAlchemyProjectData._guard_project_write
            if write
            else SqlAlchemyProjectData._guard_project_read
        )(session, project_id)
        row = session.scalar(
            select(DataTableRow).where(
                DataTableRow.project_id == project_id, DataTableRow.id == table_id
            )
        )
        if row is None:
            raise ProjectError("TABLE_NOT_FOUND", "Table was not found", 404)
        return row

    @staticmethod
    def _cas(current: int, expected: int, resource: str = "Table") -> None:
        if current != expected:
            raise ProjectError(
                "REVISION_CONFLICT",
                f"{resource} was modified",
                409,
                {
                    "expectedRevision": expected,
                    "currentRevision": current,
                    "domainCode": "revision_conflict",
                    "retryable": False,
                },
            )


def _field(row: DataFieldRow) -> dict[str, Any]:
    return {
        "ref": {
            "projectId": row.project_id,
            "tableId": row.table_id,
            "datasetGeneration": row.dataset_generation,
            "fieldId": row.id,
        },
        "key": row.key,
        "name": row.name,
        "type": row.type,
        "required": row.required,
        "writable": row.writable,
        "formula": row.formula,
        "validation": row.validation,
        "fieldRevision": row.field_revision,
    }


def _status(row: DataStatusRow) -> dict[str, Any]:
    return {
        "statusId": row.id,
        "name": row.name,
        "color": row.color,
        "order": row.position,
        "statusRevision": row.status_revision,
    }


def _record_resource(
    project_id: str, table_id: str, row: DataRecordRow
) -> dict[str, Any]:
    return {
        "type": "record",
        "recordRef": {
            "projectId": project_id,
            "tableId": table_id,
            "datasetGeneration": row.dataset_generation,
            "recordKey": {"type": row.key_type, "value": row.key_value},
        },
    }


def _change(
    operation: ProjectOperation,
    sequence: int,
    before: dict[str, Any] | None,
    after: dict[str, Any],
    resource: dict[str, Any] | None = None,
) -> DataChangeRow:
    return DataChangeRow(
        id=str(uuid4()),
        project_id=operation.project_id,
        operation_id=operation.operation_id,
        sequence=sequence,
        resource=resource or operation.resource,
        origin="manual",
        before=before,
        after=after,
        created_at=operation.completed_at,
    )


def _status_conflict() -> ProjectError:
    return ProjectError(
        "STATUS_NAME_CONFLICT",
        "Status name is already in use",
        409,
        {"domainCode": "status_name_conflict", "retryable": False},
    )
