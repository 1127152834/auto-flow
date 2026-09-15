from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.application.settings.runtime import QuiesceGate
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
from autoflow.infrastructure.process.workflow_worker import WorkerOutcome


class WorkerPort(Protocol):
    def busy(self) -> bool: ...

    async def run(
        self,
        *,
        run_id: str,
        execution_generation: int,
        execution_plan: dict[str, Any],
        parameters: dict[str, Any],
        variables: dict[str, Any],
        browser: dict[str, Any],
        executable: Path,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> WorkerOutcome: ...

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
        self, request: Mapping[str, Any], run_request_id: str
    ) -> LeasePort: ...


Recovery = Callable[[CoreRun], Awaitable[None]]
UNKNOWN_RESULT_ERROR = {
    "code": "WORKFLOW_RESULT_UNKNOWN",
    "message": "执行结果不明确，已撤销旧执行写入权限",
}


class WorkflowRunDispatcher:
    """Single-capacity owner for explicitly dispatched, frozen workflow runs."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        worker: WorkerPort,
        resources: ResourcePort,
        gate: QuiesceGate,
        recover_orphan: Recovery,
        *,
        force_stop_grace: timedelta = timedelta(seconds=30),
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._sessions = session_factory
        self._worker = worker
        self._resources = resources
        self._gate = gate
        self._recover_orphan = recover_orphan
        self._force_stop_grace = force_stop_grace
        self._now = now
        self._task: asyncio.Task[None] | None = None
        self._lease: LeasePort | None = None
        self._run_id: str | None = None
        self._owner_cleanup_unknown = False
        self._closed = False
        self._lock = asyncio.Lock()
        self._control = asyncio.Lock()
        self._idle_listeners: set[Callable[[], None]] = set()

    @property
    def capacity(self) -> int:
        """Maximum simultaneous runs supported by this concrete core owner."""
        return 1

    def subscribe_idle(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._idle_listeners.add(listener)

        def unsubscribe() -> None:
            self._idle_listeners.discard(listener)

        return unsubscribe

    async def startup(self) -> None:
        """Fence and reconcile old active runs; queued runs remain caller-owned."""
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
            self._transition_current(
                fenced.run_id,
                fenced.execution_generation,
                "interrupted",
                error=UNKNOWN_RESULT_ERROR,
            )

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
                self._task is not None
                or self._worker.busy()
                or any(run.status != "queued" for run in other_runs)
            ):
                raise WorkflowRuntimeError("WORKFLOW_CAPACITY_FULL", "当前运行容量已满")
            with self._gate.mutation() as admitted:
                if not admitted:
                    raise WorkflowRuntimeError(
                        "WORKFLOW_ADMISSION_CLOSED", "运行准入已关闭", 503
                    )
                run = self._transition_identity(
                    run_id, "running", expected_status_revision, execution_generation
                )
            self._run_id = run_id
            self._task = asyncio.create_task(self._execute(run))
            return run

    async def cancel(
        self,
        run_id: str,
        *,
        expected_status_revision: int,
        execution_generation: int,
    ) -> CoreRun:
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
        async with self._control:
            return await self._force_stop(
                run_id, expected_status_revision, execution_generation
            )

    async def _force_stop(
        self, run_id: str, expected_status_revision: int, execution_generation: int
    ) -> CoreRun:
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
        owner_task = self._task if self._run_id == run_id else None
        if owner_task is not None:
            cleanup_was_unknown = self._owner_cleanup_unknown
            owner_task.cancel()
            if not await self._task_cleanup_confirmed(owner_task):
                if not cleanup_was_unknown:
                    return self._get_run(run_id)
                try:
                    await self._recover_orphan(fenced)
                except Exception:  # noqa: BLE001 - retain unknown ownership
                    return self._get_run(run_id)
                self._owner_cleanup_unknown = False
            elif cleanup_was_unknown:
                try:
                    await self._recover_orphan(fenced)
                except Exception:  # noqa: BLE001 - retain unknown ownership
                    return self._get_run(run_id)
                self._owner_cleanup_unknown = False
        try:
            if self._run_id == run_id:
                await self._worker.force_stop(run_id)
            else:
                await self._recover_orphan(fenced)
        except Exception:  # noqa: BLE001 - cleanup ownership remains unknown
            return self._get_run(run_id)
        if self._worker.busy():
            return self._get_run(run_id)
        if self._run_id == run_id:
            self._release_lease()
        result = self._transition_current(
            run_id,
            fenced.execution_generation,
            "interrupted",
            error=UNKNOWN_RESULT_ERROR,
        )
        if self._run_id == run_id:
            self._clear_owner()
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
        async with self._control:
            return await self._reconcile(run_id)

    async def _reconcile(self, run_id: str) -> CoreRun:
        run = self._get_run(run_id)
        if run.status != "reconciling":
            raise WorkflowRuntimeError("RUN_NOT_RECONCILING", "运行不在核验状态")
        try:
            owner_task = self._task if self._run_id == run_id else None
            if owner_task is not None:
                owner_task.cancel()
                if (
                    not await self._task_cleanup_confirmed(owner_task)
                    or self._owner_cleanup_unknown
                ):
                    await self._recover_orphan(run)
                    self._owner_cleanup_unknown = False
            if self._run_id == run_id:
                await self._worker.force_stop(run_id)
            else:
                await self._recover_orphan(run)
        except Exception:  # noqa: BLE001 - recovery adapters define their failures
            return self._get_run(run_id)
        if self._worker.busy():
            return self._get_run(run_id)
        if self._run_id == run_id:
            self._release_lease()
        result = self._transition_current(
            run_id,
            run.execution_generation,
            "interrupted",
            error=UNKNOWN_RESULT_ERROR,
        )
        if self._run_id == run_id:
            self._clear_owner()
        return result

    def blockers(self) -> list[str]:
        blockers: list[str] = []
        if self._nonterminal_runs():
            blockers.append("workflow_runs_active")
        if self._worker.busy() or self._task is not None:
            blockers.append("workflow_worker_busy")
        return blockers

    async def shutdown(self) -> None:
        async with self._control:
            await self._shutdown()

    async def _shutdown(self) -> None:
        self._closed = True
        task = self._task
        run_id = self._run_id
        if run_id is not None:
            run = self._get_run(run_id)
            if not run.terminal and run.status != "reconciling":
                run = self._transition(run, "reconciling")
            if task is not None:
                task.cancel()
        error: Exception | None = None
        task_error: Exception | None = None
        if task is not None and not await self._task_cleanup_confirmed(task):
            task_error = WorkflowRuntimeError(
                "WORKFLOW_CLEANUP_FAILED", "运行任务清理尚未确认"
            )
        try:
            await self._worker.shutdown()
        except Exception as caught:  # noqa: BLE001 - shutdown must retain cleanup fact
            error = caught
        if error is None and self._owner_cleanup_unknown and run_id is not None:
            try:
                await self._recover_orphan(self._get_run(run_id))
                self._owner_cleanup_unknown = False
                task_error = None
            except Exception as caught:  # noqa: BLE001 - retain unconfirmed ownership
                error = caught
        if error is None:
            error = task_error
        if not self._worker.busy() and error is None:
            self._release_lease()
            self._clear_owner()
        elif self._worker.busy() and error is None:
            error = WorkflowRuntimeError(
                "WORKFLOW_CLEANUP_FAILED", "执行进程清理尚未确认"
            )
        if error is not None:
            raise error

    async def wait_idle(self) -> None:
        task = self._task
        if task is not None:
            await asyncio.shield(task)

    async def _execute(self, dispatched: CoreRun) -> None:
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
                lease = await self._resources.acquire(
                    dispatched.resource_request, dispatched.run_request_id
                )
                self._lease = lease
                current = self._get_run(dispatched.run_id)
                if (
                    current.status != "running"
                    or current.execution_generation != dispatched.execution_generation
                ):
                    lease.release()
                    self._lease = None
                    if current.status == "stopping":
                        self._transition_current(
                            current.run_id, current.execution_generation, "cancelled"
                        )
                    return
                budget = current.resource_request.get(
                    "automaticExecutionTimeoutSeconds", 0
                )
                timeout = asyncio.timeout(budget or None)
                try:
                    async with timeout:
                        outcome = await self._worker.run(
                            run_id=current.run_id,
                            execution_generation=current.execution_generation,
                            execution_plan=thaw_json(content.execution_plan),
                            parameters=thaw_json(current.parameters),
                            variables=self._variables(content, current),
                            browser=dict(lease.browser),
                            executable=lease.executable,
                            on_event=lambda event: self._commit_event(
                                current, content, event
                            ),
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
                        not self._worker.busy(),
                    )
            if self._worker.busy() or not outcome.cleanup_confirmed:
                raise RuntimeError("worker cleanup unconfirmed")
            lease.release()
            self._lease = None
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
            finishing = self._transition(current, "finishing")
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
        except Exception:
            current = self._get_run(dispatched.run_id)
            if current.execution_generation != dispatched.execution_generation:
                unhandled = True
                raise
            if current.terminal:
                return
            fenced = self._transition(current, "reconciling")
            try:
                if lease is None:
                    await self._recover_orphan(fenced)
                else:
                    await self._worker.force_stop(current.run_id)
            except Exception:  # noqa: BLE001 - retain lease while cleanup is unknown
                self._owner_cleanup_unknown = True
                unhandled = True
                return
            if self._worker.busy():
                return
            if lease is not None:
                lease.release()
                self._lease = None
            self._transition_current(
                fenced.run_id,
                fenced.execution_generation,
                "interrupted",
                error=UNKNOWN_RESULT_ERROR,
            )
        finally:
            async with self._lock:
                if self._task is asyncio.current_task():
                    if not cancelled and not unhandled:
                        self._task = None
                    if (
                        not cancelled
                        and not unhandled
                        and self._lease is None
                        and not self._worker.busy()
                    ):
                        self._run_id = None
            for listener in tuple(self._idle_listeners):
                listener()

    async def _commit_event(
        self, run: CoreRun, content: Any, event: dict[str, Any]
    ) -> None:
        current = self._get_run(run.run_id)
        if (
            current.execution_generation != run.execution_generation
            or current.status not in {"running", "finishing", "stopping"}
        ):
            raise WorkflowRuntimeError("EXECUTION_GENERATION_REVOKED", "执行代次已失效")
        node_id = event.get("nodeId")
        known = set(content.execution_plan.get("orderedNodeIds", ()))
        if node_id is not None and node_id not in known:
            raise WorkflowRuntimeError("RUN_EVENT_NODE_UNKNOWN", "事件引用了未知节点")
        value = dict(event)
        value.pop("sequence", None)
        try:
            with self._sessions() as session:
                SqlAlchemyWorkflowRuntimeRepository(session).append_event(value)
                session.commit()  # returning is the worker manager's ACK boundary
        except Exception:
            self._discard_uncommitted_artifact(run, event)
            raise

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
                committed = SqlAlchemyWorkflowRuntimeRepository(session).get_artifact(
                    run.run_id, artifact_id
                )
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
            session.commit()
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
            session.commit()
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

    def _release_lease(self) -> None:
        lease = self._lease
        if lease is not None:
            lease.release()
            self._lease = None

    def _clear_owner(self) -> None:
        self._task = None
        self._run_id = None
        self._owner_cleanup_unknown = False

    async def _task_cleanup_confirmed(self, task: asyncio.Task[None]) -> bool:
        results = await asyncio.gather(task, return_exceptions=True)
        confirmed = all(
            result is None or isinstance(result, asyncio.CancelledError)
            for result in results
        )
        if not confirmed:
            self._owner_cleanup_unknown = True
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
