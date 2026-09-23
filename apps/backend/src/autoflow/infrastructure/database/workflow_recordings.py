from __future__ import annotations

import copy
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.workflows.runs import WorkflowRunError

from .projects import guard_project
from .workflow_models import (
    WorkflowDocumentRow,
    WorkflowRecordingCommandRow,
    WorkflowRecordingEventRow,
    WorkflowRecordingReviewRow,
    WorkflowRecordingSessionRow,
)
from .workflow_project_scope import workflow_project_id

MAX_RECORDING_EVENTS = 10_000
MAX_RECORDING_BYTES = 64 * 1024 * 1024
MAX_RECORDING_VALUE_BYTES = 1024 * 1024
RECORDER_EVENT_TYPES = frozenset(
    {
        "navigate",
        "click",
        "dblclick",
        "input",
        "select",
        "check",
        "keypress",
        "drag",
        "upload",
        "scroll",
    }
)


class SqlAlchemyWorkflowRecordings:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def check_project(self, project_id: str | None, *, writable: bool = False) -> None:
        if project_id is not None:
            with self._session_factory() as session:
                guard_project(session, project_id, writable=writable)

    def admit_browser(self, project_id: str | None, claim: Callable[[], None]) -> None:
        # The lifecycle writer takes the same SQLite reservation. Publish the
        # in-memory browser claim before releasing it, never across an await.
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            if project_id is not None:
                guard_project(session, project_id)
            claim()
            session.rollback()

    @staticmethod
    def _owner(row: Any, project_id: str | None) -> None:
        if row.project_id != project_id:
            raise WorkflowRunError("RECORDING_NOT_FOUND", "录制资源不属于当前项目", 404)

    @staticmethod
    def _document(session: Session, document_id: str | None, project_id: str | None) -> None:
        if (document_id is not None and session.get(WorkflowDocumentRow, document_id) is not None
                and workflow_project_id(session, document_id) != project_id):
            raise WorkflowRunError("RECORDING_DOCUMENT_SCOPE", "录制文档不属于当前项目", 404)

    def start(self, session_id: str, *, now: datetime, project_id: str | None = None,
              document_id: str | None = None) -> dict[str, Any]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            if project_id is not None:
                guard_project(session, project_id)
            self._document(session, document_id, project_id)
            row = session.get(WorkflowRecordingSessionRow, session_id)
            if row is not None:
                self._owner(row, project_id)
                if row.document_id != document_id:
                    raise WorkflowRunError("RECORDING_CONFLICT", "录制会话已绑定其他文档", 409)
                if row.status != "recording":
                    session.rollback()
                    raise ValueError("录制会话已结束")
                result = _status(row)
                session.rollback()
                return result
            row = WorkflowRecordingSessionRow(
                id=session_id,
                project_id=project_id,
                document_id=document_id,
                status="recording",
                active_slot=1,
                last_sequence=0,
                byte_count=0,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise ValueError("当前已有活跃录制会话") from error
            return _status(row)

    def begin_command(
        self,
        command_id: str,
        *,
        session_id: str,
        action: str,
        request_hash: str,
        now: datetime,
        project_id: str | None = None,
    ) -> dict[str, Any] | None:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            if project_id is not None:
                guard_project(session, project_id, writable=action in {"start", "resume"})
            row = session.get(WorkflowRecordingCommandRow, command_id)
            if row is not None:
                self._owner(row, project_id)
                result = _command(row)
                session.rollback()
                return result
            session.add(
                WorkflowRecordingCommandRow(
                    id=command_id,
                    project_id=project_id,
                    session_id=session_id,
                    action=action,
                    request_hash=request_hash,
                    status="pending",
                    payload={},
                    http_status=202,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
            return None

    def finish_command(
        self,
        command_id: str,
        *,
        status: str,
        payload: dict[str, Any],
        http_status: int,
        now: datetime,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(WorkflowRecordingCommandRow, command_id)
            if row is None:
                session.rollback()
                raise ValueError("录制命令不存在")
            row.status = status
            row.payload = copy.deepcopy(payload)
            row.http_status = http_status
            row.updated_at = now
            session.commit()
            return _command(row)

    def command(self, command_id: str, *, project_id: str | None = None) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.get(WorkflowRecordingCommandRow, command_id)
            if row is not None:
                self._owner(row, project_id)
            return _command(row) if row is not None else None

    def recover_active(self, *, now: datetime) -> int:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            rows = session.scalars(
                select(WorkflowRecordingSessionRow).where(
                    WorkflowRecordingSessionRow.active_slot.is_not(None)
                )
            ).all()
            for row in rows:
                row.status = "interrupted"
                row.active_slot = None
                row.updated_at = now
            commands = session.scalars(
                select(WorkflowRecordingCommandRow).where(
                    WorkflowRecordingCommandRow.status == "pending"
                )
            ).all()
            for command in commands:
                command.status = "failed"
                command.payload = {
                    "code": "RECORDING_COMMAND_INTERRUPTED",
                    "message": "录制服务中断，命令结果未确认且不会自动重放",
                    "details": {},
                }
                command.http_status = 503
                command.updated_at = now
            session.commit()
            return len(rows)

    def append(
        self, session_id: str, events: list[dict[str, Any]], *, now: datetime
    ) -> list[dict[str, Any]]:
        if not events:
            return []
        events = [_normalize_captured_event(event) for event in events]
        encoded = [_event_bytes(event) for event in events]
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(WorkflowRecordingSessionRow, session_id)
            if row is None or row.status != "recording":
                session.rollback()
                raise ValueError("录制会话不存在或已经结束")
            if row.last_sequence + len(events) > MAX_RECORDING_EVENTS:
                session.rollback()
                raise ValueError("录制步骤已达到 10000 条上限")
            if row.byte_count + sum(len(value) for value in encoded) > MAX_RECORDING_BYTES:
                session.rollback()
                raise ValueError("录制原文已达到 64 MiB 上限")
            saved: list[dict[str, Any]] = []
            for event, raw in zip(events, encoded, strict=True):
                row.last_sequence += 1
                payload = copy.deepcopy(event)
                payload["sequence"] = row.last_sequence
                session.add(
                    WorkflowRecordingEventRow(
                        session_id=session_id,
                        sequence=row.last_sequence,
                        payload=payload,
                        size_bytes=len(raw),
                    )
                )
                saved.append(payload)
            row.byte_count += sum(len(value) for value in encoded)
            row.updated_at = now
            session.commit()
            return saved

    def stop(self, session_id: str, *, now: datetime) -> dict[str, Any]:
        return self._finish(session_id, status="stopped", now=now)

    def interrupt(self, session_id: str, *, now: datetime) -> dict[str, Any]:
        return self._finish(session_id, status="interrupted", now=now)

    def _finish(
        self, session_id: str, *, status: str, now: datetime
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(WorkflowRecordingSessionRow, session_id)
            if row is None:
                session.rollback()
                raise ValueError("录制会话不存在")
            row.status = status
            row.active_slot = None
            row.updated_at = now
            session.commit()
            return _status(row)

    def status(self, session_id: str, *, project_id: str | None = None) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(WorkflowRecordingSessionRow, session_id)
            if row is None:
                raise ValueError("录制会话不存在")
            self._owner(row, project_id)
            return _status(row)

    def current(self, *, project_id: str | None = None) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(WorkflowRecordingSessionRow)
                .where(WorkflowRecordingSessionRow.project_id == project_id)
                .order_by(WorkflowRecordingSessionRow.created_at.desc())
                .limit(1)
            )
            return _status(row) if row is not None else None

    def events(
        self, session_id: str, *, after_seq: int, limit: int = 200, project_id: str | None = None
    ) -> dict[str, Any]:
        status = self.status(session_id, project_id=project_id)
        if after_seq > status["nextSeq"]:
            raise ValueError("录制确认游标超出已确认步骤")
        with self._session_factory() as session:
            rows = session.scalars(
                select(WorkflowRecordingEventRow)
                .where(
                    WorkflowRecordingEventRow.session_id == session_id,
                    WorkflowRecordingEventRow.sequence > after_seq,
                )
                .order_by(WorkflowRecordingEventRow.sequence)
                .limit(limit)
            ).all()
            data = [copy.deepcopy(row.payload) for row in rows]
        next_seq = data[-1]["sequence"] if data else after_seq
        return {
            "sessionId": session_id,
            "nextSeq": next_seq,
            "hasMore": next_seq < status["nextSeq"],
            "data": data,
        }

    def read_review(self, document_id: str, *, project_id: str | None = None) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.get(WorkflowRecordingReviewRow, document_id)
            self._document(session, document_id, project_id)
            if row is not None:
                self._owner(row, project_id)
            return _review(row) if row is not None else None

    def save_review(
        self,
        document_id: str,
        *,
        expected_revision: int,
        auto_wait: bool,
        events: list[dict[str, Any]],
        now: datetime,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        if len(events) > MAX_RECORDING_EVENTS:
            raise ValueError("录制步骤已达到 10000 条上限")
        if sum(len(_event_bytes(event)) for event in events) > MAX_RECORDING_BYTES:
            raise ValueError("录制原文已达到 64 MiB 上限")
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            if project_id is not None:
                guard_project(session, project_id)
            self._document(session, document_id, project_id)
            row = session.get(WorkflowRecordingReviewRow, document_id)
            if row is not None:
                self._owner(row, project_id)
            actual = row.revision if row is not None else 0
            if actual != expected_revision:
                session.rollback()
                raise ValueError("录制审查已修改")
            if row is None:
                row = WorkflowRecordingReviewRow(
                    document_id=document_id,
                    project_id=project_id,
                    revision=1,
                    auto_wait=auto_wait,
                    events=copy.deepcopy(events),
                    updated_at=now,
                )
                session.add(row)
            else:
                row.revision += 1
                row.auto_wait = auto_wait
                row.events = copy.deepcopy(events)
                row.updated_at = now
            session.commit()
            return _review(row)


def _event_bytes(event: dict[str, Any]) -> bytes:
    if any(
        len(value.encode("utf-8")) > MAX_RECORDING_VALUE_BYTES
        for value in _strings(event)
    ):
        raise ValueError("录制单值超过 1 MiB 上限")
    return json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _normalize_captured_event(event: dict[str, Any]) -> dict[str, Any]:
    if event.get("type") not in RECORDER_EVENT_TYPES:
        raise ValueError("不支持的录制事件")
    normalized = copy.deepcopy(event)
    normalized.pop("sequence", None)
    if normalized.get("type") == "input" and normalized.get("sensitive") is True:
        normalized["value"] = ""
        normalized["needsValue"] = True
    return normalized


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _status(row: WorkflowRecordingSessionRow) -> dict[str, Any]:
    return {
        "sessionId": row.id,
        "recording": row.status == "recording",
        "nextSeq": row.last_sequence,
    }


def _command(row: WorkflowRecordingCommandRow) -> dict[str, Any]:
    return {
        "commandId": row.id,
        "sessionId": row.session_id,
        "action": row.action,
        "requestHash": row.request_hash,
        "status": row.status,
        "payload": copy.deepcopy(row.payload),
        "httpStatus": row.http_status,
    }


def _review(row: WorkflowRecordingReviewRow) -> dict[str, Any]:
    return {
        "documentId": row.document_id,
        "revision": row.revision,
        "autoWait": row.auto_wait,
        "events": copy.deepcopy(row.events),
    }
