from __future__ import annotations

import copy
from datetime import datetime
from typing import Any, cast

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.workflows.runs import (
    RunMode,
    RunStatus,
    TerminalRunStatus,
    WorkflowArtifact,
    WorkflowRun,
    WorkflowRunError,
    WorkflowRunEvent,
    WorkflowRunStart,
)

from .workflow_models import WorkflowRunArtifactRow, WorkflowRunEventRow, WorkflowRunRow


def _iso(value: datetime) -> str:
    return value.isoformat()


def _datetime(value: Any) -> datetime | None:
    return datetime.fromisoformat(value) if isinstance(value, str) and value else None


def _run(row: WorkflowRunRow) -> WorkflowRun:
    value = row.payload
    return WorkflowRun(
        run_id=row.id,
        workflow_id=row.workflow_id,
        request_hash=row.request_hash,
        document_id=str(value.get("documentId", "")),
        workflow_name=str(value.get("workflowName", "")),
        document_snapshot=copy.deepcopy(value.get("documentSnapshot", {})),
        layout_snapshot=copy.deepcopy(value.get("layoutSnapshot", {})),
        profile_id=str(value.get("profileId", "")),
        profile_snapshot=copy.deepcopy(value.get("profileSnapshot", {})),
        mode=cast(RunMode, value.get("mode", "run")),
        status=cast(RunStatus, value.get("status", "starting")),
        cleanup_state=cast(Any, value.get("cleanupState", "pending")),
        started_at=cast(datetime, _datetime(value.get("startedAt"))),
        finished_at=_datetime(value.get("finishedAt")),
        current_node_id=value.get("currentNodeId"),
        event_count=int(value.get("eventCount", 0)),
        log_count=int(value.get("logCount", 0)),
        stop_requested=bool(value.get("stopRequested", False)),
        error=copy.deepcopy(value.get("error")),
        custom_module_snapshots=copy.deepcopy(
            value.get("customModuleSnapshots", {})
        ),
    )


def _event(row: WorkflowRunEventRow) -> WorkflowRunEvent:
    value = row.payload
    return WorkflowRunEvent(
        run_id=row.run_id,
        sequence=row.seq,
        type=str(value.get("type", "")),
        occurred_at=cast(datetime, _datetime(value.get("occurredAt"))),
        payload=copy.deepcopy(value.get("payload", {})),
        node_id=value.get("nodeId"),
        execution_id=value.get("executionId"),
    )


def _artifact(row: WorkflowRunArtifactRow) -> WorkflowArtifact:
    value = row.payload
    return WorkflowArtifact(
        run_id=row.run_id,
        artifact_id=row.id,
        ordinal=row.ordinal,
        node_id=row.node_id,
        execution_id=row.execution_id,
        relative_path=str(value["relativePath"]),
        size=int(value["size"]),
        sha256=str(value["sha256"]),
        mime_type=str(value["mimeType"]),
        purpose=row.purpose,
        event_sequence=row.event_seq,
    )


