from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import String, func, literal, select, text, union_all
from sqlalchemy import cast as sql_cast
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.projects.models import ProjectError
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

from .projects import guard_project
from .workflow_models import (
    WorkflowDebugCommandRow,
    WorkflowDocumentRow,
    WorkflowRunArtifactRow,
    WorkflowRunEventRow,
    WorkflowRunRow,
)
from .workflow_project_scope import (
    readable_studio_run_project,
    studio_run_project_expression,
    workflow_project_id,
)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _datetime(value: Any) -> datetime | None:
    return datetime.fromisoformat(value) if isinstance(value, str) and value else None


def _run(row: WorkflowRunRow, project_id: str | None = None) -> WorkflowRun:
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
        project_id=value.get("projectId") or project_id,
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
            # Admission and the active slot are committed together. Resolve
            # saved ownership even when the editor sends only an unsaved graph.
            project_id = start.project_id
            snapshot_project = start.document_snapshot.get("projectId")
            if snapshot_project is not None:
                if (
                    not isinstance(snapshot_project, str)
                    or not snapshot_project.strip()
                    or len(snapshot_project) > 200
                ):
                    raise WorkflowRunError("RUN_REQUEST_INVALID", "项目标识无效", 422)
                if project_id is not None and project_id != snapshot_project:
                    raise WorkflowRunError("WORKFLOW_PROJECT_MISMATCH", "工作流不属于当前项目", 404)
                project_id = snapshot_project
            owners = {
                workflow_project_id(session, identifier)
                for identifier in {start.workflow_id, start.document_id}
                if session.get(WorkflowDocumentRow, identifier) is not None
            }
            if len(owners) > 1 or (
                owners and project_id is not None and project_id not in owners
            ):
                raise WorkflowRunError("WORKFLOW_PROJECT_MISMATCH", "工作流不属于当前项目", 404)
            if owners:
                project_id = next(iter(owners))
            if project_id is not None:
                try:
                    guard_project(session, project_id)
                except ProjectError as error:
                    raise WorkflowRunError(
                        error.code, error.message, error.status, error.details
                    ) from error
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
                    "projectId": project_id,
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
            record = session.execute(select(WorkflowRunRow, studio_run_project_expression()).where(
                WorkflowRunRow.id == run_id, readable_studio_run_project(),
            )).first()
            return _run(record[0], record[1]) if record is not None else None

    @staticmethod
    def _require_run(session: Session, run_id: str) -> WorkflowRunRow:
        row = session.get(WorkflowRunRow, run_id)
        if row is None:
            raise WorkflowRunError("RUN_NOT_FOUND", "运行记录不存在", 404)
        return row

    def belongs_to_project(self, run_id: str, project_id: str) -> bool:
        with self._session_factory() as session:
            return session.scalar(select(WorkflowRunRow.id).where(
                WorkflowRunRow.id == run_id,
                studio_run_project_expression() == project_id,
                readable_studio_run_project(),
            )) is not None

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

    def project_assets(
        self, project_id: str, *, kind: str | None, run_id: str | None,
        node_id: str | None, cursor: int, limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        run, event, artifact = WorkflowRunRow, WorkflowRunEventRow, WorkflowRunArtifactRow
        identity = [run.id.label("runId"), run.workflow_id.label("workflowId"),
                    run.payload["workflowName"].as_string().label("workflowName")]
        result_rows = select(
            (literal("result:") + run.id + literal(":") + sql_cast(event.seq, String)).label("assetId"),
            *identity, literal("result").label("kind"), event.seq.label("sequence"),
            event.payload["nodeId"].as_string().label("nodeId"),
            event.payload["executionId"].as_string().label("executionId"),
            event.payload["occurredAt"].as_string().label("createdAt"),
            literal(None).label("artifactId"), literal("application/json").label("mimeType"),
            literal(None).label("size"), literal(None).label("sha256"),
        ).select_from(run).join(event, event.run_id == run.id).where(
            event.payload["type"].as_string() == "execution:node-succeeded",
            event.payload["nodeId"].as_string().is_not(None),
            func.json_type(event.payload, "$.payload.result.data").not_in(("null",)),
            studio_run_project_expression() == project_id, readable_studio_run_project(),
        )
        from sqlalchemy import case

        file_rows = select(
            (literal("file:") + run.id + literal(":") + artifact.id).label("assetId"),
            *identity, case((artifact.purpose == "diagnostic", "diagnostic"), else_="file").label("kind"),
            artifact.event_seq.label("sequence"), artifact.node_id.label("nodeId"), artifact.execution_id.label("executionId"),
            func.coalesce(artifact.payload["registeredAt"].as_string(), event.payload["occurredAt"].as_string()).label("createdAt"),
            artifact.id.label("artifactId"), artifact.payload["mimeType"].as_string().label("mimeType"),
            artifact.payload["size"].as_integer().label("size"), artifact.payload["sha256"].as_string().label("sha256"),
        ).select_from(run).join(artifact, artifact.run_id == run.id).outerjoin(
            event, (event.run_id == run.id) & (event.seq == artifact.event_seq),
        ).where(studio_run_project_expression() == project_id, readable_studio_run_project())
        assets = union_all(result_rows, file_rows).subquery()
        query = select(assets)
        for column, value in ((assets.c.kind, kind), (assets.c.runId, run_id), (assets.c.nodeId, node_id)):
            if value is not None:
                query = query.where(column == value)
        with self._session_factory() as session:
            guard_project(session, project_id, writable=False)
            total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
            page = session.execute(query.order_by(assets.c.createdAt.desc(), assets.c.assetId).offset(cursor).limit(limit)).mappings()
            return [{"projectId": project_id, **dict(row)} for row in page], total

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
        self, *, document_id: str | None, cursor: int, limit: int,
        project_id: str | None = None,
    ) -> tuple[tuple[WorkflowRun, ...], int, int | None]:
        with self._session_factory() as session:
            statement = select(WorkflowRunRow, studio_run_project_expression()).where(readable_studio_run_project())
            if project_id is not None:
                statement = statement.where(studio_run_project_expression() == project_id)
            if document_id is not None:
                statement = statement.where(
                    WorkflowRunRow.payload["documentId"].as_string() == document_id
                )
            total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
            page = session.execute(
                statement.order_by(WorkflowRunRow.started_at.desc(), WorkflowRunRow.id).offset(cursor).limit(limit)
            ).all()
            next_cursor = cursor + len(page) if cursor + len(page) < total else None
            return tuple(_run(row, owner) for row, owner in page), total, next_cursor

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
                if row.payload.get("status") in {"starting", "running", "paused", "failed_paused"}
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
                    "registeredAt": _iso(datetime.now(UTC)),
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

    def save_debug_command(
        self,
        run_id: str,
        command_id: str,
        *,
        request_hash: str,
        receipt: dict[str, Any],
        http_status: int,
    ) -> tuple[str, dict[str, Any], int]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = session.scalar(
                select(WorkflowDebugCommandRow)
                .where(WorkflowDebugCommandRow.id == command_id)
                .order_by(WorkflowDebugCommandRow.run_id)
            )
            if existing is not None:
                result = self._debug_command(existing)
                session.rollback()
                return result
            self._require_run(session, run_id)
            row = WorkflowDebugCommandRow(
                run_id=run_id,
                id=command_id,
                request_hash=request_hash,
                payload={
                    "receipt": copy.deepcopy(receipt),
                    "httpStatus": http_status,
                },
            )
            session.add(row)
            session.commit()
            return self._debug_command(row)

    def get_debug_command(
        self, command_id: str
    ) -> tuple[str, dict[str, Any], int] | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(WorkflowDebugCommandRow)
                .where(WorkflowDebugCommandRow.id == command_id)
                .order_by(WorkflowDebugCommandRow.run_id)
            )
            return self._debug_command(row) if row is not None else None

    def clear_variable_tracking(
        self, run_id: str, *, now: datetime
    ) -> WorkflowRunEvent:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            run = self._require_run(session, run_id)
            sequence = self._next_sequence(session, run_id)
            row = WorkflowRunEventRow(
                run_id=run_id,
                seq=sequence,
                payload={
                    "type": "execution:variables_cleared",
                    "occurredAt": _iso(now),
                    "payload": {},
                    "nodeId": None,
                    "executionId": None,
                },
            )
            session.add(row)
            value = copy.deepcopy(run.payload)
            value["eventCount"] = sequence
            run.payload = value
            session.commit()
            return _event(row)

    @staticmethod
    def _debug_command(
        row: WorkflowDebugCommandRow,
    ) -> tuple[str, dict[str, Any], int]:
        payload = copy.deepcopy(row.payload)
        receipt = payload.get("receipt")
        if not isinstance(receipt, dict):
            receipt = payload
        status = payload.get("httpStatus")
        if not isinstance(status, int):
            status = 200 if receipt.get("success") is True else 409
        return row.request_hash, receipt, status
