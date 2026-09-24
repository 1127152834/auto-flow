from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.workflows.runs import WorkflowRunError

from .workflow_models import WorkflowMcpCommandRow, WorkflowMcpSettingsRow


class SqlAlchemyWorkflowMcp:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def settings(self) -> tuple[int, str | None, str | None]:
        with self._session_factory() as database:
            row = database.get(WorkflowMcpSettingsRow, 1)
            return (
                (row.revision, row.secret_ref, row.config_digest)
                if row is not None
                else (0, None, None)
            )

    def command(
        self, command_id: str, request_hash: str | None = None
    ) -> tuple[dict[str, Any], int] | None:
        with self._session_factory() as database:
            row = database.get(WorkflowMcpCommandRow, command_id)
            if row is None:
                return None
            if request_hash is not None and row.request_hash != request_hash:
                raise WorkflowRunError(
                    "MCP_IDEMPOTENCY_CONFLICT",
                    "命令 ID 已用于不同内容",
                    409,
                )
            return copy.deepcopy(row.payload), row.http_status

    def save_settings(
        self,
        *,
        expected_revision: int,
        secret_ref: str,
        config_digest: str,
        command_id: str,
        request_hash: str,
        now: datetime,
    ) -> tuple[dict[str, Any], int, str | None]:
        with self._session_factory() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            previous = database.get(WorkflowMcpCommandRow, command_id)
            if previous is not None:
                if previous.request_hash != request_hash:
                    database.rollback()
                    raise WorkflowRunError(
                        "MCP_IDEMPOTENCY_CONFLICT",
                        "命令 ID 已用于不同内容",
                        409,
                    )
                database.rollback()
                return copy.deepcopy(previous.payload), previous.http_status, None
            row = database.get(WorkflowMcpSettingsRow, 1)
            revision = row.revision if row is not None else 0
            if revision != expected_revision:
                database.rollback()
                raise WorkflowRunError(
                    "MCP_REVISION_CONFLICT",
                    "MCP 配置已由其他窗口修改",
                    409,
                    {
                        "expectedRevision": expected_revision,
                        "currentRevision": revision,
                    },
                )
            old_ref = row.secret_ref if row is not None else None
            revision += 1
            if row is None:
                row = WorkflowMcpSettingsRow(
                    id=1,
                    revision=revision,
                    secret_ref=secret_ref,
                    config_digest=config_digest,
                    updated_at=now,
                )
                database.add(row)
            else:
                row.revision = revision
                row.secret_ref = secret_ref
                row.config_digest = config_digest
                row.updated_at = now
            receipt = {
                "success": True,
                "saved": True,
                "commandId": command_id,
                "revision": revision,
            }
            database.add(
                WorkflowMcpCommandRow(
                    id=command_id,
                    request_hash=request_hash,
                    payload=receipt,
                    http_status=200,
                    created_at=now,
                )
            )
            database.commit()
            return receipt, 200, old_ref

    def record_command(
        self,
        *,
        command_id: str,
        request_hash: str,
        expected_revision: int,
        payload: dict[str, Any],
        http_status: int,
        now: datetime,
    ) -> tuple[dict[str, Any], int]:
        with self._session_factory() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            previous = database.get(WorkflowMcpCommandRow, command_id)
            if previous is not None:
                if previous.request_hash != request_hash:
                    database.rollback()
                    raise WorkflowRunError(
                        "MCP_IDEMPOTENCY_CONFLICT",
                        "命令 ID 已用于不同内容",
                        409,
                    )
                database.rollback()
                return copy.deepcopy(previous.payload), previous.http_status
            row = database.get(WorkflowMcpSettingsRow, 1)
            revision = row.revision if row is not None else 0
            if revision != expected_revision:
                database.rollback()
                raise WorkflowRunError(
                    "MCP_REVISION_CONFLICT",
                    "MCP 配置已由其他窗口修改",
                    409,
                    {
                        "expectedRevision": expected_revision,
                        "currentRevision": revision,
                    },
                )
            database.add(
                WorkflowMcpCommandRow(
                    id=command_id,
                    request_hash=request_hash,
                    payload=copy.deepcopy(payload),
                    http_status=http_status,
                    created_at=now,
                )
            )
            database.commit()
            return copy.deepcopy(payload), http_status
