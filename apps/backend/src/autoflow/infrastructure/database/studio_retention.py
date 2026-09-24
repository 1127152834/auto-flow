from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.workflows.models import WorkflowError

from .workflow_models import (
    WorkflowRecordingSessionRow,
    WorkflowRunArtifactRow,
    WorkflowRunRow,
)


class SqlAlchemyStudioRetention:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def recordings(self) -> list[dict[str, Any]]:
        with self._session_factory() as database:
            rows = database.scalars(
                select(WorkflowRecordingSessionRow)
                .where(WorkflowRecordingSessionRow.active_slot.is_(None))
                .order_by(WorkflowRecordingSessionRow.updated_at)
            ).all()
            return [
                {
                    "id": row.id,
                    "timestamp": row.updated_at,
                    "size": max(0, row.byte_count),
                }
                for row in rows
            ]

    def artifacts(self) -> list[dict[str, Any]]:
        with self._session_factory() as database:
            rows = database.execute(
                select(WorkflowRunArtifactRow, WorkflowRunRow.started_at)
                .join(WorkflowRunRow, WorkflowRunArtifactRow.run_id == WorkflowRunRow.id)
                .where(WorkflowRunRow.active_slot.is_(None))
                .order_by(WorkflowRunRow.started_at, WorkflowRunArtifactRow.ordinal)
            ).all()
            return [
                {
                    "key": (row.run_id, row.id),
                    "timestamp": self._datetime(started_at),
                    "size": max(0, int(row.payload.get("size", 0))),
                    "relativePath": row.payload.get("relativePath"),
                }
                for row, started_at in rows
            ]

    def usage(self) -> dict[str, dict[str, int]]:
        with self._session_factory() as database:
            recordings = database.scalars(select(WorkflowRecordingSessionRow)).all()
            artifacts = database.scalars(select(WorkflowRunArtifactRow)).all()
            return {
                "recordings": {
                    "count": len(recordings),
                    "bytes": sum(max(0, row.byte_count) for row in recordings),
                },
                "data": {
                    "count": len(artifacts),
                    "bytes": sum(
                        max(0, int(row.payload.get("size", 0))) for row in artifacts
                    ),
                },
            }

    def delete_recordings(self, ids: list[str]) -> None:
        if not ids:
            return
        with self._session_factory() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            rows = database.scalars(
                select(WorkflowRecordingSessionRow).where(
                    WorkflowRecordingSessionRow.id.in_(ids),
                    WorkflowRecordingSessionRow.active_slot.is_(None),
                )
            ).all()
            if len(rows) != len(ids):
                database.rollback()
                raise WorkflowError(
                    "RETENTION_RECORDING_CHANGED",
                    "录像状态已变化，请重新执行清理",
                    409,
                )
            for row in rows:
                database.delete(row)
            database.commit()

    def delete_artifacts(self, keys: list[tuple[str, str]]) -> None:
        if not keys:
            return
        with self._session_factory() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            rows: list[WorkflowRunArtifactRow] = []
            for key in keys:
                row = database.get(WorkflowRunArtifactRow, key)
                run = database.get(WorkflowRunRow, key[0])
                if row is None or run is None or run.active_slot is not None:
                    database.rollback()
                    raise WorkflowError(
                        "RETENTION_ARTIFACT_CHANGED",
                        "运行产物状态已变化，请重新执行清理",
                        409,
                    )
                rows.append(row)
            for row in rows:
                database.delete(row)
            database.commit()

    @staticmethod
    def _datetime(value: str) -> datetime:
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError) as error:
            raise WorkflowError(
                "RETENTION_TIMESTAMP_INVALID", "运行产物时间无效", 500
            ) from error
