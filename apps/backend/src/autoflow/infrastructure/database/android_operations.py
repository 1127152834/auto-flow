import threading
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.android.ports import AndroidError

from .android_models import AndroidDeviceRow, AndroidOperationRow

_LABELS = {"queued": "排队中", "running": "执行中", "waiting_capacity": "等待容量", "succeeded": "已完成", "failed": "失败", "cancelled": "已取消", "needs_verification": "待核实"}
_TRANSITIONS = {
    "queued": {"running", "waiting_capacity", "cancelled", "failed", "needs_verification"},
    "waiting_capacity": {"running", "cancelled", "failed", "needs_verification"},
    "running": {"running", "succeeded", "failed", "needs_verification"},
    "needs_verification": {"needs_verification", "succeeded", "failed"},
}


class OperationRecord:
    def __init__(self, row: AndroidOperationRow) -> None:
        self.operation_id = row.id
        self.workspace_identity = row.workspace_identity
        self.payload = deepcopy(row.payload)
        self.request_id = row.request_id
        self.target_id = row.target_id
        self.action = row.action
        self.state = row.state
        self.stage_code = row.stage_code
        self.stage_label = row.stage_label
        self.attempt = row.attempt
        self.retry_of = row.retry_of
        self.result_code = row.result_code
        self.message = row.message
        self.created_at = row.created_at
        self.started_at = row.started_at
        self.finished_at = row.finished_at


class SqlAlchemyAndroidOperationRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions
        self._accept_lock = threading.Lock()

    def accept(
        self,
        workspace_identity: str,
        request_id: str,
        target_id: str,
        action: str,
        request_digest: str,
        payload: dict[str, Any],
        retry_of: str | None = None,
    ) -> OperationRecord:
        # ponytail: one backend process uses one lock; add a database uniqueness constraint if multi-process retries matter.
        with self._accept_lock:
            return self._accept_unlocked(workspace_identity, request_id, target_id, action, request_digest, payload, retry_of)

    def _accept_unlocked(
        self,
        workspace_identity: str,
        request_id: str,
        target_id: str,
        action: str,
        request_digest: str,
        payload: dict[str, Any],
        retry_of: str | None = None,
    ) -> OperationRecord:
        if len(target_id) > 36:
            raise AndroidError("ANDROID_OPERATION_TARGET_INVALID", "操作目标编号超过持久化长度限制", 422)
        if retry_of is not None and len(retry_of) > 36:
            raise AndroidError("ANDROID_RETRY_INVALID", "原操作编号无效", 422)
        with self.sessions.begin() as session:
            existing = session.scalar(select(AndroidOperationRow).where(AndroidOperationRow.workspace_identity == workspace_identity, AndroidOperationRow.request_id == request_id))
            if existing is not None:
                if existing.target_id != target_id or existing.action != action or existing.request_digest != request_digest:
                    raise AndroidError("ANDROID_OPERATION_IDEMPOTENCY_CONFLICT", "请求编号已用于不同操作", 409)
                return OperationRecord(existing)
            attempt = 1
            if retry_of is not None:
                parent = session.get(AndroidOperationRow, retry_of)
                if (
                    parent is None
                    or parent.workspace_identity != workspace_identity
                    or parent.target_id != target_id
                    or parent.action != action
                    or parent.state != "failed"
                ):
                    raise AndroidError("ANDROID_RETRY_INVALID", "只能重试同一设备上已失败的原操作", 409)
                attempt = parent.attempt + 1
            now = datetime.now(UTC)
            row = AndroidOperationRow(id=str(uuid4()), workspace_identity=workspace_identity, request_id=request_id, target_id=target_id, action=action, request_digest=request_digest, payload=deepcopy(payload), state="queued", stage_code="queued", stage_label=_LABELS["queued"], attempt=attempt, retry_of=retry_of, created_at=now)
            session.add(row)
            try:
                session.flush()
            except IntegrityError as error:
                raise AndroidError("ANDROID_OPERATION_RETRY", "操作已被其他请求接收，请重新查询", 409) from error
            return OperationRecord(row)

    def get(self, operation_id: str, workspace_identity: str | None = None) -> OperationRecord:
        with self.sessions() as session:
            row = session.get(AndroidOperationRow, operation_id)
            if row is None or (workspace_identity is not None and row.workspace_identity != workspace_identity):
                raise AndroidError("ANDROID_OPERATION_NOT_FOUND", "安卓操作不存在", 404)
            return OperationRecord(row)

    def by_request(self, workspace_identity: str, request_id: str) -> OperationRecord:
        with self.sessions() as session:
            row = session.scalar(select(AndroidOperationRow).where(AndroidOperationRow.workspace_identity == workspace_identity, AndroidOperationRow.request_id == request_id))
            if row is None:
                raise AndroidError("ANDROID_OPERATION_NOT_FOUND", "安卓操作不存在", 404)
            return OperationRecord(row)

    def page(self, device_id: str | None = None, cursor: str | None = None, limit: int = 50, workspace_identity: str | None = None) -> list[OperationRecord]:
        with self.sessions() as session:
            query = select(AndroidOperationRow).order_by(AndroidOperationRow.created_at.desc(), AndroidOperationRow.id.desc()).limit(min(max(limit, 1), 200))
            if workspace_identity is not None:
                query = query.where(AndroidOperationRow.workspace_identity == workspace_identity)
            if device_id:
                query = query.where(AndroidOperationRow.target_id == device_id)
            if cursor:
                boundary = session.get(AndroidOperationRow, cursor)
                if boundary is None:
                    raise AndroidError("ANDROID_OPERATION_CURSOR_INVALID", "分页位置无效", 422)
                query = query.where(or_(AndroidOperationRow.created_at < boundary.created_at, and_(AndroidOperationRow.created_at == boundary.created_at, AndroidOperationRow.id < cursor)))
            return [OperationRecord(row) for row in session.scalars(query)]

    def count(self, device_id: str | None = None, workspace_identity: str | None = None) -> int:
        with self.sessions() as session:
            query = select(func.count()).select_from(AndroidOperationRow)
            if workspace_identity is not None:
                query = query.where(AndroidOperationRow.workspace_identity == workspace_identity)
            if device_id:
                query = query.where(AndroidOperationRow.target_id == device_id)
            return int(session.scalar(query) or 0)

    def transition(self, operation_id: str, expected_state: str, next_state: str, changes: dict[str, Any]) -> OperationRecord:
        if next_state not in _TRANSITIONS.get(expected_state, set()):
            raise AndroidError("ANDROID_OPERATION_STATE_INVALID", "操作状态无效", 422)
        with self.sessions.begin() as session:
            row = session.get(AndroidOperationRow, operation_id)
            if row is None:
                raise AndroidError("ANDROID_OPERATION_NOT_FOUND", "安卓操作不存在", 404)
            if row.state != expected_state:
                raise AndroidError("ANDROID_OPERATION_STATE_CONFLICT", "操作状态已变化，请先核实", 409)
            values = {"state": next_state, "stage_code": str(changes.get("stage_code", next_state)), "stage_label": str(changes.get("stage_label", _LABELS[next_state]))}
            for key in ("result_code", "message"):
                if key in changes:
                    values[key] = changes[key]
            if next_state == "running" and row.started_at is None:
                values["started_at"] = datetime.now(UTC)
            if next_state in {"succeeded", "failed", "cancelled", "needs_verification"}:
                values["finished_at"] = datetime.now(UTC)
            result = session.execute(update(AndroidOperationRow).where(AndroidOperationRow.id == operation_id, AndroidOperationRow.state == expected_state).values(**values))
            if cast(CursorResult, result).rowcount != 1:
                raise AndroidError("ANDROID_OPERATION_STATE_CONFLICT", "操作状态已变化，请先核实", 409)
            session.refresh(row)
            return OperationRecord(row)

    def transition_with_device(self, operation_id: str, expected_state: str, next_state: str, changes: dict[str, Any], device: dict[str, Any]) -> OperationRecord:
        """Commit an operation transition and its device projection in one SQLite transaction."""
        if next_state not in _TRANSITIONS.get(expected_state, set()):
            raise AndroidError("ANDROID_OPERATION_STATE_INVALID", "操作状态无效", 422)
        with self.sessions.begin() as session:
            row = session.get(AndroidOperationRow, operation_id)
            if row is None:
                raise AndroidError("ANDROID_OPERATION_NOT_FOUND", "安卓操作不存在", 404)
            if row.state != expected_state:
                raise AndroidError("ANDROID_OPERATION_STATE_CONFLICT", "操作状态已变化，请先核实", 409)
            values = {"state": next_state, "stage_code": str(changes.get("stage_code", next_state)), "stage_label": str(changes.get("stage_label", _LABELS[next_state]))}
            for key in ("result_code", "message"):
                if key in changes:
                    values[key] = changes[key]
            if next_state == "running" and row.started_at is None:
                values["started_at"] = datetime.now(UTC)
            if next_state in {"succeeded", "failed", "cancelled", "needs_verification"}:
                values["finished_at"] = datetime.now(UTC)
            result = session.execute(update(AndroidOperationRow).where(AndroidOperationRow.id == operation_id, AndroidOperationRow.state == expected_state).values(**values))
            if cast(CursorResult, result).rowcount != 1:
                raise AndroidError("ANDROID_OPERATION_STATE_CONFLICT", "操作状态已变化，请先核实", 409)
            session.merge(AndroidDeviceRow(id=device["deviceId"], owner_run_id=device.get("ownerRunId"), payload=deepcopy(device)))
            session.refresh(row)
            return OperationRecord(row)

    def recover_running(self, workspace_identity: str) -> int:
        with self.sessions.begin() as session:
            rows = list(session.scalars(select(AndroidOperationRow).where(AndroidOperationRow.workspace_identity == workspace_identity, AndroidOperationRow.state == "running")))
            now = datetime.now(UTC)
            for row in rows:
                row.state = "needs_verification"
                row.stage_code = "verify"
                row.stage_label = _LABELS["needs_verification"]
                row.result_code = "SERVICE_RESTART_RESULT_UNKNOWN"
                row.message = "服务已重启，请核实外部操作结果"
                row.finished_at = now
            return len(rows)

    def compact(self, before: datetime) -> int:
        with self.sessions.begin() as session:
            result = session.execute(update(AndroidOperationRow).where(AndroidOperationRow.finished_at < before, AndroidOperationRow.state.in_(["succeeded", "failed", "cancelled"]), AndroidOperationRow.payload != {}).values(payload={}))
            return int(cast(CursorResult, result).rowcount or 0)
