from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.application.models.service import ModelExecutionBinding
from autoflow.application.project_runs.interactions import ProjectRunInteractions
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.coordinator import _model_references
from autoflow.domain.models.errors import ModelError
from autoflow.domain.projects.models import ProjectError
from autoflow.domain.workflows.runtime import (
    TERMINAL_STATUSES,
    CoreRun,
    CoreRunStatus,
    WorkflowRuntimeError,
    thaw_json,
)
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from autoflow.infrastructure.process.project_test_browser_worker import wait_for_cleanup
from autoflow.infrastructure.process.project_workflow_worker import (
    WorkerOutcome,
    WorkflowWorkerError,
)


class WorkerPort(Protocol):
    def busy(self, run_id: str | None = None) -> bool: ...

    async def run(
        self,
        *,
        run_id: str,
        execution_generation: int,
        execution_plan: dict[str, Any],
        parameters: dict[str, Any],
        variables: dict[str, Any],
        browser: dict[str, Any],
        executable: Path | None,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
        model_bindings: list[dict[str, Any]],
    ) -> WorkerOutcome: ...

    async def send_command(self, run_id: str, execution_generation: int, command: dict[str, Any]) -> None: ...
    async def stop(self, run_id: str) -> None: ...
    async def force_stop(self, run_id: str) -> None: ...
    def discard_uncommitted_artifact(
        self,
        run_id: str,
        execution_generation: int,
        artifact_id: str,
        relative_path: str,
    ) -> None: ...
    async def shutdown(self) -> None: ...


class LeasePort(Protocol):
    executable: Path
    browser: dict[str, Any]

    def release(self) -> None: ...


class ResourcePort(Protocol):
    async def acquire(
        self, request: Mapping[str, Any], run_id: str
    ) -> LeasePort: ...


Recovery = Callable[[CoreRun], Awaitable[None]]
UNKNOWN_RESULT_ERROR = {
    "code": "WORKFLOW_RESULT_UNKNOWN",
    "message": "执行结果不明确，已撤销旧执行写入权限",
}
# Worker-side evidence that is already redacted and path-free (spec M1 R1-14).
DIAGNOSTIC_KEYS = (
    "causeCode", "diagnosticLog", "diagnosticLogUnavailable",
    "stderrTail", "stderrTailRedacted", "stderrTailOmitted",
)


def unknown_result_error(diagnostics: Mapping[str, Any] | None) -> dict[str, Any]:
    """The unchanged unknown-result error, plus safe diagnostics when the worker supplied them."""
    details = {key: diagnostics[key] for key in DIAGNOSTIC_KEYS if diagnostics and key in diagnostics}
    return {**UNKNOWN_RESULT_ERROR, "details": details} if details else dict(UNKNOWN_RESULT_ERROR)


@dataclass
class _RunOwner:
    run_id: str
    generation: int
    task: asyncio.Task[None] | None = None
    lease: LeasePort | None = None
    automatic_timeout: asyncio.Timeout | None = None
    automatic_remaining: float | None = None
    cleanup_unknown: bool = False
    browser_command_id: str | None = None
    waiting_manual: bool = False
    diagnostics: dict[str, Any] | None = None
    control: asyncio.Lock = field(default_factory=asyncio.Lock)


MAX_RUN_CAPACITY = 64
MEMORY_RECHECK_SECONDS = 5.0


def validate_capacity(capacity: int, live_capacity: int | None) -> tuple[int, int]:
    live = 2 * capacity if live_capacity is None and type(capacity) is int else live_capacity
    if type(capacity) is not int or not 1 <= capacity <= MAX_RUN_CAPACITY:
        raise ValueError(f'Run capacity must be an integer from 1 to {MAX_RUN_CAPACITY}')
    if type(live) is not int or not capacity <= live <= 2 * MAX_RUN_CAPACITY:
        raise ValueError('Live browser capacity must be at least the run capacity')
    return capacity, live


