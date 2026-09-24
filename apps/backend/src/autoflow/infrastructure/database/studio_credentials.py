from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.workflows.models import WorkflowError

from .workflow_models import (
    StudioCredentialCommandRow,
    StudioCredentialRow,
    StudioCredentialStateRow,
)


class SqlAlchemyStudioCredentials:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_items(self) -> list[dict[str, Any]]:
        with self._session_factory() as database:
            rows = database.scalars(
                select(StudioCredentialRow).order_by(StudioCredentialRow.name)
            )
            return [self._payload(row) for row in rows]

    def get(self, name: str) -> dict[str, Any] | None:
        with self._session_factory() as database:
            row = database.get(StudioCredentialRow, name)
            return self._payload(row) if row is not None else None

    def upsert(
        self,
        name: str,
        description: str | None,
        field_names: list[str],
        now: datetime,
    ) -> dict[str, Any]:
        with self._session_factory() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            row = database.get(StudioCredentialRow, name)
            if row is None:
                row = StudioCredentialRow(
                    name=name,
                    description=description or "",
                    field_names=sorted(field_names),
                    revision=self._next_revision(database),
                    created_at=now,
                    updated_at=now,
                )
                database.add(row)
            else:
                row.description = description or row.description
                row.field_names = sorted(set(row.field_names) | set(field_names))
                row.revision = self._next_revision(database)
                row.updated_at = now
            database.commit()
            return self._payload(row)

    def apply_fields(
        self,
        *,
        name: str,
        expected_revision: int,
        field_names: list[str],
        command_id: str,
        request_hash: str,
        now: datetime,
    ) -> tuple[dict[str, Any], bool]:
        with self._session_factory() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            previous = database.get(StudioCredentialCommandRow, command_id)
            if previous is not None:
                if previous.request_hash != request_hash:
                    database.rollback()
                    raise WorkflowError(
                        "CREDENTIAL_COMMAND_CONFLICT",
                        "命令标识已用于其他修改",
                        409,
                    )
                database.rollback()
                return copy.deepcopy(previous.response), False
            row = database.get(StudioCredentialRow, name)
            if row is None:
                database.rollback()
                raise WorkflowError("CREDENTIAL_NOT_FOUND", "凭据不存在", 404)
            if row.revision != expected_revision:
                database.rollback()
                raise WorkflowError(
                    "CREDENTIAL_REVISION_CONFLICT",
                    "凭据已被修改，请重新读取后编辑字段",
                    409,
                    details={
                        "expectedRevision": expected_revision,
                        "currentRevision": row.revision,
                    },
                )
            row.field_names = sorted(field_names)
            row.revision = self._next_revision(database)
            row.updated_at = now
            response = {
                "success": True,
                "commandId": command_id,
                "credential": self._payload(row),
            }
            database.add(
                StudioCredentialCommandRow(
                    id=command_id,
                    request_hash=request_hash,
                    response=response,
                    http_status=200,
                    created_at=now,
                )
            )
            database.commit()
            return response, True

    def command(self, command_id: str, request_hash: str) -> dict[str, Any] | None:
        with self._session_factory() as database:
            row = database.get(StudioCredentialCommandRow, command_id)
            if row is None:
                return None
            if row.request_hash != request_hash:
                raise WorkflowError(
                    "CREDENTIAL_COMMAND_CONFLICT",
                    "命令标识已用于其他修改",
                    409,
                )
            return copy.deepcopy(row.response)

    def rename(self, old_name: str, new_name: str, now: datetime) -> dict[str, Any]:
        with self._session_factory() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            row = database.get(StudioCredentialRow, old_name)
            if row is None:
                database.rollback()
                raise WorkflowError("CREDENTIAL_NOT_FOUND", "凭据不存在", 404)
            if (
                old_name != new_name
                and database.get(StudioCredentialRow, new_name) is not None
            ):
                database.rollback()
                raise WorkflowError("CREDENTIAL_EXISTS", "凭据名称已存在", 409)
            if old_name == new_name:
                row.revision = self._next_revision(database)
                row.updated_at = now
                database.commit()
                return self._payload(row)
            replacement = StudioCredentialRow(
                name=new_name,
                description=row.description,
                field_names=list(row.field_names),
                revision=self._next_revision(database),
                created_at=row.created_at,
                updated_at=now,
            )
            database.add(replacement)
            database.delete(row)
            database.commit()
            return self._payload(replacement)

    def delete(self, name: str) -> None:
        with self._session_factory() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            row = database.get(StudioCredentialRow, name)
            if row is None:
                database.rollback()
                raise WorkflowError("CREDENTIAL_NOT_FOUND", "凭据不存在", 404)
            database.delete(row)
            database.commit()

    @staticmethod
    def _payload(row: StudioCredentialRow) -> dict[str, Any]:
        return {
            "name": row.name,
            "description": row.description,
            "fields": [
                {"key": key, "masked": "••••••"} for key in sorted(row.field_names)
            ],
            "revision": row.revision,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    @staticmethod
    def _next_revision(database: Session) -> int:
        state = database.get(StudioCredentialStateRow, 1)
        if state is None:
            state = StudioCredentialStateRow(id=1, revision=0)
            database.add(state)
        state.revision += 1
        return state.revision
