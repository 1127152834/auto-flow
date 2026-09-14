"""Short transactions for durable, restart-safe workbook inspections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_excel_models import (
    ProjectExcelInspectionJobRow,
    ProjectExcelInspectionRow,
    ProjectFileSelectionRow,
)


@dataclass(frozen=True)
class InspectionJob:
    operation_id: str
    inspection_id: str
    project_id: str
    path: str
    selection_token_hash: str
    window_id: int
    window_token_hash: str
    expires_at: datetime
    claim_token: str | None = None


class SqlAlchemyProjectExcelInspections:
    def __init__(
        self, sessions: sessionmaker[Session], workspace_id: str, instance_id: str
    ):
        self.sessions, self.workspace_id, self.instance_id = (
            sessions,
            workspace_id,
            instance_id,
        )

    def register(self, values: dict[str, Any]) -> None:
        with self.sessions.begin() as session:
            if session.get(ProjectRow, values["project_id"]) is None:
                raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)
            session.add(
                ProjectFileSelectionRow(
                    **values,
                    workspace_id=self.workspace_id,
                    instance_id=self.instance_id,
                    consumed_at=None,
                )
            )

    def accept(
        self,
        *,
        project_id: str,
        key: str,
        digest: str,
        token_hash: str,
        window_id: int,
        window_token_hash: str,
    ) -> tuple[ProjectOperationRow, InspectionJob | None]:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == key
                )
            )
            if existing is not None:
                if existing.kind != "inspectExcel" or existing.request_digest != digest:
                    raise ProjectError(
                        "OPERATION_PAYLOAD_MISMATCH",
                        "Idempotency key was used for another request",
                        409,
                    )
                session.expunge(existing)
                session.rollback()
                return existing, None
            project = session.get(ProjectRow, project_id)
            if project is None or project.lifecycle_state == "deleted":
                raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)
            if project.lifecycle_state == "closing":
                raise ProjectError("PROJECT_CLOSING", "Project is closing", 423)
            if project.lifecycle_state != "active":
                raise ProjectError(
                    "LIFECYCLE_CONFLICT", "Project cannot be edited", 409
                )
            selection = session.get(ProjectFileSelectionRow, token_hash)
            if (
                selection is None
                or selection.project_id != project_id
                or selection.workspace_id != self.workspace_id
                or selection.instance_id != self.instance_id
                or selection.purpose != "inspectExcel"
            ):
                raise ProjectError(
                    "FILE_SELECTION_INVALID", "File selection is invalid", 404
                )
            _window(
                selection.window_id,
                selection.window_token_hash,
                window_id,
                window_token_hash,
            )
            expiry = _aware(selection.expires_at)
            if expiry <= datetime.now(UTC):
                raise ProjectError(
                    "FILE_SELECTION_EXPIRED", "File selection expired", 410
                )
            if selection.consumed_at is not None:
                raise ProjectError(
                    "FILE_SELECTION_CONSUMED", "File selection was already used", 409
                )
            now, operation_id, inspection_id = (
                datetime.now(UTC),
                str(uuid4()),
                str(uuid4()),
            )
            selection.consumed_at = now
            operation = ProjectOperationRow(
                id=operation_id,
                project_id=project_id,
                idempotency_key=key,
                kind="inspectExcel",
                request_digest=digest,
                status="accepted",
                status_revision=1,
                resource={"type": "project", "projectId": project_id},
                result=None,
                error=None,
                created_at=now,
                updated_at=now,
                completed_at=None,
            )
            job = ProjectExcelInspectionJobRow(
                operation_id=operation_id,
                inspection_id=inspection_id,
                project_id=project_id,
                path=selection.path,
                selection_token_hash=selection.token_hash,
                window_id=selection.window_id,
                window_token_hash=selection.window_token_hash,
                expires_at=expiry,
                state="accepted",
                claim_token=None,
                created_at=now,
                updated_at=now,
            )
            session.add_all((operation, job))
            session.commit()
            return operation, _job(job)

    def claim(self, operation_id: str) -> InspectionJob | None:
        claim = str(uuid4())
        now = datetime.now(UTC)
        with self.sessions.begin() as session:
            changed = session.execute(
                update(ProjectExcelInspectionJobRow)
                .where(
                    ProjectExcelInspectionJobRow.operation_id == operation_id,
                    ProjectExcelInspectionJobRow.state == "accepted",
                )
                .values(state="running", claim_token=claim, updated_at=now)
            ).rowcount  # type: ignore[attr-defined]
            if not changed:
                return None
            row = session.get(ProjectExcelInspectionJobRow, operation_id)
            assert row is not None
            operation = session.get(ProjectOperationRow, operation_id)
            assert operation is not None
            operation.status = "running"
            operation.status_revision += 1
            operation.updated_at = now
            return _job(row)

    def complete(
        self, job: InspectionJob, snapshot: dict[str, Any], fingerprint: str
    ) -> ProjectOperationRow | None:
        now = datetime.now(UTC)
        with self.sessions.begin() as session:
            row = session.get(ProjectExcelInspectionJobRow, job.operation_id)
            if (
                row is None
                or row.state != "running"
                or row.claim_token != job.claim_token
            ):
                return None
            operation = session.get(ProjectOperationRow, job.operation_id)
            assert operation is not None
            session.add(
                ProjectExcelInspectionRow(
                    id=job.inspection_id,
                    project_id=job.project_id,
                    selection_token_hash=job.selection_token_hash,
                    path=job.path,
                    fingerprint=fingerprint,
                    window_id=job.window_id,
                    window_token_hash=job.window_token_hash,
                    expires_at=job.expires_at,
                    snapshot=snapshot,
                    created_at=now,
                )
            )
            row.state = "succeeded"
            row.updated_at = now
            operation.status = "succeeded"
            operation.status_revision += 1
            operation.result = snapshot
            operation.updated_at = now
            operation.completed_at = now
            return operation

    def fail(
        self, operation_id: str, claim_token: str | None, error: dict[str, Any]
    ) -> None:
        now = datetime.now(UTC)
        with self.sessions.begin() as session:
            job = session.get(ProjectExcelInspectionJobRow, operation_id)
            if (
                job is None
                or job.state in {"succeeded", "failed"}
                or (claim_token is not None and job.claim_token != claim_token)
            ):
                return
            operation = session.get(ProjectOperationRow, operation_id)
            assert operation is not None
            job.state = "failed"
            job.updated_at = now
            operation.status = "failed"
            operation.status_revision += 1
            operation.error = error
            operation.updated_at = now
            operation.completed_at = now

    def pending(self) -> list[InspectionJob]:
        with self.sessions() as session:
            return [
                _job(row)
                for row in session.scalars(
                    select(ProjectExcelInspectionJobRow)
                    .where(
                        ProjectExcelInspectionJobRow.state.in_(("accepted", "running"))
                    )
                    .order_by(ProjectExcelInspectionJobRow.created_at)
                )
            ]


def _job(row: ProjectExcelInspectionJobRow) -> InspectionJob:
    return InspectionJob(
        row.operation_id,
        row.inspection_id,
        row.project_id,
        row.path,
        row.selection_token_hash,
        row.window_id,
        row.window_token_hash,
        _aware(row.expires_at),
        row.claim_token,
    )


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _window(
    expected_id: int, expected_hash: str, window_id: int, window_hash: str
) -> None:
    if expected_id != window_id or expected_hash != window_hash:
        raise ProjectError(
            "FILE_WINDOW_MISMATCH", "File selection belongs to another window", 403
        )