class SqlAlchemyWorkflowRuns:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(
        self, start: WorkflowRunStart, *, request_hash: str, now: datetime
    ) -> WorkflowRun:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            previous = session.get(WorkflowRunRow, start.run_id)
            if previous is not None:
                if previous.request_hash != request_hash:
                    session.rollback()
                    raise WorkflowRunError(
                        "RUN_ID_CONFLICT", "运行 ID 已用于不同的请求", 409
                    )
                result = _run(previous)
                session.rollback()
                return result
            row = WorkflowRunRow(
                id=start.run_id,
                workflow_id=start.workflow_id,
                request_hash=request_hash,
                started_at=_iso(now),
                # Legacy Studio used slot 1 in the retired payload format. Keep
                # that data byte-for-byte compatible and reserve slot 2 for the
                # current managed worker lifecycle.
                active_slot=2,
                payload={
                    "documentId": start.document_id,
                    "workflowName": start.workflow_name,
                    "documentSnapshot": copy.deepcopy(start.document_snapshot),
                    "layoutSnapshot": copy.deepcopy(start.layout_snapshot),
                    "profileId": start.profile_id,
                    "profileSnapshot": copy.deepcopy(start.profile_snapshot),
                    "mode": start.mode,
                    "customModuleSnapshots": copy.deepcopy(
                        start.custom_module_snapshots
                    ),
                    "status": "starting",
                    "cleanupState": "pending",
                    "startedAt": _iso(now),
                    "finishedAt": None,
                    "currentNodeId": None,
                    "eventCount": 0,
                    "logCount": 0,
                    "stopRequested": False,
                    "error": None,
                },
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise WorkflowRunError(
                    "WORKFLOW_RUN_BUSY", "当前工作区已有活跃运行", 409
                ) from error
            return _run(row)

    def get(self, run_id: str) -> WorkflowRun | None:
        with self._session_factory() as session:
            row = session.get(WorkflowRunRow, run_id)
            return _run(row) if row is not None else None

    @staticmethod
    def _require_run(session: Session, run_id: str) -> WorkflowRunRow:
        row = session.get(WorkflowRunRow, run_id)
        if row is None:
            raise WorkflowRunError("RUN_NOT_FOUND", "运行记录不存在", 404)
        return row

    @staticmethod
    def _next_sequence(session: Session, run_id: str) -> int:
        value = session.scalar(
            select(func.coalesce(func.max(WorkflowRunEventRow.seq), 0)).where(
                WorkflowRunEventRow.run_id == run_id
            )
        )
        return int(value or 0) + 1

    def append_event(
        self,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        now: datetime,
        node_id: str | None = None,
        execution_id: str | None = None,
        run_patch: dict[str, Any] | None = None,
        artifact_ids: tuple[str, ...] = (),
    ) -> WorkflowRunEvent:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            run = self._require_run(session, run_id)
            if run.active_slot is None:
                session.rollback()
                raise WorkflowRunError("RUN_ALREADY_FINISHED", "运行已经结束", 409)
            sequence = self._next_sequence(session, run_id)
            event_row = WorkflowRunEventRow(
                run_id=run_id,
                seq=sequence,
                payload={
                    "type": event_type,
                    "occurredAt": _iso(now),
                    "payload": copy.deepcopy(payload),
                    "nodeId": node_id,
                    "executionId": execution_id,
                },
            )
            session.add(event_row)
            run_payload = copy.deepcopy(run.payload)
            if run_patch:
                run_payload.update(copy.deepcopy(run_patch))
            run_payload["eventCount"] = sequence
            if event_type == "execution:log":
                run_payload["logCount"] = int(run_payload.get("logCount", 0)) + 1
            run.payload = run_payload
            if artifact_ids:
                session.query(WorkflowRunArtifactRow).filter(
                    WorkflowRunArtifactRow.run_id == run_id,
                    WorkflowRunArtifactRow.id.in_(artifact_ids),
                ).update(
                    {WorkflowRunArtifactRow.event_seq: sequence},
                    synchronize_session=False,
                )
            session.commit()
            return _event(event_row)

    def list_events(
        self, run_id: str, after_sequence: int, limit: int
    ) -> tuple[WorkflowRunEvent, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(WorkflowRunEventRow)
                .where(
                    WorkflowRunEventRow.run_id == run_id,
                    WorkflowRunEventRow.seq > after_sequence,
                )
                .order_by(WorkflowRunEventRow.seq)
                .limit(limit)
            ).all()
            return tuple(_event(row) for row in rows)

    def list_runs(
        self, *, document_id: str | None, cursor: int, limit: int
    ) -> tuple[tuple[WorkflowRun, ...], int, int | None]:
        with self._session_factory() as session:
            statement = select(WorkflowRunRow)
            if document_id is not None:
                statement = statement.where(
                    WorkflowRunRow.payload["documentId"].as_string() == document_id
                )
            rows = session.scalars(
                statement.order_by(WorkflowRunRow.started_at.desc(), WorkflowRunRow.id)
            ).all()
            total = len(rows)
            page = rows[cursor : cursor + limit]
            next_cursor = cursor + len(page) if cursor + len(page) < total else None
            return tuple(_run(row) for row in page), total, next_cursor

    def finish(
        self,
        run_id: str,
        *,
        status: TerminalRunStatus,
        error: dict[str, Any] | None,
        terminal_log: dict[str, Any] | None,
        now: datetime,
    ) -> WorkflowRun:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            run = self._require_run(session, run_id)
            if run.active_slot is None:
                result = _run(run)
                if result.status != status:
                    session.rollback()
                    raise WorkflowRunError(
                        "RUN_ALREADY_FINISHED", "运行已经以其他状态结束", 409
                    )
                session.rollback()
                return result
            sequence = self._next_sequence(session, run_id)
            if terminal_log is not None:
                session.add(
                    WorkflowRunEventRow(
                        run_id=run_id,
                        seq=sequence,
                        payload={
                            "type": "execution:log",
                            "occurredAt": _iso(now),
                            "payload": copy.deepcopy(terminal_log),
                            "nodeId": None,
                            "executionId": None,
                        },
                    )
                )
                sequence += 1
            session.add(
                WorkflowRunEventRow(
                    run_id=run_id,
                    seq=sequence,
                    payload={
                        "type": f"execution:{status}",
                        "occurredAt": _iso(now),
                        "payload": {"error": copy.deepcopy(error)},
                        "nodeId": None,
                        "executionId": None,
                    },
                )
            )
            value = copy.deepcopy(run.payload)
            value.update(
                {
                    "status": status,
                    "cleanupState": "completed",
                    "finishedAt": _iso(now),
                    "eventCount": sequence,
                    "error": copy.deepcopy(error),
                }
            )
            if terminal_log is not None:
                value["logCount"] = int(value.get("logCount", 0)) + 1
            run.payload = value
            run.active_slot = None
            session.commit()
            return _run(run)

    def recover_interrupted(self, *, now: datetime) -> tuple[WorkflowRun, ...]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            candidates = session.scalars(
                select(WorkflowRunRow)
                .where(WorkflowRunRow.active_slot.is_not(None))
                .order_by(WorkflowRunRow.started_at, WorkflowRunRow.id)
            ).all()
            rows = [
                row
                for row in candidates
                if row.payload.get("status") in {"starting", "running", "paused"}
                and row.payload.get("cleanupState") == "pending"
            ]
            for run in rows:
                sequence = self._next_sequence(session, run.id)
                session.add(
                    WorkflowRunEventRow(
                        run_id=run.id,
                        seq=sequence,
                        payload={
                            "type": "execution:interrupted",
                            "occurredAt": _iso(now),
                            "payload": {"reason": "service-restarted"},
                            "nodeId": None,
                            "executionId": None,
                        },
                    )
                )
                value = copy.deepcopy(run.payload)
                value.update(
                    {
                        "status": "interrupted",
                        "cleanupState": "completed",
                        "finishedAt": _iso(now),
                        "eventCount": sequence,
                        "error": {
                            "code": "RUN_INTERRUPTED",
                            "message": "服务重启，运行不会自动重放",
                        },
                    }
                )
                run.payload = value
                run.active_slot = None
            session.commit()
            return tuple(_run(row) for row in rows)

    def register_artifact(
        self,
        *,
        run_id: str,
        artifact_id: str,
        node_id: str,
        execution_id: str | None,
        relative_path: str,
        size: int,
        sha256: str,
        mime_type: str,
        purpose: str,
    ) -> WorkflowArtifact:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            self._require_run(session, run_id)
            existing = session.scalars(
                select(WorkflowRunArtifactRow).where(
                    WorkflowRunArtifactRow.run_id == run_id
                )
            ).all()
            if any(
                row.payload.get("relativePath") == relative_path for row in existing
            ):
                session.rollback()
                raise WorkflowRunError("ARTIFACT_ALREADY_EXISTS", "产物文件已存在", 409)
            ordinal_value = session.scalar(
                select(
                    func.coalesce(func.max(WorkflowRunArtifactRow.ordinal), 0)
                ).where(WorkflowRunArtifactRow.run_id == run_id)
            )
            row = WorkflowRunArtifactRow(
                run_id=run_id,
                id=artifact_id,
                ordinal=int(ordinal_value or 0) + 1,
                node_id=node_id,
                execution_id=execution_id,
                payload={
                    "relativePath": relative_path,
                    "size": size,
                    "sha256": sha256,
                    "mimeType": mime_type,
                },
                purpose=purpose,
                event_seq=0,
            )
            session.add(row)
            session.commit()
            return _artifact(row)

    def list_artifacts(
        self, run_id: str, *, cursor: int, limit: int
    ) -> tuple[WorkflowArtifact, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(WorkflowRunArtifactRow)
                .where(
                    WorkflowRunArtifactRow.run_id == run_id,
                    WorkflowRunArtifactRow.ordinal > cursor,
                )
                .order_by(WorkflowRunArtifactRow.ordinal)
                .limit(limit)
            ).all()
            return tuple(_artifact(row) for row in rows)

    def get_artifact(self, run_id: str, artifact_id: str) -> WorkflowArtifact | None:
        with self._session_factory() as session:
            row = session.get(
                WorkflowRunArtifactRow,
                {"run_id": run_id, "id": artifact_id},
            )
            return _artifact(row) if row is not None else None
