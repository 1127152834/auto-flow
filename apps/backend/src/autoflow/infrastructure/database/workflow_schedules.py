from __future__ import annotations

import builtins
import copy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.workflows.models import WorkflowError

from .workflow_models import ScheduledTaskExecutionRow, ScheduledTaskRow


class SqlAlchemyWorkflowSchedules:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def list(self) -> builtins.list[dict[str, Any]]:
        with self._sessions() as database:
            rows = database.scalars(select(ScheduledTaskRow).order_by(ScheduledTaskRow.created_at)).all()
            return [self._payload(row) for row in rows]

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._sessions() as database:
            row = database.get(ScheduledTaskRow, task_id)
            return self._payload(row) if row else None

    def create(self, task_id: str, payload: dict[str, Any], now: datetime) -> dict[str, Any]:
        with self._sessions() as database:
            row = ScheduledTaskRow(
                id=task_id,
                workflow_id=str(payload["workflow_id"]),
                payload=copy.deepcopy(payload),
                revision=1,
                enabled=bool(payload.get("enabled", True)),
                is_running=False,
                next_execution_time=None,
                created_at=now,
                updated_at=now,
            )
            database.add(row)
            database.commit()
            return self._payload(row)

    def update(
        self,
        task_id: str,
        changes: dict[str, Any],
        expected_revision: int | None,
        now: datetime,
    ) -> dict[str, Any]:
        with self._sessions() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            row = database.get(ScheduledTaskRow, task_id)
            if row is None:
                raise WorkflowError("SCHEDULED_TASK_NOT_FOUND", "计划任务不存在", 404)
            if expected_revision is not None and row.revision != expected_revision:
                raise WorkflowError(
                    "SCHEDULED_TASK_REVISION_CONFLICT",
                    "计划任务已被修改，请重新读取后再保存",
                    409,
                    details={"expectedRevision": expected_revision, "currentRevision": row.revision},
                )
            payload = {**row.payload, **copy.deepcopy(changes)}
            row.payload = payload
            row.workflow_id = str(payload["workflow_id"])
            row.enabled = bool(payload.get("enabled", True))
            row.revision += 1
            row.updated_at = now
            database.commit()
            return self._payload(row)

    def delete(self, task_id: str) -> None:
        with self._sessions() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            row = database.get(ScheduledTaskRow, task_id)
            if row is None:
                raise WorkflowError("SCHEDULED_TASK_NOT_FOUND", "计划任务不存在", 404)
            pending = database.scalar(
                select(ScheduledTaskExecutionRow.id).where(
                    ScheduledTaskExecutionRow.task_id == task_id,
                    ScheduledTaskExecutionRow.status.in_(("queued", "running")),
                )
            )
            if row.is_running or pending is not None:
                raise WorkflowError("SCHEDULED_TASK_RUNNING", "计划任务正在运行，不能删除", 409)
            database.delete(row)
            database.commit()

    def enqueue_execution(
        self,
        task_id: str,
        execution_id: str,
        occurrence_key: str,
        payload: dict[str, Any],
        now: datetime,
        *,
        due_at: datetime | None = None,
        next_execution_time: datetime | None = None,
        advance_schedule: bool = False,
        disable_after_claim: bool = False,
    ) -> tuple[dict[str, Any], bool]:
        with self._sessions() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            existing = database.scalar(
                select(ScheduledTaskExecutionRow).where(
                    ScheduledTaskExecutionRow.task_id == task_id,
                    ScheduledTaskExecutionRow.occurrence_key == occurrence_key,
                )
            )
            if existing is not None:
                database.rollback()
                return copy.deepcopy(existing.payload), False
            active = database.scalar(
                select(ScheduledTaskExecutionRow.id).where(
                    ScheduledTaskExecutionRow.task_id == task_id,
                    ScheduledTaskExecutionRow.status.in_(("queued", "running")),
                )
            )
            if active is not None:
                database.rollback()
                raise WorkflowError(
                    "SCHEDULED_TASK_RUNNING", "计划任务已在执行或等待执行", 409
                )
            task = database.get(ScheduledTaskRow, task_id)
            if task is None:
                database.rollback()
                raise WorkflowError("SCHEDULED_TASK_NOT_FOUND", "计划任务不存在", 404)
            task.is_running = True
            if advance_schedule:
                task.next_execution_time = next_execution_time
                if disable_after_claim:
                    task.enabled = False
                    task_payload = dict(task.payload)
                    task_payload["enabled"] = False
                    task.payload = task_payload
            task.updated_at = now
            row = ScheduledTaskExecutionRow(
                id=execution_id,
                task_id=task_id,
                occurrence_key=occurrence_key,
                status="queued",
                due_at=due_at or now,
                payload={**copy.deepcopy(payload), "status": "queued"},
                created_at=now,
                started_at=None,
                updated_at=now,
            )
            database.add(row)
            try:
                database.commit()
            except IntegrityError:
                database.rollback()
                existing = database.scalar(
                    select(ScheduledTaskExecutionRow).where(
                        ScheduledTaskExecutionRow.task_id == task_id,
                        ScheduledTaskExecutionRow.occurrence_key == occurrence_key,
                    )
                )
                if existing is None:
                    raise
                return copy.deepcopy(existing.payload), False
            return copy.deepcopy(row.payload), True

    def claim_next(self, now: datetime) -> dict[str, Any] | None:
        with self._sessions() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            if database.scalar(
                select(ScheduledTaskExecutionRow.id).where(
                    ScheduledTaskExecutionRow.status == "running"
                )
            ) is not None:
                database.rollback()
                return None
            row = database.scalar(
                select(ScheduledTaskExecutionRow)
                .where(
                    ScheduledTaskExecutionRow.status == "queued",
                    ScheduledTaskExecutionRow.due_at <= now,
                )
                .order_by(
                    ScheduledTaskExecutionRow.due_at,
                    ScheduledTaskExecutionRow.created_at,
                    ScheduledTaskExecutionRow.id,
                )
                .limit(1)
            )
            if row is None:
                database.rollback()
                return None
            task = database.get(ScheduledTaskRow, row.task_id)
            if task is None:
                database.rollback()
                return None
            row.status = "running"
            row.started_at = now
            row.updated_at = now
            row.payload = {
                **row.payload,
                "status": "running",
                "start_time": self._iso(now),
            }
            task.is_running = True
            task.updated_at = now
            database.commit()
            return copy.deepcopy(row.payload)

    def requeue_execution(
        self, execution_id: str, *, due_at: datetime, now: datetime
    ) -> dict[str, Any]:
        with self._sessions() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            row = database.get(ScheduledTaskExecutionRow, execution_id)
            if row is None:
                raise WorkflowError(
                    "SCHEDULED_EXECUTION_NOT_FOUND", "计划任务执行记录不存在", 404
                )
            task = database.get(ScheduledTaskRow, row.task_id)
            if task is None:
                raise WorkflowError("SCHEDULED_TASK_NOT_FOUND", "计划任务不存在", 404)
            row.status = "queued"
            row.due_at = due_at
            row.started_at = None
            row.updated_at = now
            payload = dict(row.payload)
            payload.update(status="queued", start_time=None, run_id=None, run_status="queued")
            row.payload = payload
            task.is_running = True
            task.updated_at = now
            database.commit()
            return copy.deepcopy(payload)

    def attach_run(
        self,
        execution_id: str,
        *,
        run_id: str,
        run_status: str,
        now: datetime,
    ) -> dict[str, Any]:
        with self._sessions() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            row = database.get(ScheduledTaskExecutionRow, execution_id)
            if row is None:
                raise WorkflowError(
                    "SCHEDULED_EXECUTION_NOT_FOUND", "计划任务执行记录不存在", 404
                )
            if row.status != "running":
                database.rollback()
                return copy.deepcopy(row.payload)
            row.payload = {
                **row.payload,
                "run_id": run_id,
                "run_status": run_status,
            }
            row.updated_at = now
            database.commit()
            return copy.deepcopy(row.payload)

    def stop_queued(self, task_id: str, now: datetime) -> dict[str, Any] | None:
        with self._sessions() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            row = database.scalar(
                select(ScheduledTaskExecutionRow)
                .where(
                    ScheduledTaskExecutionRow.task_id == task_id,
                    ScheduledTaskExecutionRow.status == "queued",
                )
                .order_by(ScheduledTaskExecutionRow.created_at.desc())
                .limit(1)
            )
            if row is None:
                database.rollback()
                return None
            row.status = "stopped"
            row.updated_at = now
            row.payload = {
                **row.payload,
                "status": "stopped",
                "end_time": self._iso(now),
                "duration": 0.0,
                "run_status": "stopped",
            }
            task = database.get(ScheduledTaskRow, row.task_id)
            if task is not None:
                task.is_running = False
                task.updated_at = now
            database.commit()
            return copy.deepcopy(row.payload)

    def has_pending(self) -> bool:
        with self._sessions() as database:
            return database.scalar(
                select(ScheduledTaskExecutionRow.id).where(
                    ScheduledTaskExecutionRow.status.in_(("queued", "running"))
                )
            ) is not None

    def finish_execution(
        self,
        execution_id: str,
        *,
        status: str,
        error: str | None,
        run_id: str | None,
        now: datetime,
        notification_results: builtins.list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        with self._sessions() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            execution = database.get(ScheduledTaskExecutionRow, execution_id)
            if execution is None:
                raise WorkflowError("SCHEDULED_EXECUTION_NOT_FOUND", "计划任务执行记录不存在", 404)
            task = database.get(ScheduledTaskRow, execution.task_id)
            if task is None:
                raise WorkflowError("SCHEDULED_TASK_NOT_FOUND", "计划任务不存在", 404)
            if execution.status != "running":
                database.rollback()
                return copy.deepcopy(execution.payload)
            payload = {
                **execution.payload,
                "status": status,
                "error": error,
                "run_id": run_id,
                "end_time": self._iso(now),
                "duration": max(
                    0.0,
                    (now - self._aware(execution.started_at or execution.created_at)).total_seconds(),
                ),
                **({"notification_results": notification_results} if notification_results is not None else {}),
            }
            execution.payload = payload
            execution.status = status
            execution.updated_at = now
            task.is_running = False
            task_payload = dict(task.payload)
            task_payload["total_executions"] = int(task_payload.get("total_executions", 0)) + 1
            if status == "success":
                task_payload["success_executions"] = int(task_payload.get("success_executions", 0)) + 1
            elif status == "failed":
                task_payload["failed_executions"] = int(task_payload.get("failed_executions", 0)) + 1
            task_payload.update(
                last_execution_time=self._iso(now),
                last_execution_status=status,
                last_execution_error=error,
            )
            task.payload = task_payload
            task.updated_at = now
            database.commit()
            return copy.deepcopy(payload)

    def execution_by_occurrence(self, occurrence_key: str) -> dict[str, Any] | None:
        with self._sessions() as database:
            row = database.scalar(
                select(ScheduledTaskExecutionRow)
                .where(ScheduledTaskExecutionRow.occurrence_key == occurrence_key)
                .order_by(ScheduledTaskExecutionRow.created_at.desc())
            )
            return copy.deepcopy(row.payload) if row else None

    def due(self, now: datetime) -> builtins.list[dict[str, Any]]:
        with self._sessions() as database:
            rows = database.scalars(
                select(ScheduledTaskRow)
                .where(
                    ScheduledTaskRow.enabled.is_(True),
                    ScheduledTaskRow.is_running.is_(False),
                    ScheduledTaskRow.next_execution_time.is_not(None),
                    ScheduledTaskRow.next_execution_time <= now,
                )
                .order_by(ScheduledTaskRow.next_execution_time, ScheduledTaskRow.id)
            ).all()
            return [self._payload(row) for row in rows]

    def set_next_execution(
        self,
        task_id: str,
        value: datetime | None,
        now: datetime,
        *,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        with self._sessions() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            row = database.get(ScheduledTaskRow, task_id)
            if row is None:
                raise WorkflowError("SCHEDULED_TASK_NOT_FOUND", "计划任务不存在", 404)
            row.next_execution_time = value
            if enabled is not None:
                row.enabled = enabled
                payload = dict(row.payload)
                payload["enabled"] = enabled
                row.payload = payload
            row.updated_at = now
            database.commit()
            return self._payload(row)

    def references(self, resource_type: str, resource_id: str) -> builtins.list[dict[str, Any]]:
        key = "profile_id" if resource_type == "profile" else "workflow_id" if resource_type == "workflow" else None
        if key is None:
            return []
        return [
            {
                "kind": "scheduledTask",
                "taskId": task["id"],
                "taskName": task["name"],
                "path": [key],
            }
            for task in self.list()
            if task.get(key) == resource_id
        ]

    def ensure_workflow_unreferenced(self, workflow_id: str) -> None:
        references = self.references("workflow", workflow_id)
        if references:
            raise WorkflowError(
                "SCHEDULED_RESOURCE_REFERENCED",
                "工作流仍被计划任务使用，不能删除",
                409,
                details={"references": references},
            )

    def list_logs(self, task_id: str | None, limit: int) -> builtins.list[dict[str, Any]]:
        with self._sessions() as database:
            query = select(ScheduledTaskExecutionRow).order_by(ScheduledTaskExecutionRow.created_at.desc()).limit(limit)
            if task_id is not None:
                query = query.where(ScheduledTaskExecutionRow.task_id == task_id)
            return [copy.deepcopy(row.payload) for row in database.scalars(query).all()]

    def clear_logs(self, task_id: str | None) -> None:
        with self._sessions() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            rows = database.scalars(select(ScheduledTaskExecutionRow)).all()
            for row in rows:
                if task_id is None or row.task_id == task_id:
                    if row.status in {"queued", "running"}:
                        raise WorkflowError("SCHEDULED_TASK_RUNNING", "执行中的计划任务日志不能清除", 409)
                    database.delete(row)
            database.commit()

    def recover_interrupted(self, now: datetime) -> int:
        recovered = 0
        with self._sessions() as database:
            database.execute(text("BEGIN IMMEDIATE"))
            for execution in database.scalars(select(ScheduledTaskExecutionRow)).all():
                if execution.status != "running":
                    continue
                task = database.get(ScheduledTaskRow, execution.task_id)
                if task is not None:
                    task.is_running = False
                    task.updated_at = now
                    task_payload = dict(task.payload)
                    task_payload["last_execution_time"] = self._iso(now)
                    task_payload["last_execution_status"] = "failed"
                    task_payload["last_execution_error"] = "服务重启，原执行结果不明确"
                    task_payload["total_executions"] = int(task_payload.get("total_executions", 0)) + 1
                    task_payload["failed_executions"] = int(task_payload.get("failed_executions", 0)) + 1
                    task.payload = task_payload
                    recovered += 1
                payload = dict(execution.payload)
                payload.update(
                    status="failed",
                    error="服务重启，原执行结果不明确",
                    end_time=self._iso(now),
                    duration=max(
                        0.0,
                        (
                            now
                            - self._aware(
                                execution.started_at or execution.created_at
                            )
                        ).total_seconds(),
                    ),
                )
                execution.payload = payload
                execution.status = "failed"
                execution.updated_at = now
            database.commit()
        return recovered

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    @classmethod
    def _iso(cls, value: datetime) -> str:
        return cls._aware(value).isoformat()

    @staticmethod
    def _payload(row: ScheduledTaskRow) -> dict[str, Any]:
        return {
            **copy.deepcopy(row.payload),
            "id": row.id,
            "revision": row.revision,
            "enabled": row.enabled,
            "is_running": row.is_running,
            "next_execution_time": SqlAlchemyWorkflowSchedules._iso(row.next_execution_time) if row.next_execution_time else None,
            "created_at": SqlAlchemyWorkflowSchedules._iso(row.created_at),
            "updated_at": SqlAlchemyWorkflowSchedules._iso(row.updated_at),
        }
