"""Persistence of Sheets connections, bindings and outbound sync facts.

Every state transition that a caller can race on is a conditional update inside
one short transaction; the network is never called from this module.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.identity import RecordKey, RecordKeyType
from autoflow.domain.projects.models import ProjectError

from .models import ProjectOperationRow, ProjectRow
from .project_data_models import (
    DataFieldRow,
    DataGenerationRow,
    DataRecordRow,
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
from .project_sync_sends import require_source_idle

_OPEN_STATUSES = ("pending", "sending", "verifying", "unknown", "paused")

# The project operation tells apart the commands the user ran; the sync row
# only needs the frozen `kind` vocabulary of the sync contract.
_SYNC_KINDS = {
    "inspectSheets": "binding",
    "changeSheetsBinding": "binding",
    "initializeSheetsIdentity": "systemIdentity",
    "createSheetsColumn": "column",
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
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def precondition(code: str, message: str, **details: Any) -> ProjectError:
    return ProjectError(
        "PRECONDITION_FAILED", message, 412, {"reason": code, **details}
    )


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


def sync_view(
    row: SyncOperationRow, record_ref: dict[str, Any] | None
) -> dict[str, Any]:
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


def _request_digest(
    project: str, table: str, kind: str, request: dict[str, Any]
) -> str:
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
        initialization_operation_id: str | None = None,
        system_identity_plan: dict[str, Any] | None = None,
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
                session, project, table_id, change, impact_revision, own=initialization_operation_id
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
            original_generation = table.current_generation
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
                    source={
                        "kind": "sheets",
                        "spreadsheetId": spreadsheet_id,
                        **source,
                    },
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
            row.identity_verification = {"systemIdentity": {key: system_identity_plan[key] for key in ("sheetId", "columnIndex", "owner")}} if system_identity_plan else None
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
            if initialization_operation_id is not None:
                initialized = session.get(SyncOperationRow, initialization_operation_id)
                operation = session.get(ProjectOperationRow, initialization_operation_id)
                if initialized is None or operation is None or initialized.request.get("datasetGeneration") != original_generation or initialized.project_id != project or initialized.table_id != table_id or initialized.kind != "systemIdentity" or initialized.status != "verifying":
                    raise precondition("identityPlan", "初始化事实已变化，请核验原操作。")
                initialized.status = "confirmed"
                initialized.status_revision += 1
                initialized.confirmed_at = initialized.updated_at = now
                operation.status = "succeeded"
                operation.status_revision += 1
                operation.result = binding_view(row)
                operation.completed_at = operation.updated_at = now
                operation.error = None
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
                raise ProjectError(
                    "SHEETS_BINDING_NOT_FOUND", "该表未绑定 Sheets。", 404
                )
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
            project_row = session.get(ProjectRow, project)
            if not (kind == "reconcileSync" and project_row is not None and project_row.lifecycle_state == "closing"):
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

    def freeze_identity(self, operation_id: str, plan: dict[str, Any], *, retry: bool = False, confirmation: dict[str, Any] | None = None) -> None:
        """Persist generated UUIDs and claim the send before touching Google."""
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(SyncOperationRow, operation_id)
            assert row is not None and row.kind == "systemIdentity"
            if retry:
                if row.status != "failed" or (row.error or {}).get("unsent") is not True or row.request.get("initialization") != plan:
                    raise precondition("identityPlan", "只有证明未发送的原计划允许重试。")
            elif row.attempts or row.status != "pending" or "initialization" in row.request:
                raise precondition("identityPlan", "原初始化计划已登记，请核验原操作。")
            request = row.request
            confirmation = confirmation or request
            require_source_idle(session, request["spreadsheetId"], own=row.id, structural=True)
            _guard_project_write(session, row.project_id)
            table = _required_table(session, row.project_id, row.table_id)
            binding = session.get(SheetsBindingRow, row.table_id)
            if table.table_revision != confirmation["expectedTableRevision"] or (binding.binding_epoch if binding else None) != request["expectedBindingEpoch"]:
                raise precondition("bindingEpoch", "表或绑定已变化，请重新确认。")
            new_column = request["identityStrategy"]["columnId"]
            if any((len(item["columnId"]), item["columnId"]) >= (len(new_column), new_column) for item in request["mapping"]):
                raise ProjectError("SHEETS_COLUMN_POSITION_IN_USE", "新身份列必须位于所有映射列之后。", 409)
            for peer in session.scalars(select(SheetsBindingRow).where(
                SheetsBindingRow.spreadsheet_id == request["spreadsheetId"], SheetsBindingRow.sheet_id == request["sheetId"],
            )):
                columns = [entry["columnId"] for entry in peer.mapping] + [peer.identity_strategy.get("columnId", "")]
                if any((len(column), column) >= (len(new_column), new_column) for column in columns):
                    raise ProjectError("SHEETS_COLUMN_POSITION_IN_USE", "插入位置会移动已有绑定列，请选择所有已映射列之后的新列。", 409)
            change = {key: request[key] for key in ("connectionId", "spreadsheetId", "sheetId", "identityStrategy", "mapping")}
            self.impacts.require_binding(session, row.project_id, row.table_id, change, confirmation["impactRevision"], own=row.id)
            if retry and table.current_generation != request.get("datasetGeneration"):
                raise precondition("datasetGeneration", "原初始化数据代次已变化。")
            row.request = {**request, "initialization": plan, "datasetGeneration": table.current_generation}
            row.status, row.attempts = "sending", row.attempts + 1
            row.error = None
            accepted = session.get(ProjectOperationRow, operation_id)
            assert accepted is not None
            accepted.status, accepted.error, accepted.completed_at = "running", None, None
            accepted.status_revision += 1
            accepted.updated_at = datetime.now(UTC)
            row.status_revision += 1
            row.updated_at = datetime.now(UTC)
            session.commit()

    def freeze_column(self, operation_id: str, plan: dict[str, Any], *, retry: bool = False, confirmation: dict[str, Any] | None = None) -> None:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(SyncOperationRow, operation_id)
            assert row is not None and row.kind == "column"
            if retry:
                if row.status != "failed" or (row.error or {}).get("unsent") is not True or (row.error or {}).get("code") == "SYNC_ABANDONED" or row.request.get("columnPlan") != plan:
                    raise precondition("columnPlan", "仅未发送的原计划可重试。")
            elif row.status != "pending" or row.attempts:
                raise precondition("columnPlan", "原计划已登记，请核验。")
            request = row.request
            change = {key: value for key, value in request.items() if key not in {"impactRevision", "columnPlan"}}
            confirmed = confirmation or request
            _guard_project_write(session, row.project_id)
            table = _required_table(session, row.project_id, row.table_id)
            if table.table_revision != confirmed["expectedTableRevision"]:
                raise precondition("tableRevision", "表结构已变化，请重新确认。")
            require_source_idle(session, request["spreadsheetId"], own=row.id, structural=True)
            self.impacts.require_column(session, row.project_id, row.table_id, change, confirmed["impactRevision"], own=row.id)
            for peer in session.scalars(select(SheetsBindingRow).where(SheetsBindingRow.spreadsheet_id == request["spreadsheetId"], SheetsBindingRow.sheet_id == request["sheetId"])):
                if any(entry["columnId"] == plan["columnId"] for entry in peer.mapping) or peer.identity_strategy.get("columnId") == plan["columnId"]:
                    raise ProjectError("SHEETS_COLUMN_POSITION_IN_USE", "目标列已有映射，不能接管。", 409)
            row.request = {**request, "columnPlan":plan}
            row.status, row.attempts, row.error = "sending", row.attempts + 1, None
            row.status_revision += 1
            row.updated_at = datetime.now(UTC)
            operation = session.get(ProjectOperationRow, row.id)
            assert operation is not None
            operation.status, operation.error, operation.completed_at = "running", None, None
            operation.status_revision += 1
            session.commit()

    def column_operation(self, project: str, table: str, operation_id: str) -> SyncOperationRow:
        with self.sessions() as session:
            row = session.get(SyncOperationRow, operation_id)
            if row is None or row.project_id != project or row.table_id != table or row.kind != "column":
                raise ProjectError("SYNC_OPERATION_NOT_FOUND", "来源列操作不存在。", 404)
            session.expunge(row)
            return row

    def cancel_column(self, project: str, table: str, operation_id: str, revision: int) -> dict[str, Any]:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            _guard_project_write(session, project)
            row = session.get(SyncOperationRow, operation_id)
            if row is None or row.project_id != project or row.table_id != table or row.kind != "column":
                raise ProjectError("SYNC_OPERATION_NOT_FOUND", "来源列操作不存在。", 404)
            if row.status_revision != revision:
                raise precondition("statusRevision", "原操作状态已变化。")
            if not ((row.status in {"pending", "failed"} and row.attempts == 0) or (row.status == "failed" and (row.error or {}).get("unsent") is True)):
                raise ProjectError("SYNC_NOT_ABANDONABLE", "已发送或未知结果只能核验，不能假定未创建。", 409)
            now = datetime.now(UTC)
            row.status, row.updated_at = "failed", now
            row.status_revision += 1
            row.error = {"code":"SYNC_ABANDONED", "message":"用户取消原未发送列计划；本地字段和值保留。", "unsent":True, "retryable":False}
            operation = session.get(ProjectOperationRow, row.id)
            assert operation is not None
            operation.status, operation.error = "failed", row.error
            operation.status_revision += 1
            operation.updated_at = operation.completed_at = now
            session.commit()
            return sync_view(row, None)

    def publish_column(self, operation_id: str, confirmation: dict[str, Any]) -> dict[str, Any]:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(SyncOperationRow, operation_id)
            assert row is not None
            if row.status != "verifying":
                raise precondition("statusRevision", "原来源列状态已变化。")
            request, plan = row.request, row.request["columnPlan"]
            _guard_project_write(session, row.project_id)
            table = _required_table(session, row.project_id, row.table_id)
            if table.table_revision != confirmation["expectedTableRevision"]:
                raise precondition("tableRevision", "表结构已变化，请重新确认。")
            change = {key: value for key, value in request.items() if key not in {"impactRevision", "columnPlan"}}
            self.impacts.require_column(session, row.project_id, row.table_id, change, confirmation["impactRevision"], own=row.id)
            binding = session.get(SheetsBindingRow, row.table_id)
            assert binding is not None
            binding.mapping = [*binding.mapping, {"fieldId":request["fieldId"], "columnId":plan["columnId"], "direction":"both", "formula":False}]
            proof = binding.identity_verification or {}
            binding.identity_verification = {**proof, "sourceColumns": {**proof.get("sourceColumns", {}), request["fieldId"]:plan}}
            now = datetime.now(UTC)
            binding.updated_at = table.updated_at = now
            table.table_revision += 1
            row.status, row.confirmed_at, row.updated_at = "confirmed", now, now
            row.status_revision += 1
            row.error = None
            for record in session.scalars(select(DataRecordRow).where(DataRecordRow.dataset_generation == table.current_generation, DataRecordRow.deleted.is_(False))):
                if request["fieldId"] in record.values_json:
                    enqueue_intent(session, table, RecordKey(cast(RecordKeyType, record.key_type), record.key_value), record.content_revision, {request["fieldId"]:record.values_json[request["fieldId"]]}, dependency_id=row.id)
            operation = session.get(ProjectOperationRow, row.id)
            assert operation is not None
            operation.status, operation.result, operation.error = "succeeded", binding_view(binding), None
            operation.status_revision += 1
            operation.completed_at = operation.updated_at = now
            session.commit()
            return operation.result

    def system_identity_plan(self, project: str, table: str, epoch: int) -> dict[str, Any]:
        with self.sessions() as session:
            row = session.get(SheetsBindingRow, table)
            if row is None or row.project_id != project or row.binding_epoch != epoch:
                raise ProjectError("SHEETS_IDENTITY_UNVERIFIED", "系统身份绑定已变化。", 409)
            plan = (row.identity_verification or {}).get("systemIdentity")
            if not plan:
                raise ProjectError("SHEETS_IDENTITY_UNVERIFIED", "系统身份缺少原初始化归属证据。", 409)
            return plan

    def known_system_identity(self, spreadsheet: str, sheet: int, column: str) -> dict[str, Any]:
        with self.sessions() as session:
            for row in session.scalars(select(SyncOperationRow).where(SyncOperationRow.kind == "systemIdentity", SyncOperationRow.status == "confirmed").order_by(SyncOperationRow.created_at.desc())):
                if row.target.get("spreadsheetId") == spreadsheet and row.target.get("sheetId") == sheet and row.request["identityStrategy"]["columnId"] == column:
                    return row.request["initialization"]
        raise ProjectError("SHEETS_IDENTITY_INITIALIZATION_REQUIRED", "该列没有已确认的系统归属，请先完成原初始化。", 409)

    def identity_operation(self, project: str, table: str, operation_id: str) -> SyncOperationRow:
        with self.sessions() as session:
            row = session.get(SyncOperationRow, operation_id)
            if row is None or row.project_id != project or row.table_id != table or row.kind != "systemIdentity":
                raise ProjectError("SYNC_OPERATION_NOT_FOUND", "初始化操作不存在。", 404)
            session.expunge(row)
            return row

    def sync_operation(self, table: str, sync_operation_id: str) -> dict[str, Any]:
        with self.sessions() as session:
            row = session.get(SyncOperationRow, sync_operation_id)
            if row is None or row.table_id != table:
                raise ProjectError("SYNC_OPERATION_NOT_FOUND", "同步操作不存在。", 404)
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
                raise ProjectError(
                    "SHEETS_BINDING_NOT_FOUND", "该表未绑定 Sheets。", 404
                )
            return self.summary(session, table)

    def sync_operations(
        self, table: str, status: str | None, page: int, page_size: int, *, kind: str | None = None
    ) -> dict[str, Any]:
        with self.sessions() as session:
            scope = (
                SyncOperationRow.table_id == table,
                SyncOperationRow.kind == kind if kind else SyncOperationRow.kind.in_(CONTENT_KINDS),
                # Only the queued local changes are listed here. A pull or
                # reconcile row *is* its command, and a push command owns the
                # queue it drains; both are readable as project operations.
                SyncOperationRow.operation_id.is_not(None) if kind else SyncOperationRow.operation_id.is_(None),
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
            if status == "sending" and row.kind == "push":
                for dependency in row.request.get("columnDependencies", []):
                    column = session.get(SyncOperationRow, dependency)
                    if column is None or column.status != "confirmed" or column.table_id != row.table_id or column.binding_epoch != row.binding_epoch:
                        raise precondition("columnDependency", "来源列尚未确认，不能推送值。")
                require_source_idle(session, str(row.target.get("spreadsheetId")))
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
        request_digest = digest(
            {"projectId": project, "kind": kind, "request": request}
        )
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
            project_id = (
                sync.operation_id or sync.id if sync is not None else operation_id
            )
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
        unknown = sum(
            counts.get(state, 0) for state in ("sending", "verifying", "unknown")
        )
        summary: dict[str, Any] = {
            "status": _summary_status(binding, counts),
            "pendingCount": pending,
            "unknownCount": unknown,
        }
        if last is not None:
            summary["lastConfirmedAt"] = instant(_aware(last) or datetime.now(UTC))
        # Read freshness must not move forward on a push, failed attempt or old binding.
        pulled = session.scalar(
            select(func.max(SyncOperationRow.confirmed_at)).where(
                SyncOperationRow.table_id == table,
                SyncOperationRow.binding_epoch == binding.binding_epoch,
                SyncOperationRow.kind == "pull",
                SyncOperationRow.status == "confirmed",
            )
        )
        if pulled is not None:
            summary["lastPulledAt"] = instant(_aware(pulled) or datetime.now(UTC))
        return summary

    def set_paused(
        self, project: str, table: str, paused: bool, expected_epoch: int
    ) -> dict:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(SheetsBindingRow, table)
            if row is None or row.project_id != project:
                raise ProjectError(
                    "SHEETS_BINDING_NOT_FOUND", "该表未绑定 Sheets。", 404
                )
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

    def verify_source_identity(
        self,
        project: str,
        table: str,
        generation: str,
        epoch: int,
        namespace: str,
        keys: list[RecordKey],
        *,
        valid: bool,
    ) -> bool:
        """Publish a complete source scan, independently of outbound write health."""
        now = datetime.now(UTC)
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            binding = session.get(SheetsBindingRow, table)
            local = session.get(DataTableRow, table)
            if (
                binding is None
                or local is None
                or binding.project_id != project
                or binding.binding_epoch != epoch
                or local.current_generation != generation
            ):
                raise ProjectError(
                    "PRECONDITION_FAILED",
                    "Sheets binding changed during identity verification",
                    412,
                )
            previous = binding.identity_verification or {}
            # A coordinate now naming another column is not evidence of ownership.
            if previous.get("namespace", namespace) != namespace:
                valid = False
                namespace = previous["namespace"]
            pairs = sorted({(key.type, key.value) for key in keys})
            revision = hashlib.sha256(
                json.dumps([namespace, sorted(("text" if kind == "uuid" else kind, value) for kind, value in pairs)], ensure_ascii=False).encode()
            ).hexdigest()
            peers = session.scalars(select(SheetsBindingRow).where(
                SheetsBindingRow.spreadsheet_id == binding.spreadsheet_id,
                SheetsBindingRow.sheet_id == binding.sheet_id,
            )).all()
            binding.identity_verification = {
                **{key: previous[key] for key in ("systemIdentity", "sourceColumns") if key in previous},
                "bindingPeers": sorted([[peer.table_id, peer.binding_epoch] for peer in peers]),
                "namespace": namespace,
                "revision": revision,
                "bindingEpoch": epoch,
                "datasetGeneration": generation,
                "valid": valid,
                "observedAt": now.isoformat(),
            }
            if valid:
                for kind, value in pairs:
                    mark = session.get(SyncRecordMarkRow, (table, kind, value))
                    if mark is None:
                        mark = SyncRecordMarkRow(
                            table_id=table, record_key_type=kind, record_key=value
                        )
                        session.add(mark)
                    mark.observed = {
                        **(mark.observed or {}),
                        "identity": {
                            "revision": revision,
                            "bindingEpoch": epoch,
                            "datasetGeneration": generation,
                        },
                    }
                    mark.remote_missing = False
                    mark.remote_seen_at = now
                    mark.updated_at = now
            session.commit()
            return valid

    def observe_source(
        self, project: str, table: str, generation: str, epoch: int,
        key: RecordKey, values: dict[str, Any],
    ) -> None:
        """Keep one ordinary-cell observation per field without creating an intent."""
        now = datetime.now(UTC)
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            current = _required_table(session, project, table)
            binding = session.get(SheetsBindingRow, table)
            if current.current_generation != generation or binding is None or binding.binding_epoch != epoch:
                return  # An old network response cannot become a new binding's observation.
            record = session.get(DataRecordRow, (generation, key.type, key.value))
            if record is None or record.deleted:
                return
            readable = {item["fieldId"] for item in binding.mapping if item["direction"] != "write"}
            fields = session.scalars(select(DataFieldRow).where(
                DataFieldRow.table_id == table, DataFieldRow.dataset_generation == generation,
            )).all()
            items = []
            for field in fields:
                if field.formula or field.id not in readable or field.id not in values:
                    continue
                local = record.values_json.get(field.id)
                present = field.id in record.values_json
                items.append({
                    "fieldId": field.id, "remoteValue": values[field.id],
                    "localValue": local, "localPresent": present,
                    "localContentRevision": record.content_revision,
                    "observedAt": instant(now),
                    "differs": not present or digest(local) != digest(values[field.id]),
                })
            mark = session.get(SyncRecordMarkRow, (table, key.type, key.value))
            if mark is None:
                mark = SyncRecordMarkRow(table_id=table, record_key_type=key.type, record_key=key.value, remote_missing=False)
                session.add(mark)
            mark.observed = {**(mark.observed or {}), "inboundObservation": {
                "datasetGeneration": generation, "bindingEpoch": epoch, "items": items,
            }}
            mark.updated_at = now
            session.commit()

    def source_observations(
        self, project: str, table: str, generation: str, key: RecordKey,
    ) -> dict[str, Any]:
        with self.sessions() as session:
            session.execute(text("BEGIN"))
            current = _required_table(session, project, table)
            if current.current_generation != generation:
                raise ProjectError("DATASET_GENERATION_GONE", "这条记录属于已替换的数据。", 410)
            record = session.get(DataRecordRow, (generation, key.type, key.value))
            if record is None or record.deleted:
                raise ProjectError("RECORD_NOT_FOUND", "Record was not found", 404)
            result: dict[str, Any] = {"record": {"projectId": project, "tableId": table, "datasetGeneration": generation,
                                 "recordKey": {"type": key.type, "value": key.value}},
                      "bindingEpoch": None, "items": []}
            binding = session.get(SheetsBindingRow, table)
            mark = session.get(SyncRecordMarkRow, (table, key.type, key.value))
            if binding is None:
                return result
            result["bindingEpoch"] = binding.binding_epoch
            observed = (mark.observed or {}).get("inboundObservation", {}) if mark else {}
            if observed.get("datasetGeneration") != generation or observed.get("bindingEpoch") != binding.binding_epoch:
                return result
            readable = {item["fieldId"] for item in binding.mapping if item["direction"] != "write"}
            current_ids = set(session.scalars(select(DataFieldRow.id).where(
                DataFieldRow.table_id == table, DataFieldRow.dataset_generation == generation,
                DataFieldRow.formula.is_(False),
            )))
            result["items"] = [item for item in observed.get("items", []) if item["fieldId"] in readable & current_ids]
            return result

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
                row.observed = {**(row.observed or {}), **(observed or {})}
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
    session: Session,
    table: DataTableRow,
    key: RecordKey,
    revision: int,
    values: dict[str, object],
    *, dependency_id: str | None = None,
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
    if dependency_id:
        request["columnDependencies"] = [dependency_id]
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
        dependencies = sorted(set(open_row.request.get("columnDependencies", []) + ([dependency_id] if dependency_id else [])))
        if dependencies:
            request["columnDependencies"] = dependencies
        open_row.target_content_revision = revision
        open_row.status_revision += 1
        open_row.request = request
        open_row.target = target
        open_row.dedupe_key = (
            f"{binding.binding_epoch}:{key.type}:{key.value}:{revision}" + (":columns:" + ":".join(dependencies) if dependencies else "")
        )
        open_row.updated_at = now
        return
    dedupe = f"{binding.binding_epoch}:{key.type}:{key.value}:{revision}" + (f":columns:{dependency_id}" if dependency_id else "")
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
