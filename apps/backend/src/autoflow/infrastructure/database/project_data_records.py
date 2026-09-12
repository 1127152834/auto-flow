from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.identity import (
    RecordKey,
    record_key,
    system_record_key,
)
from autoflow.domain.project_data.rules import validate_value
from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.infrastructure.database.project_data import (
    SqlAlchemyProjectData,
    _completed,
    _operation,
    _operation_result,
    _operation_row,
)
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataFieldRow,
    DataRecordRow,
    DataStatusRow,
    DataTableRow,
)


class SqlAlchemyProjectDataRecords:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def create(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        values: dict[str, object],
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = SqlAlchemyProjectDataCatalog._existing(session, operation)
            if existing is not None:
                session.rollback()
                return _operation_result(existing), _operation(existing), True
            table = self._table(session, project_id, table_id, generation, True)
            fields = self._fields(session, table)
            canonical = self._validate(fields, values, True)
            identity = table.identity
            if identity.get("mode") == "system":
                key = system_record_key()
            else:
                identity_field_id = identity.get("fieldId")
                if not isinstance(identity_field_id, str):
                    raise ProjectError(
                        "INVALID_PROJECT_DATA", "Invalid table identity", 422
                    )
                key = record_key(canonical.get(identity_field_id))
            now = datetime.now(UTC)
            row = DataRecordRow(
                project_id=project_id,
                table_id=table_id,
                dataset_generation=generation,
                key_type=key.type,
                key_value=key.value,
                values_json=canonical,
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
            snapshot = self._snapshot(row, fields)
            operation = replace(operation, resource=_resource(snapshot["ref"]))
            done = _completed(operation, snapshot)
            try:
                session.add(row)
                session.add(_operation_row(done))
                session.flush()
                session.add(_change(done, None, snapshot))
                session.commit()
                return snapshot, done, False
            except IntegrityError as error:
                session.rollback()
                raise ProjectError(
                    "RECORD_ALREADY_EXISTS", "Record already exists", 409
                ) from error

    def get(
        self, project_id: str, table_id: str, generation: str, key: RecordKey
    ) -> dict[str, Any] | None:
        with self._session_factory() as session:
            table = self._table(session, project_id, table_id, generation, False)
            row = self._record(session, project_id, table_id, generation, key)
            return (
                None
                if row is None or row.deleted
                else self._snapshot(row, self._fields(session, table))
            )

    def update(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        key: RecordKey,
        values: dict[str, object],
        expected: int,
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = SqlAlchemyProjectDataCatalog._existing(session, operation)
            if existing is not None:
                session.rollback()
                return _operation_result(existing), _operation(existing), True
            table = self._table(session, project_id, table_id, generation, True)
            row = self._required_record(session, project_id, table_id, generation, key)
            fields = self._fields(session, table)
            if row.content_revision != expected:
                raise _conflict(expected, row.content_revision, "Content")
            identity_id = (
                table.identity.get("fieldId")
                if table.identity.get("mode") == "field"
                else None
            )
            if identity_id in values:
                raise ProjectError(
                    "IDENTITY_FIELD_IMMUTABLE", "Identity field cannot be changed", 422
                )
            canonical = self._validate(fields, values, False)
            before = self._snapshot(row, fields)
            merged = {**row.values_json, **canonical}
            changed = merged != row.values_json
            if changed:
                row.values_json = merged
                row.content_revision += 1
                row.updated_at = datetime.now(UTC)
            snapshot = self._snapshot(row, fields)
            done = _completed(operation, snapshot)
            session.add(_operation_row(done))
            session.flush()
            if changed:
                session.add(_change(done, before, snapshot))
            session.commit()
            return snapshot, done, False

    def set_status(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        key: RecordKey,
        status_id: str | None,
        expected: int,
        has_from: bool,
        from_status: str | None,
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = SqlAlchemyProjectDataCatalog._existing(session, operation)
            if existing is not None:
                session.rollback()
                return _operation_result(existing), _operation(existing), True
            table = self._table(session, project_id, table_id, generation, True)
            row = self._required_record(session, project_id, table_id, generation, key)
            if row.status_revision != expected:
                raise _conflict(expected, row.status_revision, "Status")
            if has_from and row.status_id != from_status:
                raise ProjectError(
                    "STATUS_PRECONDITION_FAILED",
                    "Record status changed",
                    409,
                    {
                        "expectedFromStatusId": from_status,
                        "currentStatusId": row.status_id,
                    },
                )
            if (
                status_id is not None
                and session.scalar(
                    select(DataStatusRow.id).where(
                        DataStatusRow.project_id == project_id,
                        DataStatusRow.table_id == table_id,
                        DataStatusRow.id == status_id,
                    )
                )
                is None
            ):
                raise ProjectError("STATUS_NOT_FOUND", "Status was not found", 404)
            fields = self._fields(session, table)
            before = self._snapshot(row, fields)
            changed = status_id is None or status_id != row.status_id
            if changed:
                row.status_id = status_id
                row.status_revision += 1
                row.updated_at = datetime.now(UTC)
            snapshot = self._snapshot(row, fields)
            done = _completed(operation, snapshot)
            session.add(_operation_row(done))
            session.flush()
            if changed:
                session.add(_change(done, before, snapshot))
            session.commit()
            return snapshot, done, False

    @staticmethod
    def _table(
        session: Session, project_id: str, table_id: str, generation: str, write: bool
    ) -> DataTableRow:
        (
            SqlAlchemyProjectData._guard_project_write
            if write
            else SqlAlchemyProjectData._guard_project_read
        )(session, project_id)
        table = session.scalar(
            select(DataTableRow).where(
                DataTableRow.project_id == project_id, DataTableRow.id == table_id
            )
        )
        if table is None:
            raise ProjectError("TABLE_NOT_FOUND", "Table was not found", 404)
        if table.current_generation != generation:
            raise ProjectError(
                "DATASET_GENERATION_GONE",
                "Dataset generation is no longer current",
                410,
            )
        if table.source_kind not in {"local", "excel"}:
            raise ProjectError(
                "SOURCE_WRITE_UNAVAILABLE", "Source does not support record writes", 412
            )
        return table

    @staticmethod
    def _fields(session: Session, table: DataTableRow) -> list[DataFieldRow]:
        return list(
            session.scalars(
                select(DataFieldRow)
                .where(
                    DataFieldRow.project_id == table.project_id,
                    DataFieldRow.table_id == table.id,
                    DataFieldRow.dataset_generation == table.current_generation,
                )
                .order_by(DataFieldRow.position, DataFieldRow.id)
            ).all()
        )

    @staticmethod
    def _record(
        session: Session,
        project_id: str,
        table_id: str,
        generation: str,
        key: RecordKey,
    ) -> DataRecordRow | None:
        return session.get(DataRecordRow, (generation, key.type, key.value))

    def _required_record(
        self,
        session: Session,
        project_id: str,
        table_id: str,
        generation: str,
        key: RecordKey,
    ) -> DataRecordRow:
        row = self._record(session, project_id, table_id, generation, key)
        if row is None or row.deleted:
            raise ProjectError("RECORD_NOT_FOUND", "Record was not found", 404)
        return row

    @staticmethod
    def _validate(
        fields: list[DataFieldRow], values: dict[str, object], creating: bool
    ) -> dict[str, object]:
        by_id = {field.id: field for field in fields}
        unknown = set(values) - set(by_id)
        if unknown:
            raise ProjectError("UNKNOWN_FIELD", "Unknown fieldId", 422)
        result: dict[str, object] = {}
        for field_id, value in values.items():
            field = by_id[field_id]
            if not field.writable or field.formula:
                raise ProjectError("FIELD_NOT_WRITABLE", "Field is not writable", 422)
            result[field_id] = validate_value(
                {
                    "key": field.key,
                    "name": field.name,
                    "type": field.type,
                    "required": field.required,
                    "validation": field.validation,
                },
                value,
            )
        if creating:
            for field in fields:
                if field.required and field.id not in result:
                    raise ProjectError(
                        "REQUIRED_FIELD_MISSING",
                        "Required field is missing",
                        422,
                        {"fieldId": field.id},
                    )
        return result

    @staticmethod
    def _snapshot(row: DataRecordRow, fields: list[DataFieldRow]) -> dict[str, Any]:
        ref = {
            "projectId": row.project_id,
            "tableId": row.table_id,
            "datasetGeneration": row.dataset_generation,
            "recordKey": {"type": row.key_type, "value": row.key_value},
        }
        return {
            "ref": ref,
            "values": [
                {
                    "fieldId": field.id,
                    "value": row.values_json.get(field.id),
                    "source": "formula" if field.formula else "local",
                    "readable": True,
                }
                for field in fields
            ],
            "recordSlots": row.record_slots,
            "statusId": row.status_id,
            "currentEnvironmentId": row.current_environment_id,
            "contentRevision": row.content_revision,
            "statusRevision": row.status_revision,
            "linkRevision": row.link_revision,
            "deleted": row.deleted,
            "createdAt": _instant(row.created_at),
            "updatedAt": _instant(row.updated_at),
        }


def _resource(ref: dict[str, Any]) -> dict[str, Any]:
    return {"type": "record", "recordRef": ref}


def _change(
    operation: ProjectOperation, before: dict[str, Any] | None, after: dict[str, Any]
) -> DataChangeRow:
    return DataChangeRow(
        id=str(uuid4()),
        project_id=operation.project_id,
        operation_id=operation.operation_id,
        sequence=1,
        resource=operation.resource,
        origin="manual",
        before=before,
        after=after,
        created_at=operation.completed_at,
    )


def _conflict(expected: int, current: int, kind: str) -> ProjectError:
    return ProjectError(
        "REVISION_CONFLICT",
        f"{kind} was modified",
        409,
        {
            "expectedRevision": expected,
            "currentRevision": current,
            "domainCode": "revision_conflict",
            "retryable": False,
        },
    )


def _instant(value: datetime) -> str:
    return (
        value.replace(tzinfo=UTC).isoformat()
        if value.tzinfo is None
        else value.isoformat()
    )
