"""Durable facts and read snapshots for XLSX exports."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import Integer, case, func, select, text, update
from sqlalchemy import cast as sql_cast
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.query import matches, validate_filter, validate_order
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataRecordRow,
    DataStatusRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_data_queries import _collation
from autoflow.infrastructure.database.project_excel_models import (
    ProjectExcelExportJobRow,
    ProjectExcelPublicationRow,
    ProjectFileSelectionRow,
)
from autoflow.infrastructure.filesystem.project_excel import WorkbookPublication


@dataclass(frozen=True)
class ExportJob:
    operation_id: str
    project_id: str
    table_id: str
    dataset_generation: str
    path: str
    request: dict[str, Any]
    claim_token: str | None = None


@dataclass
class ExportSnapshot:
    headers: list[str]
    spool: Any

    def rows(self):
        self.spool.seek(0)
        for line in self.spool:
            yield json.loads(line)

    def close(self) -> None:
        self.spool.close()


class SqlAlchemyProjectExcelExports:
    def __init__(
        self, sessions: sessionmaker[Session], workspace_id: str, instance_id: str
    ):
        self.sessions, self.workspace_id, self.instance_id = (
            sessions,
            workspace_id,
            instance_id,
        )

    def accept(
        self,
        *,
        project_id: str,
        table_id: str,
        key: str,
        digest: str,
        token_hash: str,
        window_id: int,
        window_token_hash: str,
        request: dict[str, Any],
    ) -> tuple[ProjectOperationRow, ExportJob | None]:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            old = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == key
                )
            )
            if old:
                if old.kind != "exportXlsx" or old.request_digest != digest:
                    raise ProjectError(
                        "OPERATION_PAYLOAD_MISMATCH",
                        "Idempotency key was used for another request",
                        409,
                    )
                session.expunge(old)
                session.rollback()
                return old, None
            project, table = (
                session.get(ProjectRow, project_id),
                session.get(DataTableRow, table_id),
            )
            if project is None or project.lifecycle_state == "deleted":
                raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)
            if project.lifecycle_state not in {"active", "archived"}:
                raise ProjectError(
                    "LIFECYCLE_CONFLICT", "Project cannot be exported", 409
                )
            if table is None or table.project_id != project_id or not table.published:
                raise ProjectError("TABLE_NOT_FOUND", "Table was not found", 404)
            if table.current_generation != request["datasetGeneration"]:
                raise ProjectError(
                    "DATASET_GENERATION_GONE",
                    "Dataset generation is no longer current",
                    410,
                )
            selection = session.get(ProjectFileSelectionRow, token_hash)
            if (
                selection is None
                or selection.project_id != project_id
                or selection.workspace_id != self.workspace_id
                or selection.instance_id != self.instance_id
                or selection.purpose != "exportXlsx"
            ):
                raise ProjectError(
                    "FILE_SELECTION_INVALID", "File selection is invalid", 404
                )
            if (
                selection.window_id != window_id
                or selection.window_token_hash != window_token_hash
            ):
                raise ProjectError(
                    "FILE_WINDOW_MISMATCH",
                    "File selection belongs to another window",
                    403,
                )
            expiry = (
                selection.expires_at.replace(tzinfo=UTC)
                if selection.expires_at.tzinfo is None
                else selection.expires_at
            )
            if expiry <= datetime.now(UTC):
                raise ProjectError(
                    "FILE_SELECTION_EXPIRED", "File selection expired", 410
                )
            if selection.consumed_at is not None:
                raise ProjectError(
                    "FILE_SELECTION_CONSUMED", "File selection was already used", 409
                )
            now, op_id = datetime.now(UTC), str(uuid4())
            selection.consumed_at = now
            op = ProjectOperationRow(
                id=op_id,
                project_id=project_id,
                idempotency_key=key,
                kind="exportXlsx",
                request_digest=digest,
                status="accepted",
                status_revision=1,
                resource={
                    "type": "table",
                    "projectId": project_id,
                    "tableId": table_id,
                },
                result=None,
                error=None,
                created_at=now,
                updated_at=now,
                completed_at=None,
            )
            job = ProjectExcelExportJobRow(
                operation_id=op_id,
                project_id=project_id,
                table_id=table_id,
                dataset_generation=request["datasetGeneration"],
                selection_token_hash=token_hash,
                path=selection.path,
                window_id=window_id,
                window_token_hash=window_token_hash,
                request=request,
                state="accepted",
                claim_token=None,
                created_at=now,
                updated_at=now,
            )
            publication = ProjectExcelPublicationRow(
                operation_id=op_id,
                path=selection.path,
                digest=None,
                size_bytes=None,
                record_count=None,
                filename=Path(selection.path).name,
                state="accepted",
                published_at=None,
            )
            session.add_all((op, job, publication))
            session.commit()
            return op, _job(job)

    def claim(self, operation_id: str) -> ExportJob | None:
        token, now = str(uuid4()), datetime.now(UTC)
        with self.sessions.begin() as s:
            changed = s.execute(
                update(ProjectExcelExportJobRow)
                .where(
                    ProjectExcelExportJobRow.operation_id == operation_id,
                    ProjectExcelExportJobRow.state == "accepted",
                )
                .values(state="running", claim_token=token, updated_at=now)
            ).rowcount  # type: ignore[attr-defined]
            if not changed:
                return None
            row, op = (
                s.get(ProjectExcelExportJobRow, operation_id),
                s.get(ProjectOperationRow, operation_id),
            )
            assert row and op
            op.status = "running"
            op.status_revision += 1
            op.updated_at = now
            return _job(row)

    def snapshot(self, job: ExportJob) -> ExportSnapshot:
        with self.sessions() as s:
            s.execute(text("BEGIN"))
            table = s.get(DataTableRow, job.table_id)
            if (
                table is None
                or not table.published
                or table.current_generation != job.dataset_generation
            ):
                raise ProjectError(
                    "DATASET_GENERATION_GONE",
                    "Dataset generation is no longer current",
                    410,
                )
            fields = list(
                s.scalars(
                    select(DataFieldRow)
                    .where(
                        DataFieldRow.project_id == job.project_id,
                        DataFieldRow.table_id == job.table_id,
                        DataFieldRow.dataset_generation == job.dataset_generation,
                    )
                    .order_by(DataFieldRow.position, DataFieldRow.id)
                )
            )
            by_id = {f.id: f for f in fields}
            selected = job.request["fieldIds"]
            if len(set(selected)) != len(selected) or any(
                i not in by_id for i in selected
            ):
                raise ProjectError(
                    "VALIDATION_ERROR",
                    "fieldIds contain unknown or duplicate fields",
                    422,
                )
            statuses = list(
                s.scalars(
                    select(DataStatusRow).where(
                        DataStatusRow.project_id == job.project_id,
                        DataStatusRow.table_id == job.table_id,
                        DataStatusRow.deleted.is_(False),
                    )
                )
            )
            status_names = {x.id: x.name for x in statuses}
            status_order = {x.id: (x.position, x.id) for x in statuses}
            types = {f.id: f.type for f in fields}
            filter_expr = validate_filter(
                job.request.get("filterValue"), types, set(status_names)
            )
            order = validate_order(job.request.get("orderValue"), types)
            raw = cast(sqlite3.Connection, s.connection().connection.driver_connection)
            base = [
                DataRecordRow.project_id == job.project_id,
                DataRecordRow.table_id == job.table_id,
                DataRecordRow.dataset_generation == job.dataset_generation,
                DataRecordRow.deleted.is_(False),
            ]
            trivial = filter_expr == {"type": "all", "items": []}
            if not trivial:
                raw.create_function(
                    "autoflow_export_match",
                    2,
                    lambda values, status: int(
                        matches(filter_expr, json.loads(values), status)
                    ),
                )
                base.append(
                    func.autoflow_export_match(
                        DataRecordRow.values_json, DataRecordRow.status_id
                    )
                    == 1
                )
            statement = select(DataRecordRow).where(*base)
            if order:
                cmp = _collation(order, types, status_order)
                targets = [item["fieldId"] for item in order if "fieldId" in item]
                raw.create_function(
                    "autoflow_export_sort",
                    6,
                    lambda values, status, created, updated, key_type, key_value: (
                        json.dumps(
                            [
                                {i: json.loads(values).get(i) for i in targets},
                                status,
                                created,
                                updated,
                                key_type,
                                key_value,
                            ],
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    ),
                )
                raw.create_collation("AUTOFLOW_EXPORT", cmp)
                statement = statement.order_by(
                    text(
                        "autoflow_export_sort(values_json,status_id,created_at,updated_at,key_type,key_value) COLLATE AUTOFLOW_EXPORT"
                    )
                )
            else:
                rank = case(
                    (DataRecordRow.key_type == "text", 0),
                    (DataRecordRow.key_type == "integer", 1),
                    else_=2,
                )
                statement = statement.order_by(
                    rank,
                    case(
                        (
                            DataRecordRow.key_type == "integer",
                            sql_cast(DataRecordRow.key_value, Integer),
                        ),
                        else_=None,
                    ),
                    DataRecordRow.key_value,
                )
            headers = [by_id[i].name for i in selected] + (
                ["状态"] if job.request["includeStatus"] else []
            )
            spool = tempfile.SpooledTemporaryFile(  # noqa: SIM115 -- caller owns snapshot lifetime
                max_size=8 * 1024 * 1024, mode="w+t", encoding="utf-8"
            )
            try:
                for r in s.scalars(statement).yield_per(500):
                    row = [r.values_json.get(i) for i in selected] + (
                        [
                            status_names.get(r.status_id)
                            if r.status_id is not None
                            else None
                        ]
                        if job.request["includeStatus"]
                        else []
                    )
                    spool.write(
                        json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                        + "\n"
                    )
                s.rollback()
                raw.create_function("autoflow_export_match", 2, None)
                raw.create_function("autoflow_export_sort", 6, None)
                raw.create_collation("AUTOFLOW_EXPORT", None)
                return ExportSnapshot(headers, spool)
            except Exception:
                spool.close()
                raw.create_function("autoflow_export_match", 2, None)
                raw.create_function("autoflow_export_sort", 6, None)
                raw.create_collation("AUTOFLOW_EXPORT", None)
                raise

    def prepare(self, job: ExportJob, value: WorkbookPublication) -> None:
        now = datetime.now(UTC)
        with self.sessions.begin() as s:
            row = s.get(ProjectExcelExportJobRow, job.operation_id)
            pub = s.get(ProjectExcelPublicationRow, job.operation_id)
            if (
                row is None
                or pub is None
                or row.state != "running"
                or row.claim_token != job.claim_token
            ):
                raise ProjectError("OPERATION_CLAIM_LOST", "Export claim was lost", 409)
            row.state = pub.state = "publishing"
            row.updated_at = now
            pub.digest = value.sha256
            pub.size_bytes = value.size_bytes
            pub.record_count = value.record_count

    def complete(self, job: ExportJob) -> ProjectOperationRow | None:
        now = datetime.now(UTC)
        with self.sessions.begin() as s:
            row = s.get(ProjectExcelExportJobRow, job.operation_id)
            pub = s.get(ProjectExcelPublicationRow, job.operation_id)
            op = s.get(ProjectOperationRow, job.operation_id)
            if (
                not row
                or not pub
                or not op
                or row.state != "publishing"
                or row.claim_token != job.claim_token
            ):
                return None
            result = {
                "filename": pub.filename,
                "sha256": pub.digest,
                "recordCount": pub.record_count,
            }
            row.state = "succeeded"
            pub.state = "published"
            pub.published_at = now
            op.status = "succeeded"
            op.status_revision += 1
            op.result = result
            op.updated_at = op.completed_at = now
            return op

    def fail(self, operation_id: str, error: dict[str, Any]) -> None:
        now = datetime.now(UTC)
        with self.sessions.begin() as s:
            row = s.get(ProjectExcelExportJobRow, operation_id)
            op = s.get(ProjectOperationRow, operation_id)
            if (
                not row
                or not op
                or row.state in {"succeeded", "failed", "publishing", "reconciling"}
            ):
                return
            row.state = "failed"
            row.updated_at = now
            op.status = "failed"
            op.status_revision += 1
            op.error = error
            op.updated_at = op.completed_at = now

    def pending(self) -> list[ExportJob]:
        with self.sessions() as s:
            return [
                _job(x)
                for x in s.scalars(
                    select(ProjectExcelExportJobRow)
                    .where(
                        ProjectExcelExportJobRow.state.in_(
                            ("accepted", "running", "publishing")
                        )
                    )
                    .order_by(ProjectExcelExportJobRow.created_at)
                )
            ]

    def fail_publication_recovery(self, job: ExportJob, outcome: str) -> None:
        now = datetime.now(UTC)
        with self.sessions.begin() as s:
            row = s.get(ProjectExcelExportJobRow, job.operation_id)
            op = s.get(ProjectOperationRow, job.operation_id)
            pub = s.get(ProjectExcelPublicationRow, job.operation_id)
            if (
                not row
                or not op
                or not pub
                or row.state != "publishing"
                or row.claim_token != job.claim_token
                or not pub.digest
            ):
                return
            code = (
                "EXCEL_EXPORT_TARGET_MISSING"
                if outcome == "missing"
                else "EXCEL_EXPORT_TARGET_CONFLICT"
                if outcome == "conflict"
                else "EXCEL_EXPORT_VERIFICATION_FAILED"
            )
            row.state = "failed"
            row.updated_at = now
            op.status = "failed"
            op.status_revision += 1
            op.error = {
                "code": code,
                "message": "Export target could not be verified",
                "details": {},
            }
            op.updated_at = op.completed_at = now

    def pending_reconciliations(self) -> list[tuple[str, str]]:
        with self.sessions() as s:
            output = []
            for row in s.scalars(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.kind == "reconcileOperation",
                    ProjectOperationRow.status == "running",
                )
            ):
                if isinstance(row.result, dict) and isinstance(
                    row.result.get("targetOperationId"), str
                ):
                    output.append((row.id, row.result["targetOperationId"]))
            return output

    def publication(self, operation_id: str) -> ProjectExcelPublicationRow | None:
        with self.sessions() as s:
            row = s.get(ProjectExcelPublicationRow, operation_id)
            if row:
                s.expunge(row)
            return row

    def accept_reconcile(
        self,
        project_id: str,
        target_id: str,
        key: str,
        digest: str,
        expected_revision: int,
    ) -> tuple[ProjectOperationRow, bool]:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            old = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == key
                )
            )
            if old:
                if old.kind != "reconcileOperation" or old.request_digest != digest:
                    raise ProjectError(
                        "OPERATION_PAYLOAD_MISMATCH",
                        "Idempotency key was used for another request",
                        409,
                    )
                session.expunge(old)
                session.rollback()
                return old, False
            target = session.get(ProjectOperationRow, target_id)
            publication = session.get(ProjectExcelPublicationRow, target_id)
            job = session.get(ProjectExcelExportJobRow, target_id)
            if (
                target is None
                or target.project_id != project_id
                or target.kind != "exportXlsx"
            ):
                raise ProjectError(
                    "OPERATION_NOT_FOUND", "Operation was not found", 404
                )
            if target.status_revision != expected_revision:
                raise ProjectError(
                    "OPERATION_REVISION_CONFLICT", "Operation revision changed", 409
                )
            if (
                target.status == "succeeded"
                or publication is None
                or job is None
                or not publication.digest
            ):
                raise ProjectError(
                    "OPERATION_NOT_RECONCILABLE", "Operation cannot be reconciled", 409
                )
            now = datetime.now(UTC)
            target.status = "reconciling"
            target.status_revision += 1
            target.updated_at = now
            job.state = "reconciling"
            job.updated_at = now
            command = ProjectOperationRow(
                id=str(uuid4()),
                project_id=project_id,
                idempotency_key=key,
                kind="reconcileOperation",
                request_digest=digest,
                status="running",
                status_revision=2,
                resource=target.resource,
                result={
                    "targetOperationId": target_id,
                    "status": "reconciling",
                    "expectedTargetRevision": target.status_revision,
                },
                error=None,
                created_at=now,
                updated_at=now,
                completed_at=None,
            )
            session.add(command)
            session.commit()
            return command, True

    def finish_reconcile(
        self, command_id: str, target_id: str, outcome: str
    ) -> ProjectOperationRow:
        now = datetime.now(UTC)
        with self.sessions.begin() as s:
            command = s.get(ProjectOperationRow, command_id)
            target = s.get(ProjectOperationRow, target_id)
            pub = s.get(ProjectExcelPublicationRow, target_id)
            job = s.get(ProjectExcelExportJobRow, target_id)
            assert command and target and pub and job
            identity = command.result if isinstance(command.result, dict) else {}
            if command.status in {"succeeded", "failed"}:
                return command
            if identity.get("targetOperationId") != target_id:
                raise ProjectError(
                    "OPERATION_REVISION_CONFLICT",
                    "Operation changed during reconciliation",
                    409,
                )
            if target.status in {"succeeded", "failed"}:
                command.status = "succeeded"
                command.status_revision += 1
                command.result = {
                    "targetOperationId": target_id,
                    "status": target.status,
                }
                command.updated_at = command.completed_at = now
                return command
            if (
                command.status != "running"
                or target.status != "reconciling"
                or job.state != "reconciling"
                or identity.get("expectedTargetRevision") != target.status_revision
            ):
                raise ProjectError(
                    "OPERATION_REVISION_CONFLICT",
                    "Operation changed during reconciliation",
                    409,
                )
            if outcome == "matches":
                result = {
                    "filename": pub.filename,
                    "sha256": pub.digest,
                    "recordCount": pub.record_count,
                }
                target.status = "succeeded"
                target.result = result
                target.error = None
                pub.state = "published"
                pub.published_at = now
                job.state = "succeeded"
            else:
                target.status = "failed"
                target.error = {
                    "code": "EXCEL_EXPORT_TARGET_MISSING"
                    if outcome == "missing"
                    else "EXCEL_EXPORT_TARGET_CONFLICT"
                    if outcome == "conflict"
                    else "EXCEL_EXPORT_VERIFICATION_FAILED",
                    "message": "Export target could not be verified",
                    "details": {},
                }
                job.state = "failed"
            target.status_revision += 1
            target.updated_at = target.completed_at = now
            command.status = "succeeded"
            command.status_revision += 1
            command.result = {"targetOperationId": target_id, "status": target.status}
            command.updated_at = command.completed_at = now
            return command


def _job(r: ProjectExcelExportJobRow) -> ExportJob:
    return ExportJob(
        r.operation_id,
        r.project_id,
        r.table_id,
        r.dataset_generation,
        r.path,
        r.request,
        r.claim_token,
    )
