from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.android.ports import AndroidError

from .android_models import AndroidAiTestRow

_Runs = list[dict[str, Any]]  # `list` is a method name inside the class body
MAX_STEPS_KEPT = 200
ACTIVE_STATES = ("queued", "running")
_COLUMN_KEYS = {"state": "state", "startedAt": "started_at", "finishedAt": "finished_at"}
_TIME_KEYS = {"createdAt", "startedAt", "finishedAt"}
_FIXED = ("id", "requestId", "deviceKind", "deviceId", "serial", "state", *_TIME_KEYS)


def _utc(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _iso(value: datetime | None) -> str | None:
    # SQLite drops tzinfo on read; values are always stored as UTC.
    parsed = _utc(value)
    return None if parsed is None else parsed.isoformat()


def _public(row: AndroidAiTestRow) -> dict[str, Any]:
    return {
        "id": row.id, "requestId": row.request_id, "deviceKind": row.device_kind,
        "deviceId": row.device_id, "serial": row.serial, "state": row.state,
        "createdAt": _iso(row.created_at), "startedAt": _iso(row.started_at),
        "finishedAt": _iso(row.finished_at), **deepcopy(row.payload),
    }


def _not_found() -> AndroidError:
    return AndroidError("AI_TEST_NOT_FOUND", "AI 测试记录不存在", 404)


def _scope(device_kind: str, device_id: str | None, serial: str | None) -> list[Any]:
    clauses: list[Any] = [AndroidAiTestRow.device_kind == device_kind]
    if device_kind == "managed":
        clauses.append(AndroidAiTestRow.device_id == device_id)
    else:
        clauses.append(AndroidAiTestRow.serial == serial)
    return clauses


class AiTestRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def create(self, run: dict[str, Any]) -> dict[str, Any]:
        try:
            with self.sessions.begin() as session:
                row = AndroidAiTestRow(
                    id=run["id"], request_id=run["requestId"], device_kind=run["deviceKind"],
                    device_id=run.get("deviceId"), serial=run.get("serial"), state=run["state"],
                    created_at=_utc(run["createdAt"]), started_at=_utc(run.get("startedAt")),
                    finished_at=_utc(run.get("finishedAt")),
                    payload={k: deepcopy(v) for k, v in run.items() if k not in _FIXED},
                )
                session.add(row)
                session.flush()
                return _public(row)
        except IntegrityError:
            with self.sessions() as session:
                existing = session.scalars(
                    select(AndroidAiTestRow).where(AndroidAiTestRow.request_id == run["requestId"])
                ).first()
                if existing is None:
                    raise
                if existing.payload.get("requestDigest") != run.get("requestDigest"):
                    raise AndroidError("ANDROID_REQUEST_CONFLICT", "请求编号已用于不同的测试", 409) from None
                return _public(existing)

    def get(self, run_id: str) -> dict[str, Any]:
        with self.sessions() as session:
            row = session.get(AndroidAiTestRow, run_id)
            if row is None:
                raise _not_found()
            return _public(row)

    def get_by_request(self, request_id: str) -> dict[str, Any] | None:
        with self.sessions() as session:
            row = session.scalars(
                select(AndroidAiTestRow).where(AndroidAiTestRow.request_id == request_id)
            ).first()
            return None if row is None else _public(row)

    def update(self, run_id: str, **changes: Any) -> dict[str, Any]:
        with self.sessions.begin() as session:
            row = session.get(AndroidAiTestRow, run_id)
            if row is None:
                raise _not_found()
            payload = deepcopy(row.payload)
            for key, value in changes.items():
                if key in _COLUMN_KEYS:
                    setattr(row, _COLUMN_KEYS[key], _utc(value) if key in _TIME_KEYS else value)
                else:
                    payload[key] = value
            row.payload = payload  # reassign: JSON columns do not track in-place mutation
            session.flush()
            return _public(row)

    def append_step(self, run_id: str, step: dict[str, Any]) -> None:
        with self.sessions.begin() as session:
            row = session.get(AndroidAiTestRow, run_id)
            if row is None:
                raise _not_found()
            payload = deepcopy(row.payload)
            payload["steps"] = [*payload.get("steps", []), deepcopy(step)][-MAX_STEPS_KEPT:]
            row.payload = payload

    def list(
        self, device_kind: str, device_id: str | None, serial: str | None, cursor: str | None, limit: int = 20,
    ) -> tuple[list[dict[str, Any]], str | None]:
        query = select(AndroidAiTestRow).where(*_scope(device_kind, device_id, serial))
        if cursor:
            try:
                stamp, last_id = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                at = _utc(stamp)
            except (ValueError, TypeError, AttributeError):
                raise AndroidError("ANDROID_INVALID_CURSOR", "分页游标无效", 400) from None
            query = query.where(or_(
                AndroidAiTestRow.created_at < at,
                and_(AndroidAiTestRow.created_at == at, AndroidAiTestRow.id < last_id),
            ))
        query = query.order_by(AndroidAiTestRow.created_at.desc(), AndroidAiTestRow.id.desc()).limit(limit + 1)
        with self.sessions() as session:
            rows = list(session.scalars(query))
            items = [_public(row) for row in rows[:limit]]
        next_cursor = None
        if len(rows) > limit:
            last = items[-1]
            next_cursor = base64.urlsafe_b64encode(json.dumps([last["createdAt"], last["id"]]).encode()).decode()
        return items, next_cursor

    def active_for(self, device_kind: str, device_id: str | None, serial: str | None) -> dict[str, Any] | None:
        query = select(AndroidAiTestRow).where(
            *_scope(device_kind, device_id, serial), AndroidAiTestRow.state.in_(ACTIVE_STATES),
        ).order_by(AndroidAiTestRow.created_at.desc()).limit(1)
        with self.sessions() as session:
            row = session.scalars(query).first()
            return None if row is None else _public(row)

    def unfinished(self) -> _Runs:
        with self.sessions() as session:
            rows = session.scalars(
                select(AndroidAiTestRow).where(AndroidAiTestRow.state.in_(ACTIVE_STATES))
                .order_by(AndroidAiTestRow.created_at)
            )
            return [_public(row) for row in rows]

    def delete(self, run_id: str) -> dict[str, Any]:
        with self.sessions.begin() as session:
            row = session.get(AndroidAiTestRow, run_id)
            if row is None:
                raise _not_found()
            public = _public(row)
            session.delete(row)
            return public
