from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.android.ports import AndroidError

from .models import AndroidResourceRow


class AndroidResourceRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def get(self, kind: str, identifier: str) -> dict[str, Any]:
        with self.sessions() as session:
            row = session.get(AndroidResourceRow, (kind, identifier))
            if row is None:
                raise AndroidError("ANDROID_RESOURCE_NOT_FOUND", "记录不存在", 404)
            return deepcopy(row.payload)

    def list(self, kind: str) -> list[dict[str, Any]]:
        with self.sessions() as session:
            rows = session.scalars(
                select(AndroidResourceRow).where(AndroidResourceRow.kind == kind)
            )
            return sorted(
                (deepcopy(row.payload) for row in rows),
                key=lambda item: item.get("createdAt", ""),
            )

    def save(self, kind: str, item: dict[str, Any]) -> None:
        with self.sessions.begin() as session:
            session.merge(
                AndroidResourceRow(kind=kind, id=item["id"], payload=deepcopy(item))
            )
