from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.application.project_runs.coordinator import ProjectRunCoordinator
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.domain.project_runs.models import ProjectRunError, batch_to_dict
from autoflow.domain.projects.models import ProjectOperation
from autoflow.domain.workflows.runtime import TERMINAL_STATUSES, WorkflowRuntimeError
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_run_models import ProjectBatchRow
from autoflow.infrastructure.database.project_runs import SqlAlchemyProjectRuns
from autoflow.infrastructure.database.projects import (
    _json_dates,
    _operation,
    _operation_row,
)

BATCH_TERMINAL = frozenset({"completed", "stopped", "failed", "interrupted"})
_LOG = logging.getLogger(__name__)


class ProjectBatchScheduler:
    """Advance persisted parameter batches through the existing single-capacity core."""

    def __init__(
        self,
        factory: sessionmaker[Session],
        core: WorkflowRunDispatcher,
        gate: QuiesceGate,
    ):
        self._factory, self._core, self._gate = factory, core, gate
        # One sidecar owns this database; serialize dispatch selection and stop admission.
        self._lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._loop: asyncio.Task[None] | None = None
        self._closed = False

    async def startup(self) -> None:
        if self._loop is None:
            self._closed = False
            self._loop = asyncio.create_task(self._run())

    def wake(self) -> None:
        self._wake.set()

    async def shutdown(self) -> None:
        self._closed = True
        self.wake()
        if self._loop is not None:
            await self._loop
            self._loop = None

    def blockers(self) -> list[str]:
        return ["project_batches_active"] if self._batch_ids() else []

    def force_stop_availability(
        self, project_id: str, batch_id: str
    ) -> tuple[bool, datetime | None]:
        """Project the core's real force-stop gate without accepting a command."""
        with self._factory() as session:
            repository = SqlAlchemyProjectRuns(session)
            batch = repository.batch(project_id, batch_id)
            if batch.status not in {"stopping", "reconciling"}:
                return False, None
            tasks = repository.list_tasks(project_id, batch_id)
        states = [
            self._core.force_stop_state(task.run_id)
            for task in tasks
            if self._core.query_run(task.run_id).status
            not in TERMINAL_STATUSES | {"queued"}
        ]
        if not states:
            return False, None
        if any(value is None for _allowed, value in states):
            return False, None
        available_at = max(value for _allowed, value in states if value is not None)
        return all(allowed for allowed, _value in states), available_at

    def _batch_ids(self) -> list[tuple[str, str]]:
        with self._factory() as session:
            return list(
                session.execute(
                    select(ProjectBatchRow.project_id, ProjectBatchRow.id)
                    .where(ProjectBatchRow.status.not_in(BATCH_TERMINAL))
                    .order_by(ProjectBatchRow.created_at, ProjectBatchRow.id)
                ).tuples()
            )

    async def _run(self) -> None:
        while not self._closed:
            self._wake.clear()
            try:
                await self.tick()
            except Exception:  # noqa: BLE001 - background recovery retains durable facts
                # Keep accepted facts for the next query/recovery; never invent a terminal result.
                _LOG.exception("Project batch progress could not be committed")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=0.5)
            except TimeoutError:
                pass

    async def tick(self) -> None:
        async with self._lock:
            if self._closed:
                return
            for project_id, batch_id in self._batch_ids():
                with self._gate.mutation() as admitted:
                    if not admitted:
                        return
                    await self._advance(project_id, batch_id)

    async def _advance(self, project_id: str, batch_id: str) -> None:
        with self._factory() as session:
            repository = SqlAlchemyProjectRuns(session)
            batch = repository.batch(project_id, batch_id)
            tasks = repository.list_tasks(project_id, batch_id)
            project = ProjectRunCoordinator._project(session, project_id)
            project_active = project.lifecycle_state == "active"
            force_requested = (
                session.scalar(
                    select(ProjectOperationRow.id).where(
                        ProjectOperationRow.project_id == project_id,
                        ProjectOperationRow.kind == "forceStopBatch",
                        ProjectOperationRow.status == "running",
                        ProjectOperationRow.resource["batchId"].as_string() == batch_id,
                    )
                )
                is not None
            )
        if batch.status in BATCH_TERMINAL:
            return
        failed = any(
            task.status in {"failed", "timed_out", "interrupted"} for task in tasks
        )
        continue_after_failure = batch.frozen_request["automation"]["runPolicy"][
            "continueAfterFailure"
        ]
        stopping = batch.status == "stopping" or not project_active
        if stopping or (failed and not continue_after_failure):
            self._set_status(
                project_id, batch_id, "stopping" if stopping else "draining"
            )
            for task in tasks:
                current = self._core.query_run(task.run_id)
                if force_requested and current.status not in TERMINAL_STATUSES | {
                    "queued"
                }:
                    await self._core.force_stop(
                        current.run_id,
                        expected_status_revision=current.status_revision,
                        execution_generation=current.execution_generation,
                    )
                    continue
                if current.status == "queued" or (
                    stopping
                    and current.status
                    not in TERMINAL_STATUSES | {"stopping", "reconciling"}
                ):
                    await self._core.cancel(
                        current.run_id,
                        expected_status_revision=current.status_revision,
                        execution_generation=current.execution_generation,
                    )
            with self._factory() as session:
                tasks = SqlAlchemyProjectRuns(session).list_tasks(project_id, batch_id)
        active = [task for task in tasks if task.status not in TERMINAL_STATUSES]
        if not active:
            result = (
                "stopped"
                if stopping
                else "interrupted"
                if any(task.status == "interrupted" for task in tasks)
                else "failed"
                if any(task.status != "succeeded" for task in tasks)
                else "completed"
            )
            self._set_status(project_id, batch_id, result)
            return
        if stopping or (failed and not continue_after_failure):
            return
        if any(task.status == "reconciling" for task in active):
            self._set_status(project_id, batch_id, "reconciling")
            return
        if any(task.status != "queued" for task in active):
            return
        current = self._core.query_run(active[0].run_id)
        try:
            await self._core.dispatch(
                current.run_id,
                expected_status_revision=current.status_revision,
                execution_generation=current.execution_generation,
            )
        except WorkflowRuntimeError as error:
            if error.code in {"WORKFLOW_CAPACITY_FULL", "WORKFLOW_ADMISSION_CLOSED"}:
                self._set_status(project_id, batch_id, "blocked")
                return
            if error.code in {
                "RUN_STATUS_CONFLICT",
                "RUN_NOT_DISPATCHABLE",
                "EXECUTION_GENERATION_REVOKED",
            }:
                return  # Another authoritative core transition won; query on the next tick.
            raise
        self._set_status(project_id, batch_id, "running")

    def _set_status(self, project_id: str, batch_id: str, target: str) -> None:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            repository = SqlAlchemyProjectRuns(session)
            row = repository.batch_row(project_id, batch_id)
            if row.status in BATCH_TERMINAL:
                return
            if row.status != target:
                row.status, row.status_revision = target, row.status_revision + 1
            if target in BATCH_TERMINAL:
                row.completed_at = datetime.now(UTC)
                session.flush()
                result = {
                    "batch": _json_dates(
                        batch_to_dict(repository.batch(project_id, batch_id))
                    )
                }
                for operation in session.scalars(
                    select(ProjectOperationRow).where(
                        ProjectOperationRow.project_id == project_id,
                        ProjectOperationRow.kind.in_(["stopBatch", "forceStopBatch"]),
                        ProjectOperationRow.status == "running",
                    )
                ):
                    if operation.resource.get("batchId") == batch_id:
                        operation.status = "succeeded"
                        operation.status_revision += 1
                        operation.result = result
                        operation.updated_at = operation.completed_at = row.completed_at
            self._commit(session)

    async def stop(
        self,
        project_id: str,
        batch_id: str,
        key: str,
        payload: dict[str, Any],
        *,
        force: bool = False,
    ) -> ProjectOperation:
        async with self._lock:
            operation = self._accept_stop(
                project_id, batch_id, key, payload, force=force
            )
            self.wake()
            return operation

    def _accept_stop(
        self,
        project_id: str,
        batch_id: str,
        key: str,
        payload: dict[str, Any],
        *,
        force: bool = False,
    ) -> ProjectOperation:
        kind = "forceStopBatch" if force else "stopBatch"
        try:
            if str(UUID(key)) != key or set(payload) != {
                "expectedStatusRevision",
                "reason",
            }:
                raise ValueError
            if (
                type(payload["expectedStatusRevision"]) is not int
                or payload["expectedStatusRevision"] < 1
                or not isinstance(payload["reason"], str)
                or not payload["reason"].strip()
                or len(payload["reason"]) > 500
            ):
                raise ValueError
            digest = hashlib.sha256(
                json.dumps(
                    {
                        "projectId": project_id,
                        "batchId": batch_id,
                        "kind": kind,
                        "request": payload,
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                    allow_nan=False,
                ).encode()
            ).hexdigest()
        except (ValueError, TypeError, KeyError) as error:
            raise ProjectRunError("VALIDATION_ERROR", "停止请求无效", 422) from error
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            ProjectRunCoordinator._project(session, project_id)
            repository = SqlAlchemyProjectRuns(session)
            row = repository.batch_row(project_id, batch_id)
            existing = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == key
                )
            )
            if existing is not None:
                if (
                    existing.project_id != project_id
                    or existing.kind != kind
                    or existing.request_digest != digest
                ):
                    raise ProjectRunError(
                        "OPERATION_PAYLOAD_MISMATCH", "同一操作身份已用于其他请求", 409
                    )
                return _operation(existing)
            terminal = row.status in BATCH_TERMINAL
            if not terminal and row.status_revision != payload["expectedStatusRevision"]:
                raise ProjectRunError(
                    "REVISION_CONFLICT",
                    "批次状态已更新，请刷新后重试",
                    409,
                    {"currentStatusRevision": row.status_revision},
                )
            now = datetime.now(UTC)
            if force and not terminal:
                if row.status not in {"stopping", "reconciling"}:
                    raise ProjectRunError(
                        "STOP_REQUIRED", "请先停止批次，再核验或强制停止", 409
                    )
                for task in repository.list_tasks(project_id, batch_id):
                    run = self._core.query_run(task.run_id)
                    if run.status not in TERMINAL_STATUSES | {"queued"}:
                        self._core.validate_force_stop(
                            run.run_id, run.status_revision, run.execution_generation
                        )
            if not terminal and row.status != "stopping":
                row.status, row.status_revision = "stopping", row.status_revision + 1
            session.flush()
            operation = ProjectOperation(
                str(uuid4()),
                project_id,
                key,
                kind,
                digest,
                "succeeded" if terminal else "running",
                1,
                {"type": "batch", "projectId": project_id, "batchId": batch_id},
                {
                    "batch": _json_dates(
                        batch_to_dict(repository.batch(project_id, batch_id))
                    )
                }
                if terminal
                else None,
                None,
                now,
                now,
                now if terminal else None,
            )
            session.add(_operation_row(operation))
            self._commit(session)
            return operation

    @staticmethod
    def _commit(session: Session) -> None:
        try:
            session.commit()
        except Exception:
            session.invalidate()
            raise
