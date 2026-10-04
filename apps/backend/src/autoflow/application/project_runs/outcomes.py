"""Task terminal outcomes for the record ledger (remediation M2 Task 3).

The outcome is read from durable facts only: the run's terminal status, every
acknowledged node-start fact (R2-13) and the End business result (R2-14). A
technical failure is never hidden by a business result from another branch.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from autoflow.domain.project_automations.rules import processing_input
from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_runs.circuit_breaker import FinishedTask, needs_older
from autoflow.domain.project_runs.failure_category import AttemptFact, classify
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.project_runs.ledger import (
    DEFAULT_BACKOFF_SECONDS,
    DEFAULT_RETRY_BUDGET,
    TaskOutcome,
    scope_for,
)
from autoflow.domain.workflows.runtime import TERMINAL_STATUSES
from autoflow.infrastructure.database.environment_models import ProjectEndOperationRow
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectRecordLeaseRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.record_ledger import SqlAlchemyRecordLedger
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowRunEventRow,
    WorkflowRunRow,
)


def run_failure_category(session: Session, run_id: str, status: str) -> str | None:
    if status not in TERMINAL_STATUSES:
        return None
    rows = session.execute(
        select(WorkflowRunEventRow.node_visit_id, WorkflowRunEventRow.payload)
        .where(WorkflowRunEventRow.run_id == run_id, WorkflowRunEventRow.kind == "nodeAttempt")
        .order_by(WorkflowRunEventRow.sequence)
    ).all()
    facts = [
        AttemptFact(str(visit), str(payload.get("status")), payload.get("sideEffect"))
        for visit, payload in rows
        if isinstance(payload, dict) and visit is not None
    ]
    return classify(status, None, facts)


def task_outcome(session: Session, task: ProjectTaskRow, run: WorkflowRunRow) -> TaskOutcome:
    error = run.error if isinstance(run.error, dict) else None
    if run.status == "succeeded":
        end = session.scalar(
            select(ProjectEndOperationRow)
            .where(ProjectEndOperationRow.task_id == task.id)
            .order_by(ProjectEndOperationRow.created_at)
            .limit(1)
        )
        failed = end is not None and (end.intended_result or {}).get("businessResult") == "failed"
        return TaskOutcome("business" if failed else "succeeded", task.id, run.id, error)
    category = run_failure_category(session, run.id, run.status) or "unknown"
    return TaskOutcome(category, task.id, run.id, error)  # type: ignore[arg-type]


def project_released_leases(
    session: Session, leases: Iterable[ProjectRecordLeaseRow], now: datetime
) -> None:
    """Project each Task whose primary input lease is being released, in the same transaction.

    A lease moves from held to released exactly once, so the projection cannot
    repeat; until then the record cannot be claimed again.
    """
    by_task: dict[str, set[str]] = {}
    for lease in leases:
        by_task.setdefault(lease.task_id, set()).add(lease.id)
    ledger = SqlAlchemyRecordLedger(session)
    for task_id, lease_ids in by_task.items():
        task = session.get(ProjectTaskRow, task_id)
        batch = session.get(ProjectBatchRow, task.batch_id) if task else None
        run = session.get(WorkflowRunRow, task.run_id) if task else None
        snapshot = session.scalar(
            select(ProjectTaskInputSnapshotRow).where(ProjectTaskInputSnapshotRow.task_id == task_id)
        )
        if task is None or batch is None or run is None or snapshot is None:
            continue
        if (batch.frozen_request or {}).get("executionMode") == "previewWrites":
            continue  # R2-30: preview outcomes never reach processing records
        automation = (batch.frozen_request or {}).get("automation") or {}
        chosen = processing_input(automation.get("inputPlan") or {})
        selected = next(
            (item for item in snapshot.inputs or [] if isinstance(item, dict) and item.get("inputId") == chosen),
            None,
        )
        if not isinstance(chosen, str) or selected is None or selected.get("leaseId") not in lease_ids:
            continue
        primary = session.get(ProjectRecordLeaseRow, selected["leaseId"])
        ref = _record_ref(selected.get("recordRef"))
        if primary is None or ref is None:
            continue
        policy = automation.get("runPolicy") or {}
        scope = scope_for(batch.automation_id, chosen, ref, _namespace(primary.lease_key))
        ledger.project(
            scope,
            task_outcome(session, task, run),
            budget=int(policy.get("retryBudget", DEFAULT_RETRY_BUDGET)),
            backoff=tuple(policy.get("retryBackoffSeconds", DEFAULT_BACKOFF_SECONDS)),
            now=now,
        )
        ledger.add_batch_unit(batch.id, scope, task.id, now)


def _record_ref(value: Any) -> RecordRef | None:
    if not isinstance(value, dict) or not isinstance(value.get("recordKey"), dict):
        return None
    key = value["recordKey"]
    return RecordRef(
        str(value["projectId"]), str(value["tableId"]), str(value["datasetGeneration"]),
        RecordKey(key["type"], str(key["value"])),
    )


def _namespace(lease_key: str) -> str | None:
    try:
        value = json.loads(lease_key)
    except (TypeError, ValueError):
        return None
    namespace = value.get("identityNamespace") if value.get("source") == "sheets" else None
    return namespace if isinstance(namespace, str) else None


def last_resume(session: Session, project_id: str, batch_id: str) -> datetime | None:
    """When a person last resumed the batch; the breaker only judges what happened after it."""
    rows = session.scalars(
        select(ProjectOperationRow).where(
            ProjectOperationRow.project_id == project_id,
            ProjectOperationRow.kind == "resumeBatch",
            ProjectOperationRow.status == "succeeded",
        )
    )
    times = [row.created_at for row in rows if (row.resource or {}).get("batchId") == batch_id]
    return max((_aware(value) for value in times), default=None)


def batch_history(session: Session, batch_id: str, since: datetime | None) -> list[FinishedTask]:
    rows = session.execute(
        select(ProjectTaskRow, WorkflowRunRow)
        .join(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
        .where(ProjectTaskRow.batch_id == batch_id, WorkflowRunRow.status.in_(TERMINAL_STATUSES))
        .order_by(WorkflowRunRow.completed_at, WorkflowRunRow.id)
    ).all()
    # Newest first, and only as far back as the breaker can still see (M3: this ran over the
    # whole batch on every tick); the returned tail is oldest first like the full history.
    newest_first: list[FinishedTask] = []
    for task, run in reversed(rows):
        if since is not None and run.completed_at is not None and _aware(run.completed_at) <= since:
            continue
        outcome = task_outcome(session, task, run)
        code = (outcome.error or {}).get("code") if outcome.error else None
        newest_first.append(FinishedTask(task.id, outcome.kind, code if isinstance(code, str) else None))
        if not needs_older(newest_first):
            break
    return newest_first[::-1]


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