class WorkflowRunDispatcher:
    """Bounded owners for explicitly dispatched, frozen workflow runs."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        worker: WorkerPort,
        resources: ResourcePort,
        gate: QuiesceGate,
        recover_orphan: Recovery,
        *,
        project_end: Any | None = None,
        on_fenced: Callable[[str], None] = lambda _run_id: None,
        capacity: int = 1,
        live_capacity: int | None = None,
        memory_pressure: Callable[[], bool] = lambda: False,
        resolve_model: Callable[[str], ModelExecutionBinding] | None = None,
        resolve_default_model: Callable[[str], str] | None = None,
        force_stop_grace: timedelta = timedelta(seconds=30),
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._sessions = session_factory
        self._project_end = project_end
        self._worker = worker
        self.interactions = ProjectRunInteractions(session_factory, self._send_interaction)
        self._resources = resources
        self._gate = gate
        self._recover_orphan = recover_orphan
        self._on_fenced = on_fenced
        self._resolve_model = resolve_model
        self._resolve_default_model = resolve_default_model
        self._force_stop_grace = force_stop_grace
        self._now = now
        self._capacity, self._live_capacity = validate_capacity(capacity, live_capacity)
        self._memory_pressure = memory_pressure
        self._pause_reason: str | None = None
        self._owners: dict[str, _RunOwner] = {}
        self._recovering = False
        self._closed = False
        self._lock = asyncio.Lock()
        self._control = asyncio.Lock()
        self._idle_listeners: set[Callable[[], None]] = set()

    async def _send_interaction(self, run_id: str, generation: int, command: dict[str, Any]) -> None:
        try:
            await self._worker.send_command(run_id, generation, command)
        except (WorkflowWorkerError, OSError) as error:
            raise WorkflowRuntimeError(
                "INTERACTION_UNCONFIRMED", "交互命令尚未确认，请查询原命令结果", 503
            ) from error

    @property
    def capacity(self) -> int:
        """Maximum runs executing automatically at the same time (spec M1 R1-08)."""
        return self._capacity

    @property
    def live_capacity(self) -> int:
        """Maximum live browsers, including runs waiting for a person (spec M1 R1-09)."""
        return self._live_capacity

    def pause_dispatch(self, reason: str | None) -> None:
        """Refuse new dispatch with this reason until cleared with None; running owners are untouched."""
        self._pause_reason = reason
        if reason is None:
            self._wake_idle_listeners()

    def executing_count(self) -> int:
        return sum(1 for owner in self._owners.values() if not owner.waiting_manual)

    def set_capacity(self, capacity: int, live_capacity: int | None = None) -> None:
        """Apply a new limit; lowering it never stops runs that already own a slot."""
        self._capacity, self._live_capacity = validate_capacity(capacity, live_capacity)
        self._wake_idle_listeners()

    def subscribe_idle(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._idle_listeners.add(listener)

        def unsubscribe() -> None:
            self._idle_listeners.discard(listener)

        return unsubscribe

    async def startup(self) -> None:
        """Fence and reconcile old active runs; queued runs remain caller-owned."""
        self._recovering = True
        try:
            for run in self._nonterminal_runs():
                if run.status == "queued":
                    continue
                fenced = (
                    self._transition(run, "reconciling")
                    if run.status != "reconciling"
                    else run
                )
                try:
                    await self._recover_orphan(fenced)
                except Exception:  # noqa: BLE001,S112 - failure is durable state
                    continue
                if await self._finish_end(fenced.run_id, recovering=True):
                    continue
                self._transition_current(
                    fenced.run_id,
                    fenced.execution_generation,
                    "interrupted",
                    error=UNKNOWN_RESULT_ERROR,
                )
        finally:
            self._recovering = False

    async def dispatch(
        self,
        run_id: str,
        *,
        expected_status_revision: int,
        execution_generation: int,
    ) -> CoreRun:
        async with self._lock:
            if self._closed:
                raise WorkflowRuntimeError(
                    "WORKFLOW_DISPATCHER_CLOSED", "运行服务正在关闭", 503
                )
            if self._get_run(run_id).status != "queued":
                raise WorkflowRuntimeError(
                    "RUN_NOT_DISPATCHABLE", "运行不在等待派发状态"
                )
            other_runs = [
                run for run in self._nonterminal_runs() if run.run_id != run_id
            ]
            if (
                self._recovering
                or self.executing_count() >= self.capacity
                or len(self._owners) >= self.live_capacity
                or any(run.status != "queued" and run.run_id not in self._owners for run in other_runs)
                or (not self._owners and self._worker.busy())
            ):
                raise WorkflowRuntimeError("WORKFLOW_CAPACITY_FULL", "当前运行容量已满")
            if self._pause_reason is not None:
                raise WorkflowRuntimeError("WORKFLOW_CAPACITY_FULL", self._pause_reason)
            # With no run executing nothing can release memory, so pausing would stall the queue forever.
            if self._owners and self._memory_pressure():
                # Spec M1 R1-10: pause new dispatch; re-offer capacity once pressure may have eased.
                asyncio.get_running_loop().call_later(MEMORY_RECHECK_SECONDS, self._wake_idle_listeners)
                raise WorkflowRuntimeError(
                    "WORKFLOW_CAPACITY_FULL", "本机内存占用超过 85%，暂停派发新任务"
                )
            with self._gate.mutation() as admitted:
                if not admitted:
                    raise WorkflowRuntimeError(
                        "WORKFLOW_ADMISSION_CLOSED", "运行准入已关闭", 503
                    )
                run = self._transition_identity(
                    run_id, "running", expected_status_revision, execution_generation
                )
            owner = _RunOwner(run_id, run.execution_generation)
            self._owners[run_id] = owner
            owner.task = asyncio.create_task(self._execute(run, owner))
            return run

    def pause_manual(self, run_id: str, generation: int) -> None:
        run = self._get_run(run_id)
        owner = self._owners.get(run_id)
        if owner is None or owner.generation != generation or run.status != 'running' or run.execution_generation != generation:
            raise WorkflowRuntimeError('EXECUTION_GENERATION_REVOKED', '执行代次已失效')
        self._transition(run, 'waiting_manual')
        owner.waiting_manual = True
        self._wake_idle_listeners()
        if owner.automatic_timeout is not None:
            deadline = owner.automatic_timeout.when()
            owner.automatic_remaining = max(0, deadline - asyncio.get_running_loop().time()) if deadline is not None else None
            owner.automatic_timeout.reschedule(None)

    def resume_manual(self, run_id: str, generation: int) -> None:
        run = self._get_run(run_id)
        owner = self._owners.get(run_id)
        if owner is None or owner.generation != generation or run.status != 'waiting_manual' or run.execution_generation != generation:
            raise WorkflowRuntimeError('EXECUTION_GENERATION_REVOKED', '执行代次已失效')
        # Same live owner continues; resume_queued -> running is reserved for
        # dispatching a new owner and deliberately increments the generation.
        self._transition(run, 'running')
        owner.waiting_manual = False
        if owner.automatic_timeout is not None and owner.automatic_remaining is not None:
            owner.automatic_timeout.reschedule(asyncio.get_running_loop().time() + owner.automatic_remaining)

    async def cancel(
        self,
        run_id: str,
        *,
        expected_status_revision: int,
        execution_generation: int,
    ) -> CoreRun:
        async with self._control:
            current = self._get_run(run_id)
            if (
                current.status == "finishing"
                and self._project_end is not None
                and self._project_end.operation(run_id) is not None
            ):
                if current.status_revision != expected_status_revision:
                    raise WorkflowRuntimeError(
                        "RUN_STATUS_CONFLICT", "运行状态已发生变化"
                    )
                if current.execution_generation != execution_generation:
                    raise WorkflowRuntimeError(
                        "EXECUTION_GENERATION_REVOKED", "执行代次已失效"
                    )
                return current
            run = self._transition_identity(
                run_id, "stopping", expected_status_revision, execution_generation
            )
            if run.execution_generation == 0:  # queued: no resource or worker ever existed
                return self._transition_current(run_id, 0, "cancelled")
            await self._worker.stop(run_id)
            return self._get_run(run_id)

    async def force_stop(
        self,
        run_id: str,
        *,
        expected_status_revision: int,
        execution_generation: int,
    ) -> CoreRun:
        async with self._owner_control(run_id):
            return await self._force_stop(
                run_id, expected_status_revision, execution_generation
            )

    async def _force_stop(
        self, run_id: str, expected_status_revision: int, execution_generation: int
    ) -> CoreRun:
        owner = self._owners.get(run_id)
        run = self.validate_force_stop(
            run_id, expected_status_revision, execution_generation
        )
        fenced = (
            self._transition_identity(
                run_id, "reconciling", expected_status_revision, execution_generation
            )
            if run.status != "reconciling"
            else run
        )
        owner_task = owner.task if owner is not None else None
        if owner is not None and owner_task is not None:
            cleanup_was_unknown = owner.cleanup_unknown
            owner_task.cancel()
            if not await self._task_cleanup_confirmed(owner_task, owner):
                if not cleanup_was_unknown:
                    return self._get_run(run_id)
                try:
                    await self._recover_orphan(fenced)
                except Exception:  # noqa: BLE001 - retain unknown ownership
                    return self._get_run(run_id)
                owner.cleanup_unknown = False
            elif cleanup_was_unknown:
                try:
                    await self._recover_orphan(fenced)
                except Exception:  # noqa: BLE001 - retain unknown ownership
                    return self._get_run(run_id)
                owner.cleanup_unknown = False
        try:
            if owner is not None:
                await self._worker.force_stop(run_id)
            else:
                await self._recover_orphan(fenced)
        except Exception:  # noqa: BLE001 - cleanup ownership remains unknown
            return self._get_run(run_id)
        if self._worker.busy(run_id):
            return self._get_run(run_id)
        if await self._finish_end_locked(run_id, recovering=True):
            if owner is not None:
                self._release_lease(owner)
                self._clear_owner(owner)
            return self._get_run(run_id)
        if owner is not None:
            self._release_lease(owner)
        result = self._transition_current(
            run_id,
            fenced.execution_generation,
            "interrupted",
            error=UNKNOWN_RESULT_ERROR,
        )
        if owner is not None:
            self._clear_owner(owner)
        return result

    def query_run(self, run_id: str) -> CoreRun:
        return self._get_run(run_id)

    def validate_force_stop(
        self, run_id: str, expected_status_revision: int, execution_generation: int
    ) -> CoreRun:
        run = self._get_run(run_id)
        if run.status_revision != expected_status_revision:
            raise WorkflowRuntimeError("RUN_STATUS_CONFLICT", "运行状态已发生变化")
        if run.execution_generation != execution_generation:
            raise WorkflowRuntimeError("EXECUTION_GENERATION_REVOKED", "执行代次已失效")
        allowed, _available_at = self.force_stop_state(run_id)
        if not allowed:
            raise WorkflowRuntimeError(
                "FORCE_STOP_GRACE_ACTIVE", "普通停止宽限期尚未结束"
            )
        return run

    def force_stop_state(self, run_id: str) -> tuple[bool, datetime | None]:
        """Return the dispatcher-authoritative force-stop gate for one run."""
        run = self._get_run(run_id)
        if run.status == "reconciling":
            return True, self._now()
        if run.status != "stopping":
            return False, None
        available_at = _aware(run.updated_at) + self._force_stop_grace
        return self._now() >= available_at, available_at

    async def reconcile(self, run_id: str) -> CoreRun:
        async with self._owner_control(run_id):
            return await self._reconcile(run_id)

    async def _reconcile(self, run_id: str) -> CoreRun:
        owner = self._owners.get(run_id)
        run = self._get_run(run_id)
        if run.status != "reconciling":
            raise WorkflowRuntimeError("RUN_NOT_RECONCILING", "运行不在核验状态")
        try:
            owner_task = owner.task if owner is not None else None
            if owner is not None and owner_task is not None:
                owner_task.cancel()
                if (
                    not await self._task_cleanup_confirmed(owner_task, owner)
                    or owner.cleanup_unknown
                ):
                    await self._recover_orphan(run)
                    owner.cleanup_unknown = False
            if owner is not None:
                await self._worker.force_stop(run_id)
            else:
                await self._recover_orphan(run)
        except Exception:  # noqa: BLE001 - recovery adapters define their failures
            return self._get_run(run_id)
        if self._worker.busy(run_id):
            return self._get_run(run_id)
        if await self._finish_end_locked(run_id, recovering=True):
            if owner is not None:
                self._release_lease(owner)
                self._clear_owner(owner)
            return self._get_run(run_id)
        if owner is not None:
            self._release_lease(owner)
        result = self._transition_current(
            run_id,
            run.execution_generation,
            "interrupted",
            error=UNKNOWN_RESULT_ERROR,
        )
        if owner is not None:
            self._clear_owner(owner)
        return result

    def blockers(self) -> list[str]:
        blockers: list[str] = []
        if self._nonterminal_runs():
            blockers.append("workflow_runs_active")
        if self._worker.busy() or self._owners:
            blockers.append("workflow_worker_busy")
        return blockers

    async def shutdown(self) -> None:
        async with self._control:
            await self._shutdown()

    async def _shutdown(self) -> None:
        self._closed = True
        owners = list(self._owners.values())
        for owner in owners:
            run = self._get_run(owner.run_id)
            if not run.terminal and run.status != "reconciling":
                self._transition(run, "reconciling")
            if owner.task is not None:
                owner.task.cancel()
        errors: list[Exception] = []
        for owner in owners:
            async with owner.control:
                if owner.task is not None:
                    await self._task_cleanup_confirmed(owner.task, owner)
                try:
                    await self._worker.force_stop(owner.run_id)
                    if owner.cleanup_unknown:
                        await self._recover_orphan(self._get_run(owner.run_id))
                        owner.cleanup_unknown = False
                    if self._worker.busy(owner.run_id):
                        raise WorkflowRuntimeError('WORKFLOW_CLEANUP_FAILED', '执行进程清理尚未确认')
                    self._release_lease(owner)
                    self._clear_owner(owner)
                except Exception as error:  # noqa: BLE001 - keep this owner's lease
                    errors.append(error)
        try:
            await self._worker.shutdown()
        except Exception as error:  # noqa: BLE001 - keep unknown owners
            errors.append(error)
        if errors:
            raise errors[0]

    async def wait_idle(self) -> None:
        tasks = [owner.task for owner in self._owners.values() if owner.task is not None]
        if tasks:
            await asyncio.gather(*(asyncio.shield(task) for task in tasks))

    def _owner_control(self, run_id: str) -> asyncio.Lock:
        owner = self._owners.get(run_id)
        return owner.control if owner is not None else self._control

    async def initialize_browser(self, run_id: str, generation: int, command_id: str, prepare: Callable[[], Mapping[str, Any]]) -> dict[str, Any]:
        owner = self._owners.get(run_id)
        if owner is None or owner.generation != generation:
            raise WorkflowRuntimeError('CAPABILITY_SCOPE_DENIED', '运行所有权已失效', 409)
        async with owner.control:
            current = self._get_run(run_id)
            if current.status != 'running' or current.execution_generation != generation:
                raise WorkflowRuntimeError('CAPABILITY_SCOPE_DENIED', '运行已停止', 409)
            if owner.lease is not None:
                if owner.browser_command_id != command_id:
                    raise WorkflowRuntimeError('BROWSER_INSTANCE_ALREADY_INITIALIZED', '任务已有浏览器实例，请使用当前实例', 409)
            else:
                with self._gate.mutation() as admitted:
                    if not admitted:
                        raise WorkflowRuntimeError('WORKFLOW_ADMISSION_CLOSED', '运行准入已关闭', 503)
                    request = prepare()
                    owner.lease = await self._resources.acquire(request, current.run_id)
                    owner.browser_command_id = command_id
            return {'browser': dict(owner.lease.browser), 'executablePath': str(owner.lease.executable)}

    async def _execute(self, dispatched: CoreRun, owner: _RunOwner) -> None:
        lease: LeasePort | None = None
        cancelled = False
        unhandled = False
        try:
            with self._gate.mutation() as admitted:
                if not admitted:
                    raise WorkflowRuntimeError(
                        "WORKFLOW_ADMISSION_CLOSED", "运行准入已关闭", 503
                    )
                content = self._prepared(dispatched.prepared_content_id)
                execution_plan = thaw_json(content.execution_plan)
                try:
                    model_bindings = self._model_bindings(
                        execution_plan, dispatched.resource_request
                    )
                except ModelError as error:
                    current = self._get_run(dispatched.run_id)
                    if current.status == "stopping":
                        self._transition_current(current.run_id, current.execution_generation, "cancelled")
                    elif current.status == "running":
                        finishing = self._transition(current, "finishing")
                        self._transition_current(
                            finishing.run_id, finishing.execution_generation, "failed",
                            error={"code": error.code, "message": error.message},
                        )
                    return
                if "browser.cloakbrowser" in content.capability_requirements and dispatched.resource_request.get("browser") != "node":
                    lease = await self._resources.acquire(
                        dispatched.resource_request, dispatched.run_id
                    )
                    owner.lease = lease
                current = self._get_run(dispatched.run_id)
                if (
                    current.status != "running"
                    or current.execution_generation != dispatched.execution_generation
                ):
                    self._release_lease(owner)
                    if current.status == "stopping":
                        self._transition_current(
                            current.run_id, current.execution_generation, "cancelled"
                        )
                    return
                budget = current.resource_request.get(
                    "automaticExecutionTimeoutSeconds", 0
                )
                timeout = asyncio.timeout(budget or None)
                owner.automatic_timeout = timeout
                try:
                    async with timeout:
                        project_input_context = self._project_input_context(current)
                        if project_input_context:
                            execution_plan["projectInputContext"] = project_input_context
                        outcome = await self._worker.run(
                            run_id=current.run_id,
                            execution_generation=current.execution_generation,
                            execution_plan=execution_plan,
                            parameters=thaw_json(current.parameters),
                            variables=self._variables(content, current),
                            browser=dict(lease.browser) if lease else {},
                            executable=lease.executable if lease else None,
                            on_event=lambda event: self._commit_event(
                                current, content, event
                            ),
                            # Remediation M3 R3-04: batch-capable workers commit process events together.
                            **({"on_events": lambda events: self._commit_events(current, content, events)}
                               if getattr(self._worker, "supports_event_batches", False) else {}),
                            model_bindings=model_bindings,
                        )
                except TimeoutError:
                    if not timeout.expired():
                        raise
                    # Worker.run must finish its cancellation cleanup before this returns.
                    # Unconfirmed ownership follows the existing reconcile/fence path below.
                    outcome = WorkerOutcome(
                        "timed_out",
                        {
                            "code": "AUTOMATIC_EXECUTION_TIMEOUT",
                            "message": "自动执行超时",
                        },
                        not self._worker.busy(dispatched.run_id),
                    )
            if self._worker.busy(dispatched.run_id) or not outcome.cleanup_confirmed:
                raise RuntimeError("worker cleanup unconfirmed")
            if await self._finish_end(dispatched.run_id):
                self._release_lease(owner)
                return
            self._release_lease(owner)
            current = self._get_run(dispatched.run_id)
            if (
                current.execution_generation != dispatched.execution_generation
                or current.terminal
            ):
                return
            if current.status == "stopping" or outcome.status == "cancelled":
                self._transition_current(
                    current.run_id, current.execution_generation, "cancelled"
                )
                return
            finishing = (
                current
                if current.status == "finishing"
                else self._transition(current, "finishing")
            )
            target: CoreRunStatus = outcome.status
            self._transition_current(
                finishing.run_id,
                finishing.execution_generation,
                target,
                error=outcome.error,
            )
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception as error:
            logging.getLogger(__name__).warning("Project worker requires reconciliation: %s (%s)", type(error).__name__, getattr(error, "code", "unclassified"))
            details = getattr(error, "details", None)
            if isinstance(details, dict):
                owner.diagnostics = details
            current = self._get_run(dispatched.run_id)
            if current.execution_generation != dispatched.execution_generation:
                unhandled = True
                raise
            if current.terminal:
                return
            fenced = self._transition(current, "reconciling")
            try:
                if owner.lease is None:
                    await self._recover_orphan(fenced)
                else:
                    await self._worker.force_stop(current.run_id)
            except Exception:  # noqa: BLE001 - retain lease while cleanup is unknown
                owner.cleanup_unknown = True
                unhandled = True
                return
            if self._worker.busy(dispatched.run_id):
                return
            if (
                self._project_end is not None
                and self._project_end.operation(current.run_id) is not None
            ):
                unhandled = True
                return
            self._release_lease(owner)
            self._transition_current(
                fenced.run_id,
                fenced.execution_generation,
                "interrupted",
                error=unknown_result_error(owner.diagnostics),
            )
        finally:
            owner.automatic_timeout = None
            owner.automatic_remaining = None
            self.interactions.forget_run(dispatched.run_id)
            async with self._lock:
                if owner.task is asyncio.current_task():
                    if not cancelled and not unhandled:
                        owner.task = None
                    if (
                        not cancelled
                        and not unhandled
                        and owner.lease is None
                        and not self._worker.busy(dispatched.run_id)
                    ):
                        self._clear_owner(owner)
            self._wake_idle_listeners()

    def _wake_idle_listeners(self) -> None:
        for listener in tuple(self._idle_listeners):
            listener()

    async def _finish_end(self, run_id: str, *, recovering: bool = False) -> bool:
        async with self._control:
            return await self._finish_end_locked(run_id, recovering=recovering)

    async def _finish_end_locked(
        self, run_id: str, *, recovering: bool = False
    ) -> bool:
        if self._project_end is None or self._project_end.operation(run_id) is None:
            return False
        current = self._get_run(run_id)
        if current.terminal:
            return True
        if not recovering and current.status != "finishing":
            return False
        work = asyncio.create_task(
            asyncio.to_thread(
                self._project_end.recover if recovering else self._project_end.finalize,
                run_id,
            )
        )
        try:
            try:
                result = await asyncio.shield(work)
            except asyncio.CancelledError:
                await wait_for_cleanup(work)
                raise
        except ProjectError as error:
            if error.code in {
                "INSTANCE_NOT_QUIESCENT",
                "INSTANCE_OWNERSHIP_UNKNOWN",
            }:
                raise RuntimeError("End browser ownership remains unknown") from error
            self._transition_current(
                run_id,
                current.execution_generation,
                "failed",
                error={
                    "code": error.code,
                    "message": error.message,
                    "details": error.details,
                },
            )
            return True
        if result is None:
            return False
        business, outcome, result_error = result
        target: CoreRunStatus = (
            "succeeded"
            if outcome.get("complete") and business == "succeeded"
            else "failed"
        )
        self._transition_current(
            run_id,
            current.execution_generation,
            target,
            error=result_error
            or (
                {"code": "END_BUSINESS_FAILED", "message": "End 业务结果为失败"}
                if target == "failed"
                else None
            ),
        )
        return True

    def _model_bindings(
        self, plan: dict[str, Any], resource_request: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        document = plan.get("document")
        if not isinstance(document, dict):
            document = {"nodes": [
                {"id": node["nodeId"], "data": node["data"]}
                for node in plan["nodes"]
            ]}
        documents = [document]
        for snapshot in plan.get("customModuleDependencies", {}).values():
            if isinstance(snapshot, dict) and isinstance(snapshot.get("workflow"), dict):
                documents.append(snapshot["workflow"])
        documents.extend(
            snapshot for snapshot in plan.get("workflowDependencies", {}).values()
            if isinstance(snapshot, dict)
        )
        default_model_id: str | None = None
        for node in (node for item in documents for node in item["nodes"]):
            data = node["data"]
            if not str(data.get("moduleType", "")).startswith("ai_"):
                continue
            config = data.get("config", data)
            if not isinstance(config, dict):
                continue
            model_id = config.get("modelId")
            if model_id is not None and not isinstance(model_id, str):
                raise ModelError("MODEL_ID_INVALID", "模型标识必须是字符串", 422)
            if isinstance(model_id, str) and model_id.strip():
                continue
            provider_id = resource_request.get("modelProviderId")
            if not isinstance(provider_id, str) or not provider_id:
                raise ModelError("PROJECT_DEFAULT_MODEL_MISSING", "项目未设置默认模型服务，请显式选择模型", 422)
            if self._resolve_default_model is None:
                raise ModelError("MODEL_SERVICE_UNAVAILABLE", "模型服务不可用", 503)
            if default_model_id is None:
                default_model_id = self._resolve_default_model(provider_id)
            config["modelId"] = default_model_id
        references = _model_references(documents)
        if references and self._resolve_model is None:
            raise ModelError("MODEL_SERVICE_UNAVAILABLE", "模型服务不可用", 503)
        bindings: dict[str, ModelExecutionBinding] = {}
        for model_id, _node_id, _path in references:
            if model_id not in bindings:
                assert self._resolve_model is not None
                bindings[model_id] = self._resolve_model(model_id)
        return [
            {
                "modelId": binding.model_id,
                "modelKey": binding.model_key,
                "presetId": binding.connection.preset_id,
                "providerKind": binding.connection.provider_kind,
                "baseUrl": binding.connection.base_url,
                "secret": binding.secret,
            }
            for binding in bindings.values()
        ]

    async def _commit_event(
        self, run: CoreRun, content: Any, event: dict[str, Any]
    ) -> None:
        await self._commit_events(run, content, [event])

    async def _commit_events(
        self, run: CoreRun, content: Any, events: list[dict[str, Any]]
    ) -> None:
        """Commit events in one transaction off the event loop; returning is the worker's ACK.

        Remediation M3 R3-04 / rule 3: process-event batches share a commit, and SQLite work no
        longer blocks the loop. Event identities keep replays idempotent.
        """
        try:
            observed = await asyncio.to_thread(self._persist_events, run, content, events)
        except Exception:
            for event in events:
                self._discard_uncommitted_artifact(run, event)
            raise
        for event in observed:
            self.interactions.observe(event)

    def _persist_events(
        self, run: CoreRun, content: Any, events: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        current = self._get_run(run.run_id)
        if (
            current.execution_generation != run.execution_generation
            or current.status not in {"running", "finishing", "stopping"}
        ):
            raise WorkflowRuntimeError("EXECUTION_GENERATION_REVOKED", "执行代次已失效")
        known = set(content.execution_plan.get("orderedNodeIds", ()))
        for snapshot in content.execution_plan.get("customModuleDependencies", {}).values():
            if isinstance(snapshot, Mapping) and isinstance(snapshot.get("workflow"), Mapping):
                known.update(
                    node["id"] for node in snapshot["workflow"].get("nodes", ())
                    if isinstance(node, Mapping) and isinstance(node.get("id"), str)
                )
        for snapshot in content.execution_plan.get("workflowDependencies", {}).values():
            if isinstance(snapshot, Mapping):
                known.update(
                    node["id"] for node in snapshot.get("nodes", ())
                    if isinstance(node, Mapping) and isinstance(node.get("id"), str)
                )
        for event in events:
            node_id = event.get("nodeId")
            if node_id is not None and node_id not in known:
                raise WorkflowRuntimeError("RUN_EVENT_NODE_UNKNOWN", "事件引用了未知节点")
        values = []
        for event in events:
            value = self.interactions.public_event(dict(event))
            value.pop("sequence", None)
            values.append(value)
        for attempt in range(5):
            try:
                with self._sessions() as session:
                    repository = SqlAlchemyWorkflowRuntimeRepository(session)
                    persisted = repository.append_events(values) if len(values) > 1 else [repository.append_event(values[0])]
                    for value in values:
                        self.interactions.confirm(session, value)
                    session.commit()  # returning is the worker manager's ACK boundary
                break
            except WorkflowRuntimeError as error:
                # Off the loop, an event commit can race a status change on the loop thread;
                # the sequence CAS fails cleanly and the same identities are retried.
                if error.code != "RUN_EVENT_SEQUENCE_CONFLICT" or attempt == 4:
                    raise
        return [event for event, stored in zip(events, persisted, strict=True) if stored.sequence > current.last_sequence]

    def _discard_uncommitted_artifact(
        self, run: CoreRun, event: dict[str, Any]
    ) -> None:
        if event.get("kind") != "artifact" or not isinstance(
            event.get("payload"), dict
        ):
            return
        payload = event["payload"]
        artifact_id, relative_path = (
            payload.get("artifactId"),
            payload.get("relativePath"),
        )
        if not isinstance(artifact_id, str) or not isinstance(relative_path, str):
            return
        try:
            with self._sessions() as session:
                repository = SqlAlchemyWorkflowRuntimeRepository(session)
                committed = repository.get_artifact(run.run_id, artifact_id)
                if repository.artifact_path_is_registered(run.run_id, relative_path):
                    return
        except Exception:  # noqa: BLE001 - unknown fact checks must preserve evidence.
            return
        if committed is None:
            discard = getattr(self._worker, "discard_uncommitted_artifact", None)
            if discard is not None:
                discard(
                    run.run_id,
                    run.execution_generation,
                    artifact_id,
                    relative_path,
                )

    def _get_run(self, run_id: str) -> CoreRun:
        with self._sessions() as session:
            run = SqlAlchemyWorkflowRuntimeRepository(session).get_run(run_id=run_id)
        if run is None:
            raise WorkflowRuntimeError("RUN_NOT_FOUND", "运行不存在", 404)
        return run

    def _prepared(self, prepared_content_id: str) -> Any:
        with self._sessions() as session:
            value = SqlAlchemyWorkflowRuntimeRepository(session).get_prepared_content(
                prepared_content_id=prepared_content_id
            )
        if value is None:
            raise WorkflowRuntimeError(
                "PREPARED_CONTENT_MISSING", "不可变执行内容不存在", 404
            )
        return value

    def _transition_identity(
        self, run_id: str, target: CoreRunStatus, revision: int, generation: int
    ) -> CoreRun:
        with self._sessions() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            before = repository.get_run(run_id=run_id)
            changed = repository.transition_run(
                run_id,
                target_status=target,
                expected_status_revision=revision,
                expected_execution_generation=generation,
                now=self._now(),
            )
            if before is not None and changed.status_revision != before.status_revision:
                repository.append_event(self._status_event(changed))
                changed = repository.get_run(run_id=run_id) or changed
            self.interactions.finish(session, changed)
            session.commit()
            if changed.status == "reconciling":
                self._on_fenced(run_id)
            return changed

    def _transition(self, run: CoreRun, target: CoreRunStatus) -> CoreRun:
        return self._transition_identity(
            run.run_id, target, run.status_revision, run.execution_generation
        )

    def _transition_current(
        self,
        run_id: str,
        generation: int,
        target: CoreRunStatus,
        error: dict[str, Any] | None = None,
    ) -> CoreRun:
        current = self._get_run(run_id)
        with self._sessions() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            changed = repository.transition_run(
                run_id,
                target_status=target,
                expected_status_revision=current.status_revision,
                expected_execution_generation=generation,
                now=self._now(),
                error=error,
            )
            if changed.status_revision != current.status_revision:
                repository.append_event(self._status_event(changed))
                changed = repository.get_run(run_id=run_id) or changed
            self.interactions.finish(session, changed)
            session.commit()
            if changed.status == "reconciling":
                self._on_fenced(run_id)
            return changed

    def _nonterminal_runs(self) -> list[CoreRun]:
        with self._sessions() as session:
            ids = session.scalars(
                select(WorkflowRunRow.id)
                .where(WorkflowRunRow.status.not_in(TERMINAL_STATUSES))
                .order_by(WorkflowRunRow.created_at, WorkflowRunRow.id)
            ).all()
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            return [run for run_id in ids if (run := repository.get_run(run_id=run_id))]

    def _release_lease(self, owner: _RunOwner) -> None:
        if owner.lease is not None:
            owner.lease.release()
            owner.lease = None

    def _clear_owner(self, owner: _RunOwner) -> None:
        if self._owners.get(owner.run_id) is owner:
            self._owners.pop(owner.run_id)

    async def _task_cleanup_confirmed(self, task: asyncio.Task[None], owner: _RunOwner) -> bool:
        results = await asyncio.gather(task, return_exceptions=True)
        confirmed = all(result is None or isinstance(result, asyncio.CancelledError) for result in results)
        if not confirmed:
            owner.cleanup_unknown = True
        return confirmed

    def _status_event(self, run: CoreRun) -> dict[str, Any]:
        return {
            "eventId": str(uuid4()),
            "runId": run.run_id,
            "executionGeneration": run.execution_generation,
            "kind": "status",
            "occurredAt": self._now().isoformat(),
            "payload": {"status": run.status, "statusRevision": run.status_revision},
        }

    def _project_input_context(self, run: CoreRun) -> dict[str, Any]:
        from autoflow.domain.project_automations.rules import processing_input
        from autoflow.domain.workflows.project_inputs import input_context
        from autoflow.infrastructure.database.project_run_models import (
            ProjectBatchRow,
            ProjectTaskInputSnapshotRow,
            ProjectTaskRow,
        )
        with self._sessions() as session:
            task = session.scalar(select(ProjectTaskRow).where(ProjectTaskRow.run_id == run.run_id))
            if task is None:
                return {}
            snapshot = session.scalar(select(ProjectTaskInputSnapshotRow).where(ProjectTaskInputSnapshotRow.task_id == task.id))
            if snapshot is None:
                return {}
            batch = session.get(ProjectBatchRow, task.batch_id)
            plan = ((batch.frozen_request or {}).get('automation') or {}).get('inputPlan') if batch else None
            primary = processing_input(plan) if isinstance(plan, dict) else None
            return input_context(snapshot.inputs, snapshot.parameters, primary if isinstance(primary, str) else None)

    @staticmethod
    def _variables(content: Any, run: CoreRun) -> dict[str, Any]:
        document = thaw_json(content.document)
        raw = document.get("content", {}).get("variables", [])
        values = {
            item["name"]: item.get("value")
            for item in raw
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        values.update(thaw_json(run.parameters))
        return values


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
