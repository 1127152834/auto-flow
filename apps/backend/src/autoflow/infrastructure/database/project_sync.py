"""Persistence of Sheets connections, bindings and outbound sync facts.

Every state transition that a caller can race on is a conditional update inside
one short transaction; the network is never called from this module.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.projects.models import ProjectError

from .models import ProjectOperationRow
from .project_data_models import (
    DataFieldRow,
    DataGenerationRow,
    DataTableRow,
)
from .project_excel_common import instant, operation_view
from .project_sync_impacts import SqlAlchemySheetsImpacts
from .project_sync_models import (
    SheetsBindingRow,
    SheetsConnectionRow,
    SyncOperationRow,
    SyncRecordMarkRow,
)

_OPEN_STATUSES = ("pending", "sending", "verifying", "unknown", "paused")

# The project operation tells apart the commands the user ran; the sync row
# only needs the frozen `kind` vocabulary of the sync contract.
_SYNC_KINDS = {
    "inspectSheets": "binding",
    "changeSheetsBinding": "binding",
    "removeSheetsBinding": "binding",
    "syncPull": "pull",
    "syncPush": "push",
    "reconcileSync": "reconcile",
}

# Inspection and binding are configuration commands: their audit trail lives in
# the project operation, and they must not appear in the content sync queue,
# its badges or its operation listing.
CONTENT_KINDS = ("push", "pull", "reconcile")


def content_rows():
    """The rows that represent real content work, for the queue and its badges.

    A ``pull`` or ``reconcile`` row *is* the command, so it counts. A ``push``
    command also writes a paired row for itself, and that row is the aggregate
    of the batch rather than one record's change; only the rows with no
    ``operation_id`` are the queued local changes the user waits for.
    """
    return or_(
        SyncOperationRow.kind != "push",
        SyncOperationRow.operation_id.is_(None),
    )


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def precondition(code: str, message: str, **details: Any) -> ProjectError:
    return ProjectError("PRECONDITION_FAILED", message, 412, {"reason": code, **details})


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _required_table(session: Session, project: str, table_id: str) -> DataTableRow:
    row = session.get(DataTableRow, table_id)
    if row is None or row.project_id != project or not row.published:
        raise ProjectError("TABLE_NOT_FOUND", "Table was not found", 404)
    return row


def _guard_project_write(session: Session, project_id: str) -> None:
    from .project_data import SqlAlchemyProjectData

    SqlAlchemyProjectData._guard_project_write(session, project_id)


def connection_view(row: SheetsConnectionRow, credential_state: str) -> dict[str, Any]:
    return {
        "connectionId": row.id,
        "accountLabel": row.account_label,
        "credentialState": credential_state,
        "readable": row.readable,
        "writable": row.writable,
        "updatedAt": instant(_aware(row.updated_at) or datetime.now(UTC)),
    }


def binding_view(row: SheetsBindingRow) -> dict[str, Any]:
    return {
        "connectionId": row.connection_id,
        "spreadsheetId": row.spreadsheet_id,
        "sheetId": row.sheet_id,
        "bindingEpoch": row.binding_epoch,
        "identityStrategy": row.identity_strategy,
        "mapping": row.mapping,
        "syncPaused": row.sync_paused,
        "spreadsheetTitle": row.spreadsheet_title,
        "sheetName": row.sheet_name,
    }


def sync_view(row: SyncOperationRow, record_ref: dict[str, Any] | None) -> dict[str, Any]:
    view: dict[str, Any] = {
        "syncOperationId": row.id,
        "projectId": row.project_id,
        "tableId": row.table_id,
        "kind": row.kind,
        "bindingEpoch": row.binding_epoch,
        "status": row.status,
        "statusRevision": row.status_revision,
        "createdAt": instant(_aware(row.created_at) or datetime.now(UTC)),
        "updatedAt": instant(_aware(row.updated_at) or datetime.now(UTC)),
    }
    if record_ref is not None:
        view["record"] = record_ref
    if row.target_content_revision is not None:
        view["targetContentRevision"] = row.target_content_revision
    if row.operation_id is not None:
        view["operationId"] = row.operation_id
    if row.evidence is not None:
        view["evidence"] = row.evidence
    if row.error is not None:
        view["error"] = row.error
    return view


def _request_digest(project: str, table: str, kind: str, request: dict[str, Any]) -> str:
    return digest(
        {"projectId": project, "tableId": table, "kind": kind, "request": request}
    )


class SqlAlchemyProjectSync:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        impacts: SqlAlchemySheetsImpacts | None = None,
    ) -> None:
        self.sessions = sessions
        self.impacts = impacts or SqlAlchemySheetsImpacts(sessions)

    # ----------------------------------------------------------------- connections

    def require_project(self, project: str) -> None:
        """A directory for a project that does not exist is a 404, not an empty list."""
        from .project_data import SqlAlchemyProjectData

        with self.sessions() as session:
            SqlAlchemyProjectData._guard_project_read(session, project)

    def connections(self, project: str) -> list[SheetsConnectionRow]:
        with self.sessions() as session:
            rows = session.scalars(
                select(SheetsConnectionRow)
                .where(
                    SheetsConnectionRow.project_id == project,
                    SheetsConnectionRow.revoked_at.is_(None),
                )
                .order_by(SheetsConnectionRow.created_at, SheetsConnectionRow.id)
            ).all()
            for row in rows:
                session.expunge(row)
            return list(rows)

    def connection(self, project: str, connection_id: str) -> SheetsConnectionRow:
        with self.sessions() as session:
            row = session.get(SheetsConnectionRow, connection_id)
            if row is None or row.project_id != project or row.revoked_at is not None:
                raise ProjectError(
                    "SHEETS_CONNECTION_NOT_FOUND", "Google 连接不存在。", 404
                )
            session.expunge(row)
            return row

    def add_connection(
        self,
        project: str,
        *,
        account_label: str,
        credential_key: str,
        auth_method: str,
        state: str,
        readable: bool,
        writable: bool,
    ) -> SheetsConnectionRow:
        now = datetime.now(UTC)
        row = SheetsConnectionRow(
            id=str(uuid4()),
            project_id=project,
            account_label=account_label,
            credential_key=credential_key,
            auth_method=auth_method,
            state=state,
            readable=readable,
            writable=writable,
            created_at=now,
            updated_at=now,
            revoked_at=None,
        )
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            _guard_project_write(session, project)
            session.add(row)
            session.commit()
            session.expunge(row)
        return row

    def set_connection_state(
        self,
        project: str,
        connection_id: str,
        *,
        state: str,
        readable: bool,
        writable: bool,
    ) -> None:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(SheetsConnectionRow, connection_id)
            if row is None or row.project_id != project:
                raise ProjectError(
                    "SHEETS_CONNECTION_NOT_FOUND", "Google 连接不存在。", 404
                )
            row.state, row.readable, row.writable = state, readable, writable
            row.updated_at = datetime.now(UTC)
            session.commit()

    def revoke_connection(
        self,
        project: str,
        connection_id: str,
        mode: str,
        impact_revision: int,
    ) -> SheetsConnectionRow:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            _guard_project_write(session, project)
            self.impacts.require_disconnect(
                session, project, connection_id, mode, impact_revision
            )
            row = session.get(SheetsConnectionRow, connection_id)
            if row is None or row.project_id != project or row.revoked_at is not None:
                raise ProjectError(
                    "SHEETS_CONNECTION_NOT_FOUND", "Google 连接不存在。", 404
                )
            bound = session.scalar(
                select(SheetsBindingRow.table_id)
                .where(SheetsBindingRow.connection_id == connection_id)
                .limit(1)
            )
            if bound is not None:
                raise ProjectError(
                    "SHEETS_CONNECTION_IN_USE",
                    "仍有数据表绑定使用该连接，请先解除绑定。",
                    409,
                    {"tableId": bound},
                )
            now = datetime.now(UTC)
            row.revoked_at, row.state, row.updated_at = now, "missing", now
            session.commit()
            session.expunge(row)
            return row

    # -------------------------------------------------------------------- bindings

    def binding(self, project: str, table_id: str) -> dict[str, Any] | None:
        with self.sessions() as session:
            row = session.get(SheetsBindingRow, table_id)
            if row is None or row.project_id != project:
                return None
            return binding_view(row)

    def binding_row(self, session: Session, table_id: str) -> SheetsBindingRow | None:
        return session.get(SheetsBindingRow, table_id)

    def put_binding(
        self,
        project: str,
        table_id: str,
        *,
        connection_id: str,
        spreadsheet_id: str,
        sheet_id: int,
        spreadsheet_title: str,
        sheet_name: str,
        identity_strategy: dict[str, Any],
        mapping: list[dict[str, Any]],
        expected_table_revision: int,
        expected_binding_epoch: int | None,
        source: dict[str, Any],
        impact_revision: int,
        identity_field_id: str | None = None,
        formula_columns: list[str] | None = None,
    ) -> dict[str, Any]:
        change = {
            "connectionId": connection_id,
            "spreadsheetId": spreadsheet_id,
            "sheetId": sheet_id,
            "identityStrategy": identity_strategy,
            "mapping": mapping,
        }
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            # The new generation row and its copied fields are flushed together;
            # defer the composite check to commit so insert order cannot matter.
            session.execute(text("PRAGMA defer_foreign_keys=ON"))
            _guard_project_write(session, project)
            self.impacts.require_binding(
                session, project, table_id, change, impact_revision
            )
            table = _required_table(session, project, table_id)
            if table.table_revision != expected_table_revision:
                raise precondition(
                    "tableRevision",
                    "表结构已变化，请重新检查来源。",
                    tableRevision=table.table_revision,
                )
            connection = session.get(SheetsConnectionRow, connection_id)
            if (
                connection is None
                or connection.project_id != project
                or connection.revoked_at is not None
            ):
                raise ProjectError(
                    "SHEETS_CONNECTION_NOT_FOUND", "Google 连接不存在。", 404
                )
            existing = session.get(SheetsBindingRow, table_id)
            current_epoch = existing.binding_epoch if existing else None
            if current_epoch != expected_binding_epoch:
                raise precondition(
                    "bindingEpoch",
                    "绑定已被其他操作修改，请重新加载。",
                    bindingEpoch=current_epoch,
                )
            now = datetime.now(UTC)
            epoch = (current_epoch or 0) + 1
            generation = str(uuid4())
            formula_set = {column.upper() for column in formula_columns or []}
            formula_fields = {
                entry["fieldId"]
                for entry in mapping
                if entry["formula"] or str(entry["columnId"]).upper() in formula_set
            }
            # A formula column is read-only: it keeps the mapping honest too, so
            # a later push cannot queue a write that would replace the formula.
            mapping = [
                (
                    {**entry, "formula": True, "direction": "read"}
                    if entry["fieldId"] in formula_fields
                    else entry
                )
                for entry in mapping
            ]
            fields = session.scalars(
                select(DataFieldRow).where(
                    DataFieldRow.table_id == table_id,
                    DataFieldRow.dataset_generation == table.current_generation,
                )
            ).all()
            session.add(
                DataGenerationRow(
                    id=generation,
                    project_id=project,
                    table_id=table_id,
                    identity={
                        "mode": "field" if identity_field_id else "system",
                        "fieldId": identity_field_id,
                    },
                    source={"kind": "sheets", "spreadsheetId": spreadsheet_id, **source},
                    created_at=now,
                )
            )
            # The copied fields reference the generation by a composite key, so
            # the row has to exist before they are flushed.
            session.flush()
            for field in fields:
                session.add(
                    DataFieldRow(
                        id=field.id,
                        project_id=project,
                        table_id=table_id,
                        dataset_generation=generation,
                        key=field.key,
                        name=field.name,
                        type=field.type,
                        required=field.required,
                        writable=field.writable and field.id not in formula_fields,
                        formula=field.formula or field.id in formula_fields,
                        validation=field.validation,
                        field_revision=field.field_revision,
                        position=field.position,
                    )
                )
            row = existing or SheetsBindingRow(
                table_id=table_id,
                project_id=project,
                created_at=now,
                sync_paused=False,
            )
            row.connection_id = connection_id
            row.spreadsheet_id = spreadsheet_id
            row.sheet_id = sheet_id
            row.spreadsheet_title = spreadsheet_title
            row.sheet_name = sheet_name
            row.binding_epoch = epoch
            row.identity_strategy = identity_strategy
            row.mapping = mapping
            row.updated_at = now
            session.add(row)
            if current_epoch is not None:
                # A rebind points the table at a new target; unsent intents of
                # the retired epoch have no valid destination any more.
                self._retire_epoch(session, table_id, current_epoch, now)
            table.current_generation = generation
            table.source_kind = "sheets"
            table.identity = (
                {"mode": "field", "fieldId": identity_field_id}
                if identity_field_id
                else {"mode": "system"}
            )
            table.table_revision += 1
            table.updated_at = now
            session.commit()
            return binding_view(row)

    @staticmethod
    def _retire_epoch(
        session: Session, table_id: str, epoch: int, now: datetime
    ) -> None:
        stale = session.scalars(
            select(SyncOperationRow).where(
                SyncOperationRow.table_id == table_id,
                SyncOperationRow.kind == "push",
                SyncOperationRow.binding_epoch == epoch,
                SyncOperationRow.attempts == 0,
                SyncOperationRow.status.in_(("pending", "paused")),
            )
        ).all()
        for row in stale:
            row.status = "failed"
            row.status_revision += 1
            row.error = {
                "code": "SYNC_BINDING_CHANGED",
                "message": "来源绑定已更换，这条本地修改需要在新绑定下重新推送。",
            }
            row.updated_at = now

    def delete_binding(
        self,
        project: str,
        table_id: str,
        expected_table_revision: int,
        impact_revision: int,
    ) -> None:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            _guard_project_write(session, project)
            self.impacts.require_unbind(session, project, table_id, impact_revision)
            table = _required_table(session, project, table_id)
            if table.table_revision != expected_table_revision:
                raise precondition(
                    "tableRevision",
                    "表结构已变化，请重新加载。",
                    tableRevision=table.table_revision,
                )
            row = session.get(SheetsBindingRow, table_id)
            if row is None or row.project_id != project:
                raise ProjectError("SHEETS_BINDING_NOT_FOUND", "该表未绑定 Sheets。", 404)
            session.delete(row)
            table.source_kind = "unconfigured"
            table.table_revision += 1
            table.updated_at = datetime.now(UTC)
            session.commit()

    # ------------------------------------------------------------------ operations

    def replay(
        self, project: str, table: str, kind: str, key: str, request: dict[str, Any]
    ) -> dict[str, Any] | None:
        """The stored operation for an idempotency key, or ``None``.

        A retry of the same command has to answer with the original operation,
        so this lookup cannot sit behind a precondition the command itself
        moves: a reconcile advances the very status revision it quotes, and a
        client that lost the first response would otherwise see 412 instead of
        the decision it already made.
        """
        request_digest = _request_digest(project, table, kind, request)
        with self.sessions() as session:
            old = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == key
                )
            )
            if old is None:
                return None
            if (
                old.project_id != project
                or old.kind != kind
                or old.request_digest != request_digest
            ):
                raise ProjectError(
                    "OPERATION_PAYLOAD_MISMATCH", "原操作键已用于其他请求。", 409
                )
            return operation_view(old)

    def accept(
        self,
        *,
        project: str,
        table: str,
        kind: str,
        key: str,
        request: dict[str, Any],
        target: dict[str, Any],
        dedupe_key: str,
        binding_epoch: int,
        record_ref: dict[str, Any] | None = None,
        target_content_revision: int | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Create the paired project and sync operation rows, or replay the key."""
        request_digest = _request_digest(project, table, kind, request)
        now = datetime.now(UTC)
        operation_id = str(uuid4())
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            old = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == key
                )
            )
            if old is not None:
                if (
                    old.project_id != project
                    or old.kind != kind
                    or old.request_digest != request_digest
                ):
                    raise ProjectError(
                        "OPERATION_PAYLOAD_MISMATCH", "原操作键已用于其他请求。", 409
                    )
                sync = session.get(SyncOperationRow, old.id)
                assert sync is not None
                return (
                    {
                        "operation": operation_view(old),
                        "sync": sync_view(sync, _record_ref(sync)),
                    },
                    True,
                )
            _guard_project_write(session, project)
            operation = ProjectOperationRow(
                id=operation_id,
                project_id=project,
                idempotency_key=key,
                kind=kind,
                request_digest=request_digest,
                status="running",
                status_revision=1,
                resource={"type": "table", "projectId": project, "tableId": table},
                result=None,
                error=None,
                created_at=now,
                updated_at=now,
                completed_at=None,
            )
            sync = SyncOperationRow(
                id=operation_id,
                project_id=project,
                table_id=table,
                operation_id=operation_id,
                kind=_SYNC_KINDS.get(kind, kind),
                record_key_type=record_ref["recordKey"]["type"] if record_ref else None,
                record_key=record_ref["recordKey"]["value"] if record_ref else None,
                binding_epoch=binding_epoch,
                target_content_revision=target_content_revision,
                status="pending",
                status_revision=1,
                dedupe_key=dedupe_key,
                request=request,
                target=target,
                evidence=None,
                attempts=0,
                error=None,
                created_at=now,
                updated_at=now,
                next_attempt_at=None,
                confirmed_at=None,
            )
            session.add_all((operation, sync))
            session.commit()
            return (
                {
                    "operation": operation_view(operation),
                    "sync": sync_view(sync, record_ref),
                },
                False,
            )

    def sync_operation(self, table: str, sync_operation_id: str) -> dict[str, Any]:
        with self.sessions() as session:
            row = session.get(SyncOperationRow, sync_operation_id)
            if row is None or row.table_id != table:
                raise ProjectError(
                    "SYNC_OPERATION_NOT_FOUND", "同步操作不存在。", 404
                )
            return sync_view(row, _record_ref(row))

    def sync_operation_by_id(self, sync_operation_id: str) -> dict[str, Any]:
        with self.sessions() as session:
            row = session.get(SyncOperationRow, sync_operation_id)
            if row is None:
                raise ProjectError("SYNC_OPERATION_NOT_FOUND", "同步操作不存在。", 404)
            return sync_view(row, _record_ref(row))

    def summary_for_table(self, project: str, table: str) -> dict[str, Any]:
        with self.sessions() as session:
            binding = session.get(SheetsBindingRow, table)
            if binding is None or binding.project_id != project:
                raise ProjectError("SHEETS_BINDING_NOT_FOUND", "该表未绑定 Sheets。", 404)
            return self.summary(session, table)

    def sync_operations(
        self, table: str, status: str | None, page: int, page_size: int
    ) -> dict[str, Any]:
        with self.sessions() as session:
            scope = (
                SyncOperationRow.table_id == table,
                SyncOperationRow.kind.in_(CONTENT_KINDS),
                # Only the queued local changes are listed here. A pull or
                # reconcile row *is* its command, and a push command owns the
                # queue it drains; both are readable as project operations.
                SyncOperationRow.operation_id.is_(None),
            )
            query = select(SyncOperationRow).where(*scope)
            count = select(func.count()).select_from(SyncOperationRow).where(*scope)
            if status is not None:
                query = query.where(SyncOperationRow.status == status)
                count = count.where(SyncOperationRow.status == status)
            total = session.scalar(count) or 0
            rows = session.scalars(
                query.order_by(SyncOperationRow.created_at.desc(), SyncOperationRow.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return {
                "items": [sync_view(row, _record_ref(row)) for row in rows],
                "page": page,
                "pageSize": page_size,
                "total": total,
            }

    def transition(
        self,
        sync_operation_id: str,
        *,
        status: str,
        expected_status_revision: int | None = None,
        evidence: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        attempt: bool = False,
        keep_evidence: bool = False,
        keep_error: bool = False,
    ) -> dict[str, Any]:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(SyncOperationRow, sync_operation_id)
            if row is None:
                raise ProjectError("SYNC_OPERATION_NOT_FOUND", "同步操作不存在。", 404)
            if (
                expected_status_revision is not None
                and row.status_revision != expected_status_revision
            ):
                raise precondition(
                    "statusRevision",
                    "该操作已被其他请求更新，请重新加载。",
                    statusRevision=row.status_revision,
                )
            now = datetime.now(UTC)
            row.status = status
            row.status_revision += 1
            row.updated_at = now
            if attempt:
                row.attempts += 1
            if evidence is not None:
                row.evidence = evidence
            elif not keep_evidence:
                row.evidence = None
            if error is not None:
                row.error = error
            elif not keep_error:
                row.error = None
            if status == "confirmed":
                row.confirmed_at = now
            elif status == "failed":
                row.next_attempt_at = None
            operation = session.get(ProjectOperationRow, row.operation_id or row.id)
            if operation is not None:
                operation.status = _operation_status(status)
                operation.status_revision += 1
                operation.updated_at = now
                operation.error = row.error
                if status in ("confirmed", "failed"):
                    operation.completed_at = now
            session.commit()
            return sync_view(row, _record_ref(row))

    def accept_project_operation(
        self,
        *,
        project: str,
        kind: str,
        key: str,
        request: dict[str, Any],
        resource: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        """Project scoped operation that has no table and no sync row."""
        request_digest = digest({"projectId": project, "kind": kind, "request": request})
        now = datetime.now(UTC)
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            old = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == key
                )
            )
            if old is not None:
                if (
                    old.project_id != project
                    or old.kind != kind
                    or old.request_digest != request_digest
                ):
                    raise ProjectError(
                        "OPERATION_PAYLOAD_MISMATCH", "原操作键已用于其他请求。", 409
                    )
                return operation_view(old), True
            _guard_project_write(session, project)
            operation = ProjectOperationRow(
                id=str(uuid4()),
                project_id=project,
                idempotency_key=key,
                kind=kind,
                request_digest=request_digest,
                status="running",
                status_revision=1,
                resource=resource,
                result=None,
                error=None,
                created_at=now,
                updated_at=now,
                completed_at=None,
            )
            session.add(operation)
            session.commit()
            return operation_view(operation), False

    def finish_operation(
        self, operation_id: str, result: dict[str, Any], status: str = "succeeded"
    ) -> None:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            operation = session.get(ProjectOperationRow, operation_id)
            if operation is None:
                return
            now = datetime.now(UTC)
            operation.status = status
            operation.status_revision += 1
            operation.result = result
            operation.updated_at = now
            operation.completed_at = now
            session.commit()

    def complete(
        self, sync_operation_id: str, result: dict[str, Any], status: str = "succeeded"
    ) -> None:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            sync = session.get(SyncOperationRow, sync_operation_id)
            operation = (
                session.get(ProjectOperationRow, sync.operation_id)
                if sync is not None and sync.operation_id is not None
                else None
            )
            if operation is None:
                return
            now = datetime.now(UTC)
            operation.status = status
            operation.status_revision += 1
            operation.result = result
            operation.updated_at = now
            operation.completed_at = now
            session.commit()

    def fail_operation(self, sync_operation_id: str, error: dict[str, Any]) -> None:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            sync = session.get(SyncOperationRow, sync_operation_id)
            operation = (
                session.get(ProjectOperationRow, sync.operation_id)
                if sync is not None and sync.operation_id
                else None
            )
            if operation is None:
                return
            now = datetime.now(UTC)
            operation.status = "failed"
            operation.status_revision += 1
            operation.error = error
            operation.updated_at = now
            operation.completed_at = now
            session.commit()

    def operation_view(self, operation_id: str) -> dict[str, Any]:
        """Read back either half of the pair; project scoped commands have no sync row."""
        with self.sessions() as session:
            sync = session.get(SyncOperationRow, operation_id)
            project_id = sync.operation_id or sync.id if sync is not None else operation_id
            operation = session.get(ProjectOperationRow, project_id)
            if operation is None:
                raise ProjectError("SYNC_OPERATION_NOT_FOUND", "同步操作不存在。", 404)
            return operation_view(operation)

    # ----------------------------------------------------------------------- queue

    def pending(self, table: str, limit: int) -> list[SyncOperationRow]:
        """Unsent intents for the binding epoch that currently owns the table.

        A rebind retires the previous epoch, so its leftover intents must never
        be replayed against the new target. A push command writes its own paired
        row, and only rows without an ``operation_id`` are local-change intents.
        """
        with self.sessions() as session:
            binding = session.get(SheetsBindingRow, table)
            if binding is None:
                return []
            rows = session.scalars(
                select(SyncOperationRow)
                .where(
                    SyncOperationRow.table_id == table,
                    SyncOperationRow.kind == "push",
                    SyncOperationRow.operation_id.is_(None),
                    SyncOperationRow.binding_epoch == binding.binding_epoch,
                    SyncOperationRow.status == "pending",
                )
                .order_by(SyncOperationRow.created_at, SyncOperationRow.id)
                .limit(limit)
            ).all()
            for row in rows:
                session.expunge(row)
            return list(rows)

    @staticmethod
    def summary(session: Session, table: str) -> dict[str, Any]:
        binding = session.get(SheetsBindingRow, table)
        if binding is None:
            return {"status": "notApplicable", "pendingCount": 0, "unknownCount": 0}
        counts: dict[str, int] = {
            row[0]: row[1]
            for row in session.execute(
                select(SyncOperationRow.status, func.count())
                .where(
                    SyncOperationRow.table_id == table,
                    SyncOperationRow.kind.in_(CONTENT_KINDS),
                    content_rows(),
                )
                .group_by(SyncOperationRow.status)
            ).all()
        }
        last = session.scalar(
            select(func.max(SyncOperationRow.confirmed_at)).where(
                SyncOperationRow.table_id == table,
                SyncOperationRow.kind.in_(CONTENT_KINDS),
                content_rows(),
            )
        )
        pending = sum(counts.get(state, 0) for state in ("pending", "paused"))
        unknown = sum(counts.get(state, 0) for state in ("sending", "verifying", "unknown"))
        summary: dict[str, Any] = {
            "status": _summary_status(binding, counts),
            "pendingCount": pending,
            "unknownCount": unknown,
        }
        if last is not None:
            summary["lastConfirmedAt"] = instant(_aware(last) or datetime.now(UTC))
        return summary

    def set_paused(self, project: str, table: str, paused: bool, expected_epoch: int) -> dict:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(SheetsBindingRow, table)
            if row is None or row.project_id != project:
                raise ProjectError("SHEETS_BINDING_NOT_FOUND", "该表未绑定 Sheets。", 404)
            if row.binding_epoch != expected_epoch:
                raise precondition(
                    "bindingEpoch",
                    "绑定已变化，请重新加载。",
                    bindingEpoch=row.binding_epoch,
                )
            row.sync_paused = paused
            now = datetime.now(UTC)
            row.updated_at = now
            if not paused:
                # DATA-LIFE-05: resuming only reopens the queue. Intents that
                # piled up while paused become sendable again; nothing else is
                # replayed or rewritten.
                for intent in session.scalars(
                    select(SyncOperationRow).where(
                        SyncOperationRow.table_id == table,
                        SyncOperationRow.status == "paused",
                    )
                ).all():
                    intent.status = "pending"
                    intent.status_revision += 1
                    intent.updated_at = now
            session.commit()
            return binding_view(row)

    # ----------------------------------------------------------------------- marks

    def marks(self, table: str) -> dict[tuple[str, str], SyncRecordMarkRow]:
        with self.sessions() as session:
            rows = session.scalars(
                select(SyncRecordMarkRow).where(SyncRecordMarkRow.table_id == table)
            ).all()
            for row in rows:
                session.expunge(row)
            return {(row.record_key_type, row.record_key): row for row in rows}

    def mark(
        self,
        table: str,
        key_type: str,
        key: str,
        *,
        remote_missing: bool,
        observed: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(UTC)
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(SyncRecordMarkRow, (table, key_type, key))
            if row is None:
                row = SyncRecordMarkRow(
                    table_id=table,
                    record_key_type=key_type,
                    record_key=key,
                    remote_missing=remote_missing,
                    observed=observed,
                    remote_seen_at=None if remote_missing else now,
                    updated_at=now,
                )
            else:
                row.remote_missing = remote_missing
                row.observed = observed
                row.remote_seen_at = None if remote_missing else now
                row.updated_at = now
            session.add(row)
            session.commit()


def _operation_status(status: str) -> str:
    if status == "confirmed":
        return "succeeded"
    if status == "failed":
        return "failed"
    if status in ("sending", "verifying", "unknown"):
        return "reconciling"
    return "running"


def _summary_status(binding: SheetsBindingRow, counts: dict[str, int]) -> str:
    if binding.sync_paused:
        return "paused"
    for state in ("unknown", "verifying", "sending"):
        if counts.get(state, 0):
            return state
    for state in ("failed", "pending"):
        if counts.get(state, 0):
            return state
    if counts.get("confirmed", 0):
        return "confirmed"
    return "idle"


def _record_ref(row: SyncOperationRow) -> dict[str, Any] | None:
    if row.record_key_type is None or row.record_key is None:
        return None
    generation = row.request.get("datasetGeneration")
    return {
        "projectId": row.project_id,
        "tableId": row.table_id,
        "datasetGeneration": generation,
        "recordKey": {"type": row.record_key_type, "value": row.record_key},
    }


def enqueue_intent(
    session: Session, table: DataTableRow, key: RecordKey, revision: int,
    values: dict[str, object],
) -> None:
    """Register one local content change as a pending outbound intent.

    Called inside the same transaction as the content write, so a table that is
    not bound, or a write that rolls back, never leaves a phantom intent.

    Unsent changes to the same record merge into the newest target revision
    (DATA-SYNC / rules §11.1 #2): the queue carries one entry per record per
    binding epoch, so a second edit cannot ship the first edit's stale value or
    inflate the queue with duplicates. Anything already attempted keeps its own
    row and its own evidence, because a sent version can never be taken back.
    """
    binding = session.get(SheetsBindingRow, table.id)
    if binding is None:
        return
    now = datetime.now(UTC)
    target = {
        "spreadsheetId": binding.spreadsheet_id,
        "sheetId": binding.sheet_id,
        "sheetName": binding.sheet_name,
    }
    request = {
        "datasetGeneration": table.current_generation,
        "contentRevision": revision,
        "values": values,
    }
    open_row = session.scalar(
        select(SyncOperationRow).where(
            SyncOperationRow.table_id == table.id,
            SyncOperationRow.kind == "push",
            SyncOperationRow.binding_epoch == binding.binding_epoch,
            SyncOperationRow.record_key_type == key.type,
            SyncOperationRow.record_key == key.value,
            SyncOperationRow.attempts == 0,
            SyncOperationRow.status.in_(("pending", "paused")),
        )
    )
    if open_row is not None and isinstance(open_row.request.get("values"), dict):
        request["values"] = {**open_row.request["values"], **values}
        open_row.target_content_revision = revision
        open_row.status_revision += 1
        open_row.request = request
        open_row.target = target
        open_row.dedupe_key = f"{binding.binding_epoch}:{key.type}:{key.value}:{revision}"
        open_row.updated_at = now
        return
    dedupe = f"{binding.binding_epoch}:{key.type}:{key.value}:{revision}"
    exists = session.scalar(
        select(SyncOperationRow.id).where(
            SyncOperationRow.table_id == table.id,
            SyncOperationRow.dedupe_key == dedupe,
        )
    )
    if exists is not None:
        return
    session.add(
        SyncOperationRow(
            id=str(uuid4()),
            project_id=table.project_id,
            table_id=table.id,
            operation_id=None,
            kind="push",
            record_key_type=key.type,
            record_key=key.value,
            binding_epoch=binding.binding_epoch,
            target_content_revision=revision,
            status="paused" if binding.sync_paused else "pending",
            status_revision=1,
            dedupe_key=dedupe,
            request=request,
            target=target,
            evidence=None,
            attempts=0,
            error=None,
            created_at=now,
            updated_at=now,
            next_attempt_at=None,
            confirmed_at=None,
        )
    )
