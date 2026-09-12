from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.models import DataTable, table_to_dict
from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataGenerationRow,
    DataRecordRow,
    DataTableRow,
)


class SqlAlchemyProjectData:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def create(
        self, table: DataTable, operation: ProjectOperation
    ) -> tuple[dict, ProjectOperation, bool]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            session.execute(text("PRAGMA defer_foreign_keys=ON"))
            existing = self._existing_operation(session, operation)
            if existing is not None:
                session.rollback()
                return _operation_result(existing), _operation(existing), True
            self._guard_project_write(session, table.project_id)
            snapshot = table_to_dict(table)
            done = _completed(operation, snapshot)
            try:
                session.add(_table_row(table))
                session.add(
                    DataGenerationRow(
                        id=table.dataset_generation,
                        project_id=table.project_id,
                        table_id=table.table_id,
                        identity=table.identity,
                        source={"kind": "local"},
                        created_at=table.created_at,
                    )
                )
                session.add(_operation_row(done))
                session.flush()
                session.add(_change(table.project_id, done, None, snapshot))
                session.commit()
                return snapshot, done, False
            except IntegrityError as error:
                session.rollback()
                raise _name_conflict() from error

    def update(
        self,
        project_id: str,
        table_id: str,
        patch: dict,
        expected_revision: int,
        operation: ProjectOperation,
    ) -> tuple[dict, ProjectOperation, bool]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = self._existing_operation(session, operation)
            if existing is not None:
                session.rollback()
                return _operation_result(existing), _operation(existing), True
            self._guard_project_write(session, project_id)
            row = session.scalar(
                select(DataTableRow).where(
                    DataTableRow.project_id == project_id, DataTableRow.id == table_id
                )
            )
            if row is None:
                session.rollback()
                raise ProjectError("TABLE_NOT_FOUND", "Table was not found", 404)
            current = self._snapshot(session, row)
            if row.table_revision != expected_revision:
                current_revision = current["tableRevision"]
                session.rollback()
                raise ProjectError(
                    "REVISION_CONFLICT",
                    "Table was modified",
                    409,
                    {
                        "expectedRevision": expected_revision,
                        "currentRevision": current_revision,
                        "current": current,
                        "domainCode": "revision_conflict",
                        "retryable": False,
                    },
                )
            changed = _table(row, current["recordCount"]).patched(
                patch, datetime.now(UTC)
            )
            snapshot = table_to_dict(changed)
            done = _completed(operation, snapshot)
            try:
                row.name = changed.name
                row.name_key = changed.name.casefold()
                row.description = changed.description
                row.search_text = _search_text(changed.name, changed.description)
                row.table_revision = changed.table_revision
                row.updated_at = changed.updated_at
                session.add(_operation_row(done))
                session.flush()
                if snapshot != current:
                    session.add(_change(project_id, done, current, snapshot))
                session.commit()
                return snapshot, done, False
            except IntegrityError as error:
                session.rollback()
                raise _name_conflict() from error

    def get(self, project_id: str, table_id: str) -> dict | None:
        with self._session_factory() as session:
            self._guard_project_read(session, project_id)
            row = session.scalar(
                select(DataTableRow).where(
                    DataTableRow.project_id == project_id, DataTableRow.id == table_id
                )
            )
            return self._snapshot(session, row) if row is not None else None

    def list(
        self,
        project_id: str,
        q: str | None,
        source_kind: str | None,
        page: int,
        page_size: int,
        sort: str,
    ) -> tuple[list[dict], int]:
        with self._session_factory() as session:
            self._guard_project_read(session, project_id)
            query = select(DataTableRow).where(DataTableRow.project_id == project_id)
            if q and (needle := q.strip().casefold()):
                query = query.where(
                    DataTableRow.search_text.contains(needle, autoescape=True)
                )
            if source_kind is not None:
                query = query.where(DataTableRow.source_kind == source_kind)
            total = (
                session.scalar(select(func.count()).select_from(query.subquery())) or 0
            )
            orders = {
                "name": (DataTableRow.name_key, DataTableRow.id),
                "-name": (DataTableRow.name_key.desc(), DataTableRow.id),
                "updatedAt": (DataTableRow.updated_at, DataTableRow.id),
                "-updatedAt": (DataTableRow.updated_at.desc(), DataTableRow.id),
            }
            rows = session.scalars(
                query.order_by(*orders[sort])
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return [self._snapshot(session, row) for row in rows], total

    def _existing_operation(
        self, session: Session, incoming: ProjectOperation
    ) -> ProjectOperationRow | None:
        existing = session.scalar(
            select(ProjectOperationRow).where(
                ProjectOperationRow.idempotency_key == incoming.idempotency_key
            )
        )
        if existing is not None and (
            existing.kind != incoming.kind
            or existing.request_digest != incoming.request_digest
        ):
            raise ProjectError(
                "OPERATION_PAYLOAD_MISMATCH",
                "Idempotency key was used for another request",
                409,
                {"domainCode": "operation_payload_mismatch", "retryable": False},
            )
        return existing

    @staticmethod
    def _guard_project_read(session: Session, project_id: str) -> ProjectRow:
        project = session.get(ProjectRow, project_id)
        if project is None or project.lifecycle_state == "deleted":
            raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)
        return project

    @classmethod
    def _guard_project_write(cls, session: Session, project_id: str) -> ProjectRow:
        project = cls._guard_project_read(session, project_id)
        if project.lifecycle_state == "closing":
            raise ProjectError("PROJECT_CLOSING", "Project is closing", 423)
        if project.lifecycle_state != "active":
            raise ProjectError("LIFECYCLE_CONFLICT", "Project cannot be edited", 409)
        return project

    @staticmethod
    def _snapshot(session: Session, row: DataTableRow) -> dict:
        record_count = session.scalar(
            select(func.count())
            .select_from(DataRecordRow)
            .where(
                DataRecordRow.project_id == row.project_id,
                DataRecordRow.table_id == row.id,
                DataRecordRow.dataset_generation == row.current_generation,
                DataRecordRow.deleted.is_(False),
            )
        ) or 0
        return table_to_dict(_table(row, record_count))


