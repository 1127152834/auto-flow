"""Project-side work that keeps the workspace from being paused or switched.

Exiting the app and switching workspaces must not silently abandon work that
still has a real, addressable owner. These are the two facts that no other
blocker source covers: a manual item someone is expected to finish, and an
outbound send whose outcome is still unknown.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from .environment_models import ProjectManualItemRow
from .project_sync_models import SyncOperationRow

OPEN_MANUAL_STATUSES = ("waiting", "resume_requested")
UNKNOWN_SEND_STATUSES = ("sending", "verifying", "unknown")


class SqlAlchemyProjectPendingWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def blockers(self) -> list[str]:
        with self._factory() as session:
            manual = (
                session.scalar(
                    select(func.count())
                    .select_from(ProjectManualItemRow)
                    .where(ProjectManualItemRow.status.in_(OPEN_MANUAL_STATUSES))
                )
                or 0
            )
            unknown = (
                session.scalar(
                    select(func.count())
                    .select_from(SyncOperationRow)
                    .where(SyncOperationRow.status.in_(UNKNOWN_SEND_STATUSES))
                )
                or 0
            )
        return [
            *(["project_manual_item_pending"] if manual else []),
            *(["project_sync_outcome_unknown"] if unknown else []),
        ]
