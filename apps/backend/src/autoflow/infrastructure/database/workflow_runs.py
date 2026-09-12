from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from threading import RLock
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.runs import ACTIVE_RUN_STATES, RunRecord

from .models import WorkflowRunEventRow, WorkflowRunRow


class SqlAlchemyWorkflowRunRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._sessions = session_factory
        self._lock = RLock()

    def get(self, run_id: str) -> RunRecord | None:
        with self._sessions() as session:
            row = session.get(WorkflowRunRow, run_id)
            return _record(row) if row else None

    def create(self, record: RunRecord) -> RunRecord:
        try:
            with self._lock, self._sessions.begin() as session:
                session.add(WorkflowRunRow(
                    id=record.data["runId"], workflow_id=record.data["workflowId"],
                    request_hash=record.request_hash, started_at=record.data["startedAt"],
                    active_slot=1, payload=deepcopy(record.data),
                ))
                session.flush()
                session.add(WorkflowRunEventRow(run_id=record.data["runId"], seq=1, payload={
                    "runId": record.data["runId"], "seq": 1, "timestamp": record.data["startedAt"],
                    "type": "accepted", "nodeId": None, "level": "info",
                    "message": "已接受当前草稿快照，正在启动浏览器", "durationMs": None,
                    "artifactId": None, "error": None,
                }))
        except IntegrityError:
            existing = self.get(record.data["runId"])
            if existing is not None:
                if existing.request_hash == record.request_hash:
                    return existing
                raise WorkflowError("WORKFLOW_RUN_ID_CONFLICT", "运行标识已用于不同请求", 409) from None
            raise WorkflowError("WORKFLOW_RUN_BUSY", "当前工作区已有运行，请先停止或等待完成", 409) from None
        return record

    def active_id(self) -> str | None:
        with self._sessions() as session:
            return session.scalar(select(WorkflowRunRow.id).where(WorkflowRunRow.active_slot == 1))

    def list_runs(self, workflow_id: str | None, offset: int, limit: int) -> list[RunRecord]:
        query = select(WorkflowRunRow)
        if workflow_id is not None:
            query = query.where(WorkflowRunRow.workflow_id == workflow_id)
        with self._sessions() as session:
            return [_record(row) for row in session.scalars(
                query.order_by(WorkflowRunRow.started_at.desc(), WorkflowRunRow.id.desc()).offset(offset).limit(limit)
            )]

    def append(
        self, run_id: str, event: dict[str, Any], changes: dict[str, Any]
    ) -> dict[str, Any]:
        # A workspace admits one worker; this lock also serializes recovery/control writes.
        with self._lock, self._sessions.begin() as session:
            row = session.get(WorkflowRunRow, run_id)
            if row is None:
                raise WorkflowError("WORKFLOW_RUN_NOT_FOUND", "运行记录不存在", 404)
            payload = {**row.payload, **deepcopy(changes)}
            seq = row.payload["latestSeq"] + 1
            timestamp = datetime.now(UTC).isoformat()
            stored = {
                "runId": run_id, "seq": seq, "timestamp": timestamp,
                "type": "log", "nodeId": None, "level": "info", "message": "",
                "durationMs": None, "artifactId": None, "error": None,
                **deepcopy(event),
            }
            stored.update(runId=run_id, seq=seq, timestamp=timestamp)
            payload["latestSeq"] = seq
            row.payload = payload
            row.active_slot = 1 if payload["state"] in ACTIVE_RUN_STATES else None
            session.add(WorkflowRunEventRow(run_id=run_id, seq=seq, payload=stored))
        return stored

    def events(self, run_id: str, after_seq: int, limit: int) -> list[dict[str, Any]]:
        with self._sessions() as session:
            return [deepcopy(row.payload) for row in session.scalars(
                select(WorkflowRunEventRow).where(
                    WorkflowRunEventRow.run_id == run_id, WorkflowRunEventRow.seq > after_seq,
                ).order_by(WorkflowRunEventRow.seq).limit(limit)
            )]

    def recover_interrupted(self) -> None:
        run_id = self.active_id()
        if run_id is not None:
            error: dict[str, Any] = {"code": "WORKFLOW_RUN_INTERRUPTED", "message": "本地服务退出，运行已中断；不会自动重放", "nodeId": None, "path": []}
            self.append(run_id, {"type": "interrupted", "level": "error", "message": error["message"], "error": error}, {
                "state": "interrupted", "finishedAt": datetime.now(UTC).isoformat(), "error": error,
            })


def _record(row: WorkflowRunRow) -> RunRecord:
    return RunRecord(row.request_hash, deepcopy(row.payload))
