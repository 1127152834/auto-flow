"""Durable source fences shared by sends, binding changes and lifecycle guards."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from autoflow.domain.projects.models import ProjectError

from .project_sync_models import SyncOperationRow


def unresolved_structure(session: Session) -> list[SyncOperationRow]:
    return [row for row in session.scalars(select(SyncOperationRow).where(
        SyncOperationRow.kind.in_(("systemIdentity", "column")),
        SyncOperationRow.attempts > 0,
        SyncOperationRow.status.not_in(("confirmed", "cancelled")),
    )) if not (row.status == "failed" and (row.error or {}).get("unsent") is True)]


def unresolved_values(session: Session) -> list[SyncOperationRow]:
    return list(session.scalars(select(SyncOperationRow).where(
        SyncOperationRow.kind == "push", SyncOperationRow.operation_id.is_(None),
        SyncOperationRow.status.in_(("sending", "verifying", "unknown")),
    )))


def require_source_idle(session: Session, spreadsheet: str, *, own: str | None = None, structural: bool = False) -> None:
    blockers = [row for row in unresolved_structure(session)
                if row.id != own and row.target.get("spreadsheetId") == spreadsheet]
    if structural:
        blockers += unresolved_values(session)
    if any(row.target.get("spreadsheetId") == spreadsheet for row in blockers):
        raise ProjectError("SHEETS_SOURCE_SEND_IN_PROGRESS", "来源仍有发送中或结果未确认的操作，请先核验原操作。", 409)
