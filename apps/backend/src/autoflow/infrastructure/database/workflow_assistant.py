from __future__ import annotations

import copy
from datetime import UTC, datetime

from sqlalchemy import select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.workflows.assistant import AssistantCommand, AssistantSession

from .workflow_models import WorkflowAssistantCommandRow, WorkflowAssistantSessionRow


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _session(row: WorkflowAssistantSessionRow) -> AssistantSession:
    payload = row.payload
    return AssistantSession(
        id=row.id,
        title=row.title,
        messages=tuple(copy.deepcopy(payload.get("messages", []))),
        status=payload.get("status", "idle"),
        pending_action=copy.deepcopy(payload.get("pendingAction")),
        revision=row.revision,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _command(row: WorkflowAssistantCommandRow) -> AssistantCommand:
    payload = row.payload
    return AssistantCommand(
        id=row.id,
        session_id=row.session_id,
        request_hash=row.request_hash,
        status=payload["status"],
        result=copy.deepcopy(payload["result"]),
        receipt=copy.deepcopy(payload.get("receipt")),
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


class SqlAlchemyWorkflowAssistant:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(self, session_id: str, title: str, *, now: datetime) -> AssistantSession:
        with self._session_factory() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            existing = database.get(WorkflowAssistantSessionRow, session_id)
            if existing is not None:
                database.rollback()
                return _session(existing)
            row = WorkflowAssistantSessionRow(
                id=session_id,
                title=title,
                payload={"messages": [], "status": "idle", "pendingAction": None},
                revision=1,
                created_at=now,
                updated_at=now,
            )
            database.add(row)
            database.commit()
            return _session(row)

    def get(self, session_id: str) -> AssistantSession | None:
        with self._session_factory() as database:
            row = database.get(WorkflowAssistantSessionRow, session_id)
            return _session(row) if row is not None else None

    def list(self) -> tuple[AssistantSession, ...]:
        with self._session_factory() as database:
            rows = database.scalars(
                select(WorkflowAssistantSessionRow).order_by(
                    WorkflowAssistantSessionRow.updated_at.desc()
                )
            )
            return tuple(_session(row) for row in rows)

    def find_pending(self, command_id: str) -> AssistantSession | None:
        for item in self.list():
            if item.pending_action and item.pending_action.get("commandId") == command_id:
                return item
        return None

    def save(self, value: AssistantSession) -> AssistantSession:
        now = datetime.now(UTC)
        with self._session_factory() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            result = database.execute(
                update(WorkflowAssistantSessionRow)
                .where(
                    WorkflowAssistantSessionRow.id == value.id,
                    WorkflowAssistantSessionRow.revision == value.revision,
                )
                .values(
                    title=value.title,
                    payload={
                        "messages": copy.deepcopy(value.messages),
                        "status": value.status,
                        "pendingAction": copy.deepcopy(value.pending_action),
                    },
                    revision=value.revision + 1,
                    updated_at=now,
                )
            )
            if not isinstance(result, CursorResult) or result.rowcount != 1:
                database.rollback()
                raise ValueError("助手会话已由其他请求修改")
            database.commit()
        restored = self.get(value.id)
        assert restored is not None
        return restored

    def delete(self, session_id: str) -> bool:
        with self._session_factory.begin() as database:
            row = database.get(WorkflowAssistantSessionRow, session_id)
            if row is None:
                return False
            database.delete(row)
            return True

    def confirm_command(
        self,
        command_id: str,
        session_id: str,
        *,
        request_hash: str,
        result: dict[str, object],
        now: datetime,
    ) -> tuple[AssistantCommand, bool]:
        with self._session_factory() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            existing = database.get(WorkflowAssistantCommandRow, command_id)
            if existing is not None:
                previous = _command(existing)
                database.rollback()
                if previous.session_id != session_id or previous.request_hash != request_hash:
                    raise ValueError("commandId 已用于不同请求")
                return previous, False
            row = WorkflowAssistantCommandRow(
                id=command_id,
                session_id=session_id,
                request_hash=request_hash,
                payload={"status": "confirmed", "result": copy.deepcopy(result), "receipt": None},
                created_at=now,
                updated_at=now,
            )
            database.add(row)
            database.commit()
            return _command(row), True

    def get_command(self, command_id: str) -> AssistantCommand | None:
        with self._session_factory() as database:
            row = database.get(WorkflowAssistantCommandRow, command_id)
            return _command(row) if row is not None else None

    def finish_command(
        self, command_id: str, *, status: str, receipt: dict[str, object]
    ) -> AssistantCommand:
        with self._session_factory.begin() as database:
            row = database.get(WorkflowAssistantCommandRow, command_id)
            if row is None:
                raise ValueError("助手命令不存在")
            row.payload = {
                **row.payload,
                "status": status,
                "receipt": copy.deepcopy(receipt),
            }
            row.updated_at = datetime.now(UTC)
        restored = self.get_command(command_id)
        assert restored is not None
        return restored
