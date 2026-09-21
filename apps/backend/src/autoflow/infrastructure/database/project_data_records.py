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
from autoflow.domain.project_data.records import validate_record_scalar
from autoflow.domain.project_data.rules import validate_value, validation_issues
from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.infrastructure.database.project_claims import active_record_lease
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
from autoflow.infrastructure.database.project_sync import enqueue_intent


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
        key: RecordKey | None = None,
        origin: str = "local",
    ) -> tuple[dict[str, Any], ProjectOperation, bool]:
        """``key`` overrides the derived identity for sources that know it.

        A Sheets row keeps the type the spreadsheets API reported for the cell
        ("1" text versus 1 number), which the local identity column alone loses.

        ``origin`` separates a local business write from a write the source
        itself produced. A pull materialises remote rows, so it must not queue
        them for an outbound push (design §11): only local changes are intents.
        """
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = SqlAlchemyProjectDataCatalog._existing(session, operation)
            if existing is not None:
                session.rollback()
                return _operation_result(existing), _operation(existing), True
            table = self._table(session, project_id, table_id, generation, True)
            fields = self._fields(session, table)
            canonical = self._validate(fields, values, True, origin)
            identity = table.identity
            if key is not None:
                pass
            elif identity.get("mode") == "system":
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
                if origin == "local":
                    enqueue_intent(session, table, key, row.content_revision, canonical)
                session.commit()
                return snapshot, done, False
            except IntegrityError as error:
                session.rollback()
                raise ProjectError(
                    "RECORD_ALREADY_EXISTS", "Record already exists", 409
                ) from error

    def create_many(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        expected: int,
        rows: list[tuple[str, dict[str, object]]],
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = SqlAlchemyProjectDataCatalog._existing(session, operation)
            if existing is not None:
                session.rollback()
                return _operation_result(existing), _operation(existing), True
            table = self._table(session, project_id, table_id, generation, True)
            if table.table_revision != expected:
                raise _conflict(expected, table.table_revision, "Table")
            fields = self._fields(session, table)
            errors: list[dict[str, Any]] = []
            prepared: list[DataRecordRow] = []
            seen: set[RecordKey] = set()
            now = datetime.now(UTC)
            for row_id, values in rows:
                canonical: dict[str, object] = {}
                before = len(errors)
                # Validate each cell separately so every invalid field is addressable.
                for field_id, value in values.items():
                    try:
                        canonical.update(
                            self._validate(fields, {field_id: value}, False)
                        )
                    except ProjectError as error:
                        errors.append(_row_error(row_id, field_id, error))
                for field in fields:
                    if field.required and field.id not in values:
                        errors.append(
                            _row_error(
                                row_id,
                                field.id,
                                ProjectError(
                                    "REQUIRED_FIELD_MISSING",
                                    "Required field is missing",
                                    422,
                                ),
                            )
                        )
                if len(errors) != before:
                    continue
                identity_id = table.identity.get("fieldId")
                try:
                    key = (
                        system_record_key()
                        if table.identity.get("mode") == "system"
                        else record_key(
                            canonical.get(identity_id)
                            if isinstance(identity_id, str)
                            else None
                        )
                    )
                except ProjectError as error:
                    errors.append(_row_error(row_id, identity_id, error))
                    continue
                if (
                    key in seen
                    or self._record(session, project_id, table_id, generation, key)
                    is not None
                ):
                    errors.append(
                        _row_error(
                            row_id,
                            identity_id,
                            ProjectError(
                                "RECORD_ALREADY_EXISTS", "Record already exists", 409
                            ),
                        )
                    )
                    continue
                seen.add(key)
                prepared.append(
                    DataRecordRow(
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
                )
            if errors:
                duplicate = all(
                    error["code"] == "RECORD_ALREADY_EXISTS" for error in errors
                )
                raise ProjectError(
                    "RECORD_ALREADY_EXISTS" if duplicate else "INVALID_RECORD_BATCH",
                    "Record batch was not saved",
                    409 if duplicate else 422,
                    {"rowErrors": errors},
                )
            result: dict[str, Any] = {
                "records": [
                    {"clientRowId": rid, "record": self._snapshot(row, fields)}
                    for (rid, _), row in zip(rows, prepared, strict=True)
                ]
            }
            done = _completed(operation, result)
            session.add_all(prepared)
            session.add(_operation_row(done))
            session.flush()
            for index, item in enumerate(result["records"], 1):
                evidence = _change(done, None, item["record"])
                evidence.sequence = index
                evidence.resource = _resource(item["record"]["ref"])
                session.add(evidence)
            session.commit()
            return result, done, False

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
        origin: str = "local",
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
            canonical = self._validate(fields, values, False, origin)
            before = self._snapshot(row, fields)
            old_values = row.values_json
            merged = {**old_values, **canonical}
            changed = merged != row.values_json
            if changed:
                row.values_json = merged
                row.content_revision += 1
                row.updated_at = datetime.now(UTC)
            snapshot = self._snapshot(row, fields)
            done = _completed(operation, snapshot)
            session.add(_operation_row(done))
            session.flush()
            if changed and origin == "local":
                enqueue_intent(session, table, key, row.content_revision, {
                    field_id: value for field_id, value in canonical.items()
                    if field_id not in old_values or old_values[field_id] != value
                })
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
            lease = active_record_lease(
                session, project_id, table_id, generation, key
            )
            if lease is not None:
                raise ProjectError(
                    "RECORD_IN_USE",
                    "Record is currently used by a running task",
                    409,
                    {"recordKeyType": key.type, "retryable": True},
                )
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
                        DataStatusRow.deleted.is_(False),
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
                DataTableRow.published.is_(True),
                DataTableRow.project_id == project_id,
                DataTableRow.id == table_id,
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
        if table.source_kind not in {"local", "excel", "sheets"}:
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
        fields: list[DataFieldRow],
        values: dict[str, object],
        creating: bool,
        origin: str = "local",
    ) -> dict[str, object]:
        """Check values against the field definitions.

        ``origin`` marks a write the source itself produced. A Sheets pull
        materialises the formula a row actually holds, which the local
        read-only rule exists to protect rather than to reject (DATA-SH-11).
        """
        by_id = {field.id: field for field in fields}
        unknown = set(values) - set(by_id)
        if unknown:
            raise ProjectError("UNKNOWN_FIELD", "Unknown fieldId", 422)
        result: dict[str, object] = {}
        for field_id, value in values.items():
            field = by_id[field_id]
            if origin != "source" and (not field.writable or field.formula):
                raise ProjectError("FIELD_NOT_WRITABLE", "Field is not writable", 422)
            definition = {
                "key": field.key, "name": field.name, "type": field.type,
                "required": field.required, "validation": field.validation,
            }
            try:
                result[field_id] = validate_value(definition, value)
            except ProjectError:
                if origin != "source":
                    raise
                # Sources may preserve a safe business scalar for diagnosis;
                # identity and unsafe wire values are checked before materialization.
                result[field_id] = validate_record_scalar(value)
        if creating and origin != "source":
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
        issue_fields = [{
            "fieldId": field.id, "key": field.key, "name": field.name,
            "type": field.type, "required": field.required, "validation": field.validation,
        } for field in fields]
        return {
            "ref": ref,
            "validationIssues": validation_issues(issue_fields, row.values_json),
            "values": [
                {
                    "fieldId": field.id,
                    "value": row.values_json[field.id],
                    "source": "formula" if field.formula else "local",
                    "readable": True,
                }
                for field in fields
                if field.id in row.values_json
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


def _row_error(
    row_id: str, field_id: str | None, error: ProjectError
) -> dict[str, Any]:
    return {
        "clientRowId": row_id,
        "fieldId": field_id,
        "code": error.code,
        "message": str(error),
    }
