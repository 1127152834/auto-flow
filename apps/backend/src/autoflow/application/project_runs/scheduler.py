from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.application.project_runs.coordinator import ProjectRunCoordinator
from autoflow.application.project_runs.resources import ProjectRunResourceResolver
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.domain.project_runs.input_selection import MAX_CANDIDATE_EVALUATIONS
from autoflow.domain.project_runs.models import ProjectRunError, batch_to_dict
from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.domain.workflows.runtime import (
    TERMINAL_STATUSES,
    WorkflowRuntimeError,
    thaw_json,
)
from autoflow.infrastructure.database.environment_models import (
    ProjectEnvironmentInstanceRow,
)
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_claims import (
    SqlAlchemyProjectInputGroups,
    _parse_record_ref,
)
from autoflow.infrastructure.database.project_data_models import DataTableRow
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectRecordLeaseRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.project_runs import SqlAlchemyProjectRuns
from autoflow.infrastructure.database.projects import (
    _json_dates,
    _operation,
    _operation_row,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow

BATCH_TERMINAL = frozenset({"completed", "stopped", "failed", "interrupted"})
_LOG = logging.getLogger(__name__)


def _follow_up_candidate_restriction(follow_up: Any) -> dict[str, Any]:
    """Pinned candidate map of a follow-up Batch, or {} for a normal Batch."""
    if not isinstance(follow_up, dict):
        return {}
    raw = follow_up.get("candidateRestriction")
    if not isinstance(raw, dict):
        return {}
    restriction = {
        input_id: refs
        for input_id, refs in raw.items()
        if isinstance(input_id, str) and isinstance(refs, list)
    }
    return {"candidateRestriction": restriction} if restriction else {}


def _next_candidate_offsets(
    input_plan: dict[str, Any],
    current: dict[str, int],
    continuation_input_ids: tuple[str, ...],
) -> dict[str, int] | None:
    """Advance one physical candidate page at a time without skipping page pairs."""
    continuations = set(continuation_input_ids)
    ordered: list[str] = []
    for item in input_plan.get("inputs", []):
        if isinstance(item, dict) and isinstance(item.get("inputId"), str):
            ordered.append(item["inputId"])
    for index, input_id in enumerate(ordered):
        if input_id not in continuations:
            continue
        result = dict(current)
        result[input_id] = result.get(input_id, 0) + MAX_CANDIDATE_EVALUATIONS
        for earlier in ordered[:index]:
            result[earlier] = 0
        return result
    return None


class ProjectBatchScheduler:
    """Advance persisted parameter batches through the existing single-capacity core."""

    def __init__(
        self,
        factory: sessionmaker[Session],
        core: WorkflowRunDispatcher,
        gate: QuiesceGate,
        environments: Any | None = None,
        resource_resolver: ProjectRunResourceResolver | None = None,
    ):
        self._factory, self._core, self._gate = factory, core, gate
        self._environments = environments
        self._resource_resolver = resource_resolver
        # One sidecar owns this database; serialize dispatch selection and stop admission.
        self._lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._loop: asyncio.Task[None] | None = None
        self._closed = False
        self._unsubscribe_core: Any = None

    async def startup(self) -> None:
        if self._loop is None:
            self._closed = False
            subscribe = getattr(self._core, "subscribe_idle", None)
            if callable(subscribe):
                self._unsubscribe_core = subscribe(self.wake)
            self._loop = asyncio.create_task(self._run())

    def wake(self) -> None:
        self._wake.set()

    async def shutdown(self) -> None:
        self._closed = True
        self.wake()
        if self._loop is not None:
            await self._loop
            self._loop = None
        if self._unsubscribe_core is not None:
            self._unsubscribe_core()
            self._unsubscribe_core = None

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
                await asyncio.wait_for(self._wake.wait(), timeout=30)
            except TimeoutError:
                pass

    async def tick(self) -> None:
        if self._closed:
            return
        if self._environments is not None:
            with self._factory() as session:
                active = session.scalar(select(WorkflowRunRow.id).where(
                    WorkflowRunRow.status.not_in(TERMINAL_STATUSES | {"queued"}),
                ).limit(1))
            # Cleanup can wait for a browser/filesystem. Do not delay another
            # active run's cancellation or hold the stop-admission lock.
            if active is None:
                with self._gate.mutation() as admitted:
                    if not admitted:
                        return
                    await asyncio.to_thread(self._environments.cleanup_terminal_tasks)
        async with self._lock:
            if self._closed:
                return
            for project_id, batch_id in self._batch_ids():
                with self._gate.mutation() as admitted:
                    if not admitted:
                        return
                    await self._advance(project_id, batch_id)

    async def _advance(self, project_id: str, batch_id: str) -> None:
        await self._cleanup_terminal_instances(project_id, batch_id)
        self._release_terminal_leases(project_id, batch_id)
        with self._factory() as session:
            repository = SqlAlchemyProjectRuns(session)
            batch = repository.batch(project_id, batch_id)
            tasks = repository.list_tasks(project_id, batch_id)
            project = ProjectRunCoordinator._project(session, project_id)
            project_active = project.lifecycle_state == "active"
            stop_kinds = set(
                session.scalars(
                    select(ProjectOperationRow.kind).where(
                        ProjectOperationRow.project_id == project_id,
                        ProjectOperationRow.kind.in_(["stopBatch", "forceStopBatch"]),
                        ProjectOperationRow.status == "running",
                        ProjectOperationRow.resource["batchId"].as_string() == batch_id,
                    )
                )
            )
            stop_requested = bool(stop_kinds)
            force_requested = "forceStopBatch" in stop_kinds
        if (
            batch.frozen_request.get("automation", {})
            .get("inputPlan", {})
            .get("inputs")
        ):
            await self._advance_data(
                project_id,
                batch_id,
                batch,
                tasks,
                project_active=project_active,
                stop_requested=stop_requested,
                force_requested=force_requested,
            )
            return
        if batch.status in BATCH_TERMINAL:
            return
        failed = any(
            task.status in {"failed", "timed_out", "interrupted"} for task in tasks
        )
        continue_after_failure = batch.frozen_request["automation"]["runPolicy"][
            "continueAfterFailure"
        ]
        stopping = batch.status == "stopping" or stop_requested or not project_active
        if stopping or (failed and not continue_after_failure):
            self._set_status(
                project_id,
                batch_id,
                "reconciling"
                if any(task.status == "reconciling" for task in tasks)
                else "stopping" if stopping else "draining",
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
            await self._cleanup_terminal_instances(project_id, batch_id)
            self._release_terminal_leases(project_id, batch_id)
            self._set_status(project_id, batch_id, result)
            return
        if any(task.status == "reconciling" for task in active):
            self._set_status(project_id, batch_id, "reconciling")
            return
        if stopping or (failed and not continue_after_failure):
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

    async def _advance_data(
        self,
        project_id: str,
        batch_id: str,
        batch: Any,
        tasks: list[Any],
        *,
        project_active: bool,
        stop_requested: bool,
        force_requested: bool,
    ) -> None:
        failed = any(
            task.status in {"failed", "timed_out", "interrupted"} for task in tasks
        )
        continue_after_failure = bool(
            batch.frozen_request["automation"]["runPolicy"]["continueAfterFailure"]
        )
        stopping = batch.status == "stopping" or stop_requested or not project_active
        if stopping or (failed and not continue_after_failure):
            self._close_claim_gate(project_id, batch_id)
            self._set_status(
                project_id,
                batch_id,
                "reconciling"
                if any(task.status == "reconciling" for task in tasks)
                else "stopping" if stopping else "draining",
            )
            if stopping:
                await self._stop_active_runs(
                    project_id,
                    batch_id,
                    tasks,
                    stopping=True,
                    force_requested=force_requested,
                )
            with self._factory() as session:
                tasks = SqlAlchemyProjectRuns(session).list_tasks(project_id, batch_id)

        active = [task for task in tasks if task.status not in TERMINAL_STATUSES]
        if not stopping and not (failed and not continue_after_failure):
            target = batch.frozen_request.get("maxTasks")
            requested_concurrency = int(batch.frozen_request.get("concurrency") or 1)
            configured_concurrency = int(
                batch.frozen_request["automation"]["runPolicy"].get(
                    "concurrency", 1
                )
            )
            configured_capacity = int(
                batch.frozen_request["automation"]["runPolicy"].get(
                    "maxLiveInstances", 1
                )
            )
            with self._factory() as session:
                global_active = session.scalar(
                    select(func.count())
                    .select_from(WorkflowRunRow)
                    .where(WorkflowRunRow.status.not_in(TERMINAL_STATUSES))
                ) or 0
                automation_active = session.scalar(
                    select(func.count())
                    .select_from(ProjectTaskRow)
                    .join(
                        ProjectBatchRow,
                        ProjectBatchRow.id == ProjectTaskRow.batch_id,
                    )
                    .join(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
                    .where(
                        ProjectBatchRow.automation_id == batch.automation_id,
                        WorkflowRunRow.status.not_in(TERMINAL_STATUSES),
                    )
                ) or 0
            core_capacity = max(1, int(getattr(self._core, "capacity", 1)))
            slots = max(
                0,
                min(
                    requested_concurrency - len(active),
                    configured_concurrency - len(active),
                    configured_capacity - automation_active,
                    core_capacity - global_active,
                ),
            )
            if slots == 0 and not active:
                self._set_status(project_id, batch_id, "blocked")
                return
            claim_outcome = "idle"
            for _ in range(slots):
                if target is not None and len(tasks) >= int(target):
                    self._close_claim_gate(
                        project_id, batch_id, selection_status="limitReached"
                    )
                    claim_outcome = "limitReached"
                    break
                claim_outcome = self._claim_data_task(project_id, batch_id)
                if claim_outcome != "ready":
                    break
                with self._factory() as session:
                    tasks = SqlAlchemyProjectRuns(session).list_tasks(
                        project_id, batch_id
                    )
                active = [
                    task for task in tasks if task.status not in TERMINAL_STATUSES
                ]
            if claim_outcome == "temporarilyBusy" and not active:
                self._set_status(project_id, batch_id, "blocked")
                return
            if claim_outcome == "capacityFull" and not active:
                self._set_status(project_id, batch_id, "blocked")
                return
            if claim_outcome == "staleSelection":
                self.wake()
                return
            if claim_outcome in {"configurationError", "ambiguous"}:
                self._set_status(project_id, batch_id, "draining")
            if claim_outcome == "scanBudgetExceeded":
                self._set_status(project_id, batch_id, "blocked")
                with self._factory() as session:
                    outcome = (
                        SqlAlchemyProjectRuns(session)
                        .batch_row(project_id, batch_id)
                        .selection_outcome
                        or {}
                    )
                if outcome.get("hasContinuation") is True:
                    self.wake()
                return

        active = [task for task in tasks if task.status not in TERMINAL_STATUSES]
        with self._factory() as session:
            stored = SqlAlchemyProjectRuns(session).batch_row(project_id, batch_id)
            gate_open = stored.claim_gate_state == "open"
            selection_status = (stored.selection_outcome or {}).get("status")
        if not active:
            if gate_open:
                return
            result = (
                "stopped"
                if stopping
                else "interrupted"
                if any(task.status == "interrupted" for task in tasks)
                else "failed"
                if any(task.status != "succeeded" for task in tasks)
                or selection_status in {"configurationError", "ambiguous"}
                else "completed"
            )
            if not tasks and selection_status == "noMatch":
                result = "completed"
            await self._cleanup_terminal_instances(project_id, batch_id)
            self._release_terminal_leases(project_id, batch_id)
            self._set_status(project_id, batch_id, result)
            return
        if any(task.status == "reconciling" for task in active):
            self._set_status(project_id, batch_id, "reconciling")
            return
        if stopping:
            return
        queued = [task for task in active if task.status == "queued"]
        if not queued:
            self._set_status(
                project_id,
                batch_id,
                "draining"
                if (failed and not continue_after_failure)
                or selection_status in {"configurationError", "ambiguous"}
                else "running",
            )
            return
        dispatched = False
        for task in queued:
            current = self._core.query_run(task.run_id)
            try:
                await self._core.dispatch(
                    current.run_id,
                    expected_status_revision=current.status_revision,
                    execution_generation=current.execution_generation,
                )
                dispatched = True
            except WorkflowRuntimeError as error:
                if error.code in {
                    "WORKFLOW_CAPACITY_FULL",
                    "WORKFLOW_ADMISSION_CLOSED",
                }:
                    if not dispatched:
                        self._set_status(project_id, batch_id, "blocked")
                    return
                if error.code in {
                    "RUN_STATUS_CONFLICT",
                    "RUN_NOT_DISPATCHABLE",
                    "EXECUTION_GENERATION_REVOKED",
                }:
                    continue
                raise
        self._set_status(
            project_id,
            batch_id,
            "draining"
            if (failed and not continue_after_failure)
            or selection_status in {"configurationError", "ambiguous"}
            else "running",
        )

    async def _stop_active_runs(
        self,
        project_id: str,
        batch_id: str,
        tasks: list[Any],
        *,
        stopping: bool,
        force_requested: bool,
    ) -> None:
        for task in tasks:
            current = self._core.query_run(task.run_id)
            if force_requested and current.status not in TERMINAL_STATUSES | {"queued"}:
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

    @staticmethod
    def claim_data_task(
        factory: sessionmaker[Session],
        project_id: str,
        batch_id: str,
        *,
        core_capacity: int = 1,
        environments: Any | None = None,
        resource_resolver: ProjectRunResourceResolver | None = None,
    ) -> str:
        """Prepare outside the write lock, then atomically commit one data Task."""
        prepared = ProjectBatchScheduler._prepare_data_claim(
            factory, project_id, batch_id
        )
        if isinstance(prepared, str):
            return prepared
        with factory() as session:
            groups = SqlAlchemyProjectInputGroups(session)
            pinned: dict[str, list[Any]] = {}
            for input_id, refs in (prepared.get("candidateRestriction") or {}).items():
                if not isinstance(refs, list):
                    continue
                parsed: list[Any] = []
                for raw in refs:
                    try:
                        parsed.append(_parse_record_ref(raw))
                    except (KeyError, TypeError, ValueError):
                        continue
                pinned[input_id] = parsed
            selection = groups.select_required(
                project_id,
                prepared["inputPlan"],
                candidate_offsets=prepared["candidateOffsets"],
                **({"candidate_restriction": pinned} if pinned else {}),
            )
        result = ProjectBatchScheduler._commit_data_claim(
            factory,
            project_id,
            batch_id,
            prepared,
            selection,
            core_capacity=core_capacity,
            environments=environments,
            resource_resolver=resource_resolver,
        )
        return result

    def _claim_data_task(self, project_id: str, batch_id: str) -> str:
        result = self.claim_data_task(
            self._factory,
            project_id,
            batch_id,
            core_capacity=max(1, int(getattr(self._core, "capacity", 1))),
            environments=self._environments,
            resource_resolver=self._resource_resolver,
        )
        if result == "ready" and self._environments is not None:
            self._attach_claimed_environment(project_id, batch_id)
        return result

    def _attach_claimed_environment(self, project_id: str, batch_id: str) -> None:
        if self._environments is None:
            return
        with self._factory() as session:
            repository = SqlAlchemyProjectRuns(session)
            batch = repository.batch_row(project_id, batch_id)
            tasks = repository.list_tasks(project_id, batch_id)
            if not tasks:
                return
            task = max(tasks, key=lambda item: item.created_at)
            snapshots = session.scalars(
                select(ProjectTaskInputSnapshotRow).where(
                    ProjectTaskInputSnapshotRow.task_id == task.task_id
                )
            ).all()
            inputs = {}
            for row in snapshots:
                for item in row.inputs or []:
                    if isinstance(item, dict) and item.get("inputId"):
                        inputs[item["inputId"]] = item
            frozen = batch.frozen_request or {}
            if frozen.get("resourceRequest", {}).get("browser") in {"none", "node"}:
                return
            policy = frozen.get("resourceRequest", {}).get("environmentPolicy") or frozen.get("environmentOverride") or frozen.get("automation", {}).get(
                "environmentPolicy"
            )
        if not policy:
            return
        self._environments.attach_task_instance(
            project_id, task.task_id, task.run_id, policy, inputs
        )

    @staticmethod
    def _prepare_data_claim(
        factory: sessionmaker[Session], project_id: str, batch_id: str
    ) -> dict[str, Any] | str:
        with factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            repository = SqlAlchemyProjectRuns(session)
            row = repository.batch_row(project_id, batch_id)
            project = session.get(ProjectRow, project_id)
            if project is None or project.lifecycle_state != "active":
                row.claim_gate_state = "closed"
                ProjectBatchScheduler._commit(session)
                return "closed"
            if row.claim_gate_state != "open" or row.status in BATCH_TERMINAL:
                session.rollback()
                return "closed"
            tasks = repository.list_tasks(project_id, batch_id)
            if (
                not row.frozen_request["automation"]["runPolicy"].get(
                    "continueAfterFailure", False
                )
                and any(
                    task.status in {"failed", "timed_out", "interrupted"}
                    for task in tasks
                )
            ):
                row.claim_gate_state = "closed"
                ProjectBatchScheduler._commit(session)
                return "closed"
            target = row.frozen_request.get("maxTasks")
            if target is not None and len(tasks) >= int(target):
                row.claim_gate_state = "closed"
                row.selection_outcome = {"status": "limitReached"}
                ProjectBatchScheduler._commit(session)
                return "limitReached"
            automation = row.frozen_request["automation"]
            input_plan = automation["inputPlan"]
            previous_outcome = row.selection_outcome or {}
            offsets = previous_outcome.get("candidateOffsets", {})
            if not isinstance(offsets, dict):
                offsets = {}
            valid_offsets = {
                key: value
                for key, value in offsets.items()
                if isinstance(key, str) and type(value) is int and value >= 0
            }
            now = datetime.now(UTC)
            follow_up = row.frozen_request.get("followUp")
            restriction = _follow_up_candidate_restriction(follow_up)
            if 'debugSelection' in row.frozen_request:
                restriction = {'candidateRestriction': {key: [value['recordRef']] if value is not None else [] for key, value in row.frozen_request['debugSelection'].items()}}
            attempt = previous_outcome.get("claimAttempt")
            if not isinstance(attempt, dict) or attempt.get("state") != "prepared":
                attempt = {
                    "prepareOperationId": str(uuid4()),
                    "taskId": str(uuid4()),
                    "runRequestId": str(uuid4()),
                    "inputSnapshotId": str(uuid4()),
                    "taskOrdinal": len(tasks),
                    "state": "prepared",
                    "preparedAt": now.isoformat(),
                }
            row.selection_outcome = {
                "status": "preparing",
                "candidateOffsets": valid_offsets,
                "sawBusy": previous_outcome.get("sawBusy") is True,
                "claimAttempt": attempt,
                "selectionGuards": _selection_guards(session, project_id, input_plan),
            }
            ProjectBatchScheduler._commit(session)
            return {
                **attempt,
                "inputPlan": input_plan,
                "candidateOffsets": valid_offsets,
                "parameters": row.frozen_request["parameters"],
                "resourceRequest": row.frozen_request["resourceRequest"],
                "preparedContentId": row.prepared_content_id,
                "selectionGuards": row.selection_outcome["selectionGuards"],
                "dataCapabilityBinding": row.frozen_request.get(
                    "dataCapabilityBinding"
                ),
                **restriction,
            }

    @staticmethod
    def _commit_data_claim(
        factory: sessionmaker[Session],
        project_id: str,
        batch_id: str,
        prepared: dict[str, Any],
        selection: Any,
        *,
        core_capacity: int = 1,
        environments: Any | None = None,
        resource_resolver: ProjectRunResourceResolver | None = None,
    ) -> str:
        with factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            repository = SqlAlchemyProjectRuns(session)
            row = repository.batch_row(project_id, batch_id)
            current_outcome = row.selection_outcome or {}
            current_attempt = current_outcome.get("claimAttempt")
            if (
                not isinstance(current_attempt, dict)
                or current_attempt.get("prepareOperationId")
                != prepared["prepareOperationId"]
            ):
                session.rollback()
                return "closed"
            project = session.get(ProjectRow, project_id)
            tasks = repository.list_tasks(project_id, batch_id)
            target = row.frozen_request.get("maxTasks")
            if (
                project is None
                or project.lifecycle_state != "active"
                or row.claim_gate_state != "open"
                or row.status in BATCH_TERMINAL
                or (
                    target is not None
                    and len(tasks) >= int(target)
                )
                or (
                    not row.frozen_request["automation"]["runPolicy"].get(
                        "continueAfterFailure", False
                    )
                    and any(
                        task.status in {"failed", "timed_out", "interrupted"}
                        for task in tasks
                    )
                )
            ):
                row.claim_gate_state = "closed"
                row.selection_outcome = {"status": "closed"}
                ProjectBatchScheduler._commit(session)
                return "closed"
            if 'debugSelection' in row.frozen_request:
                from .debug_inputs import validate_debug_selection
                try:
                    selection = validate_debug_selection(session, project_id, prepared['inputPlan'], row.frozen_request['debugSelection'])
                except ProjectRunError as exc:
                    row.claim_gate_state = 'closed'
                    row.selection_outcome = {'status': 'configurationError', 'code': exc.code, 'message': str(exc)}
                    ProjectBatchScheduler._commit(session)
                    return 'configurationError'
            if _selection_guards(
                session,
                project_id,
                prepared["inputPlan"],
            ) != prepared.get("selectionGuards"):
                row.selection_outcome = {
                    "status": "staleSelection",
                    "candidateOffsets": {},
                    "sawBusy": False,
                    "claimAttempt": current_attempt,
                }
                ProjectBatchScheduler._commit(session)
                return "staleSelection"
            if selection.status == "ready" and not _claim_capacity_available(
                session,
                row,
                batch_id,
                core_capacity,
            ):
                row.selection_outcome = {
                    "status": "capacityFull",
                    "candidateOffsets": prepared["candidateOffsets"],
                    "sawBusy": current_outcome.get("sawBusy") is True,
                    "claimAttempt": current_attempt,
                    "selectionGuards": prepared["selectionGuards"],
                }
                ProjectBatchScheduler._commit(session)
                return "capacityFull"
            if selection.status == "ready":
                selection = SqlAlchemyProjectInputGroups(session).revalidate_selected(
                    project_id,
                    prepared["inputPlan"],
                    selection,
                )
            if selection.status == "scanBudgetExceeded":
                offsets = prepared["candidateOffsets"]
                next_offsets = _next_candidate_offsets(
                    prepared["inputPlan"],
                    offsets,
                    selection.continuation_input_ids,
                )
                has_continuation = next_offsets is not None
                row.selection_outcome = {
                    "status": selection.status,
                    "category": (
                        "candidatePage"
                        if has_continuation
                        else "candidateBindingBudget"
                    ),
                    "issueInputIds": list(selection.issue_input_ids),
                    "issueDetails": dict(selection.issue_details),
                    "candidateOffsets": next_offsets or offsets,
                    "hasContinuation": has_continuation,
                    "sawBusy": current_outcome.get("sawBusy") is True
                    or selection.continuation_status == "temporarilyBusy",
                }
                ProjectBatchScheduler._commit(session)
                return selection.status
            if (
                selection.status == "noMatch"
                and current_outcome.get("sawBusy") is True
            ):
                row.selection_outcome = {
                    "status": "temporarilyBusy",
                    "candidateOffsets": {},
                    "sawBusy": False,
                }
                ProjectBatchScheduler._commit(session)
                return "temporarilyBusy"
            row.selection_outcome = {
                "status": selection.status,
                "issueInputIds": list(selection.issue_input_ids),
                "issueDetails": dict(selection.issue_details),
            }
            if selection.status != "ready":
                active = any(task.status not in TERMINAL_STATUSES for task in tasks)
                if selection.status in {"configurationError", "ambiguous"} or (
                    selection.status == "noMatch" and not active
                ):
                    row.claim_gate_state = "closed"
                ProjectBatchScheduler._commit(session)
                return selection.status
            now = datetime.now(UTC)
            task_id = prepared["taskId"]
            request_id = prepared["runRequestId"]
            snapshot_id = prepared["inputSnapshotId"]
            binding = row.frozen_request.get("dataCapabilityBinding")
            capability_bindings = (
                [
                    {
                        **binding,
                        "taskId": task_id,
                        "executionGeneration": 1,
                    }
                ]
                if isinstance(binding, dict)
                else []
            )
            resource_request = prepared["resourceRequest"]
            policy = resource_request.get("environmentPolicy") or row.frozen_request["automation"]["environmentPolicy"]
            if resource_request.get("environmentResolution") == "atTaskStart":
                try:
                    if environments is None or resource_resolver is None:
                        raise ProjectRunError("RESOURCE_UNAVAILABLE", "环境资源解析尚未接入", 409)
                    selected_source = environments.environments.resolve_source_in_session(
                        session, project_id, policy,
                        {item.input_id: thaw_json(item.value) for item in selection.inputs},
                    )
                    resource_request = resource_resolver.freeze_input_environment(resource_request, selected_source)
                except (ProjectError, ProjectRunError, WorkflowRuntimeError) as error:
                    row.claim_gate_state = "closed"
                    row.selection_outcome = {"status": "configurationError", "issueDetails": {"environmentPolicy": error.message}, "errorCode": error.code}
                    ProjectBatchScheduler._commit(session)
                    return "configurationError"
            if resource_request.get("browser") == "node":
                from copy import deepcopy

                from autoflow.domain.environments.identity import request_from_identity
                resource_request = deepcopy(resource_request)
                try:
                    for node_id, frozen_node in resource_request['nodeBrowserEnvironments'].items():
                        if frozen_node.get('environmentResolution') != 'atTaskStart':
                            continue
                        if environments is None:
                            raise ProjectRunError('RESOURCE_UNAVAILABLE', '环境服务尚未就绪', 409)
                        selected = environments.environments.resolve_source_in_session(session, project_id, frozen_node['environmentPolicy'], {item.input_id: thaw_json(item.value) for item in selection.inputs})
                        resource_request['nodeBrowserEnvironments'][node_id] = {**request_from_identity(selected.identity_package), 'identityPackage': selected.identity_package, 'environmentRef': selected.environment_ref.to_dict(), 'environmentPolicy': frozen_node['environmentPolicy']}
                except (ProjectError, ProjectRunError, WorkflowRuntimeError) as error:
                    row.claim_gate_state = 'closed'
                    row.selection_outcome = {'status': 'configurationError', 'errorCode': error.code}
                    ProjectBatchScheduler._commit(session)
                    return 'configurationError'
            run = WorkflowRuntimeService(factory).prepare_run(
                run_request_id=request_id,
                prepared_content_id=prepared["preparedContentId"],
                parameters=prepared["parameters"],
                input_snapshot_ref={
                    "projectId": project_id,
                    "batchId": batch_id,
                    "taskId": task_id,
                    "inputSnapshotId": snapshot_id,
                },
                resource_request=resource_request,
                capability_bindings=capability_bindings,
                created_at=now,
                uow=session,
            )
            session.add(
                ProjectTaskRow(
                    id=task_id,
                    project_id=project_id,
                    batch_id=batch_id,
                    run_id=run.run_id,
                    run_request_id=run.run_request_id,
                    ordinal=prepared["taskOrdinal"],
                    created_at=now,
                )
            )
            session.flush()
            inputs = SqlAlchemyProjectInputGroups(session).hold(
                selection,
                input_plan=prepared["inputPlan"],
                project_id=project_id,
                batch_id=batch_id,
                task_id=task_id,
                run_id=run.run_id,
                now=now,
            )
            session.add(
                ProjectTaskInputSnapshotRow(
                    id=snapshot_id,
                    task_id=task_id,
                    batch_id=batch_id,
                    parameters=prepared["parameters"],
                    inputs=inputs,
                    captured_at=now,
                )
            )
            session.flush()
            if environments is not None and resource_request.get("browser") not in {"none", "node"}:
                environments.reserve_task_instance(
                    session, project_id, task_id, run.run_id, policy,
                    {item["inputId"]: item for item in inputs if item.get("inputId")},
                    resource_request=resource_request,
                )
            row.selection_outcome = {
                "status": "ready",
                "lastClaim": {
                    "prepareOperationId": prepared["prepareOperationId"],
                    "taskId": task_id,
                    "runRequestId": request_id,
                    "state": "committed",
                },
            }
            ProjectBatchScheduler._commit(session)
            return "ready"

    def _close_claim_gate(
        self,
        project_id: str,
        batch_id: str,
        *,
        selection_status: str | None = None,
    ) -> None:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = SqlAlchemyProjectRuns(session).batch_row(project_id, batch_id)
            if row.claim_gate_state != "closed":
                row.claim_gate_state = "closed"
            if selection_status is not None:
                row.selection_outcome = {"status": selection_status}
            self._commit(session)

    async def _cleanup_terminal_instances(self, project_id: str, batch_id: str) -> None:
        if self._environments is None:
            return
        with self._factory() as session:
            instances = list(session.scalars(select(ProjectEnvironmentInstanceRow)
                .join(ProjectTaskRow, ProjectTaskRow.id == ProjectEnvironmentInstanceRow.active_task_id)
                .join(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
                .where(ProjectTaskRow.project_id == project_id, ProjectTaskRow.batch_id == batch_id,
                       ProjectEnvironmentInstanceRow.project_id == project_id,
                       ProjectEnvironmentInstanceRow.active_run_id == WorkflowRunRow.id,
                       WorkflowRunRow.status.in_(TERMINAL_STATUSES),
                       ProjectEnvironmentInstanceRow.state.in_(['reserved', 'starting', 'active', 'waiting_manual', 'closing', 'closed', 'cleaning']))))
        for instance in instances:
            # Terminal Run means worker cleanup was confirmed; the environment
            # service still verifies native ownership before deleting its copy.
            await asyncio.to_thread(self._environments.close_instance, project_id, instance.id, instance.environment_id)

    def _release_terminal_leases(self, project_id: str, batch_id: str) -> None:
        with self._factory() as session:
            terminal_ids = list(
                session.scalars(
                    select(ProjectRecordLeaseRow.id)
                    .join(
                        WorkflowRunRow,
                        WorkflowRunRow.id == ProjectRecordLeaseRow.run_id,
                    )
                    .where(
                        ProjectRecordLeaseRow.project_id == project_id,
                        ProjectRecordLeaseRow.batch_id == batch_id,
                        ProjectRecordLeaseRow.state.in_(("held", "reconciling")),
                        WorkflowRunRow.status.in_(TERMINAL_STATUSES),
                    )
                )
            )
        if not terminal_ids:
            return
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            now = datetime.now(UTC)
            rows = list(
                session.scalars(
                    select(ProjectRecordLeaseRow).where(
                        ProjectRecordLeaseRow.id.in_(terminal_ids),
                        ProjectRecordLeaseRow.state.in_(("held", "reconciling")),
                    )
                )
            )
            for lease in rows:
                run_status = session.scalar(
                    select(WorkflowRunRow.status).where(
                        WorkflowRunRow.id == lease.run_id
                    )
                )
                if run_status in TERMINAL_STATUSES:
                    lease.state = "released"
                    lease.updated_at = lease.released_at = now
            self._commit(session)

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
            if (
                not terminal
                and row.status_revision != payload["expectedStatusRevision"]
            ):
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
            if not terminal:
                row.claim_gate_state = "closed"
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


def _claim_capacity_available(
    session: Session,
    row: ProjectBatchRow,
    batch_id: str,
    core_capacity: int,
) -> bool:
    request_concurrency = int(row.frozen_request.get("concurrency") or 1)
    run_policy = row.frozen_request["automation"]["runPolicy"]
    configured_concurrency = int(run_policy.get("concurrency", 1))
    configured_capacity = int(run_policy.get("maxLiveInstances", 1))
    batch_active = session.scalar(
        select(func.count())
        .select_from(ProjectTaskRow)
        .join(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
        .where(
            ProjectTaskRow.batch_id == batch_id,
            WorkflowRunRow.status.not_in(TERMINAL_STATUSES),
        )
    ) or 0
    automation_active = session.scalar(
        select(func.count())
        .select_from(ProjectTaskRow)
        .join(ProjectBatchRow, ProjectBatchRow.id == ProjectTaskRow.batch_id)
        .join(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
        .where(
            ProjectBatchRow.automation_id == row.automation_id,
            WorkflowRunRow.status.not_in(TERMINAL_STATUSES),
        )
    ) or 0
    global_active = session.scalar(
        select(func.count())
        .select_from(WorkflowRunRow)
        .where(WorkflowRunRow.status.not_in(TERMINAL_STATUSES))
    ) or 0
    return (
        batch_active < request_concurrency
        and batch_active < configured_concurrency
        and automation_active < configured_capacity
        and global_active < max(1, core_capacity)
    )


def _selection_guards(
    session: Session,
    project_id: str,
    input_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    """Capture the monotonic table facts that make a selection authoritative."""
    identities = sorted(
        {
            (item.get("tableId"), item.get("datasetGeneration"))
            for item in input_plan.get("inputs", [])
            if isinstance(item, dict)
            and isinstance(item.get("tableId"), str)
            and isinstance(item.get("datasetGeneration"), str)
        }
    )
    guards: list[dict[str, Any]] = []
    for table_id, generation in identities:
        table = session.scalar(
            select(DataTableRow).where(
                DataTableRow.project_id == project_id,
                DataTableRow.id == table_id,
            )
        )
        guards.append(
            {
                "tableId": table_id,
                "datasetGeneration": generation,
                "published": table.published if table is not None else None,
                "currentGeneration": (
                    table.current_generation if table is not None else None
                ),
                "tableRevision": table.table_revision if table is not None else None,
                "schemaGuardRevision": (
                    table.schema_guard_revision if table is not None else None
                ),
            }
        )
    return guards