def _table(row: DataTableRow, record_count: int) -> DataTable:
    return DataTable(
        project_id=row.project_id,
        table_id=row.id,
        name=row.name,
        description=row.description,
        source_kind=row.source_kind,
        dataset_generation=row.current_generation,
        table_revision=row.table_revision,
        identity=row.identity,
        slot_definitions=row.slot_definitions,
        created_at=_aware_required(row.created_at),
        updated_at=_aware_required(row.updated_at),
        record_count=record_count,
    )


def _table_row(value: DataTable) -> DataTableRow:
    return DataTableRow(
        id=value.table_id,
        project_id=value.project_id,
        name=value.name,
        name_key=value.name.casefold(),
        description=value.description,
        search_text=_search_text(value.name, value.description),
        source_kind=value.source_kind,
        current_generation=value.dataset_generation,
        table_revision=value.table_revision,
        identity=value.identity,
        slot_definitions=value.slot_definitions,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _completed(operation: ProjectOperation, result: dict) -> ProjectOperation:
    now = datetime.now(UTC)
    return replace(
        operation,
        status="succeeded",
        status_revision=2,
        result=result,
        updated_at=now,
        completed_at=now,
    )


def _operation_row(value: ProjectOperation) -> ProjectOperationRow:
    return ProjectOperationRow(
        id=value.operation_id,
        project_id=value.project_id,
        idempotency_key=value.idempotency_key,
        kind=value.kind,
        request_digest=value.request_digest,
        status=value.status,
        status_revision=value.status_revision,
        resource=value.resource,
        result=value.result,
        error=value.error,
        created_at=value.created_at,
        updated_at=value.updated_at,
        completed_at=value.completed_at,
    )


def _operation(row: ProjectOperationRow) -> ProjectOperation:
    return ProjectOperation(
        row.id,
        row.project_id,
        row.idempotency_key,
        row.kind,
        row.request_digest,
        row.status,
        row.status_revision,
        row.resource,
        row.result,
        row.error,
        _aware_required(row.created_at),
        _aware_required(row.updated_at),
        _aware(row.completed_at),
    )


def _operation_result(row: ProjectOperationRow) -> dict:
    if row.result is None:
        raise ProjectError("OPERATION_RESULT_UNKNOWN", "Operation has no result", 504)
    return row.result


def _change(
    project_id: str,
    operation: ProjectOperation,
    before: dict[str, Any] | None,
    after: dict[str, Any],
) -> DataChangeRow:
    return DataChangeRow(
        id=str(uuid4()),
        project_id=project_id,
        operation_id=operation.operation_id,
        sequence=1,
        resource=operation.resource,
        origin="manual",
        before=before,
        after=after,
        created_at=operation.completed_at,
    )


def _aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


def _search_text(name: str, description: str) -> str:
    return f"{name} {description}".casefold()


def _aware_required(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _name_conflict() -> ProjectError:
    return ProjectError(
        "TABLE_NAME_CONFLICT",
        "Table name is already in use",
        409,
        {
            "fields": {"name": "Table name is already in use"},
            "domainCode": "table_name_conflict",
            "retryable": False,
        },
    )
