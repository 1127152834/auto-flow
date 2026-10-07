"""Batch progress aggregation (remediation M5 5B-A4, B7).

Everything is read with a fixed number of aggregate queries (never per row or per task), so a 10,000
row batch costs the same handful of statements as a small one. Callers run it in a worker thread.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_automations.rules import processing_input
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.domain.project_runs.progress import (
    error_code,
    eta_seconds,
    mask_message,
    per_minute,
)
from autoflow.domain.workflows.runtime import TERMINAL_STATUSES
from autoflow.infrastructure.database.identity_models import IdentityRow
from autoflow.infrastructure.database.project_data_models import (
    DataRecordRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.project_runs import aware
from autoflow.infrastructure.database.record_ledger_models import (
    AutomationRecordLedgerRow as Ledger,
)
from autoflow.infrastructure.database.record_ledger_models import (
    ProjectBatchUnitRow as Unit,
)
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowRunEventRow,
    WorkflowRunRow,
)

from .presentation import prepared_node_names

RECENT_WINDOW_MINUTES = 5
MAX_RUNNING_TASKS = 50
SAMPLE_UNITS = 3
LEDGER_STATES = ("pending", "succeeded", "failed_retryable", "quarantined", "needs_review", "skipped")
_FAILED = Ledger.state.in_(("failed_retryable", "quarantined", "needs_review"))  # a skipped unit is a decision, not a failure


class BatchProgressService:
    def __init__(
        self, factory: sessionmaker[Session], clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._factory, self._clock = factory, clock

    def progress(self, project_id: str, batch_id: str) -> dict[str, Any]:
        now = self._clock()
        with self._factory() as session:
            batch = session.get(ProjectBatchRow, batch_id)
            if batch is None or batch.project_id != project_id:
                raise ProjectRunError("NOT_FOUND", "批次不存在", 404)
            ledger, tasks = _ledger(session, batch_id), _tasks(session, batch_id, now)
            # A unit stays "pending" in the ledger until its task ends, so running tasks are carved out of it.
            ledger["running"] = min(tasks["total"] - tasks["finished"], ledger["pending"])
            ledger["pending"] -= ledger["running"]
            return {
                "ledger": ledger,
                "throughput": _throughput(batch, tasks, now),
                "runningTasks": _running(session, batch, now),
                "failureGroups": _failures(session, batch_id),
                "updatedAt": now,
            }


def _ledger(session: Session, batch_id: str) -> dict[str, int]:
    counts = dict.fromkeys(LEDGER_STATES, 0)
    for state, count in session.execute(
        select(Ledger.state, func.count()).select_from(Unit).join(Ledger, Ledger.id == Unit.ledger_id)
        .where(Unit.batch_id == batch_id).group_by(Ledger.state)
    ):
        counts[state] = count
    return {"total": sum(counts.values()), "running": 0, **counts}


def _tasks(session: Session, batch_id: str, now: datetime) -> dict[str, int]:
    finished = WorkflowRunRow.status.in_(TERMINAL_STATUSES)
    since = now - timedelta(minutes=RECENT_WINDOW_MINUTES)
    total, done, recent = session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(case((finished, 1), else_=0)), 0),
            func.coalesce(func.sum(case((finished & (WorkflowRunRow.completed_at >= since), 1), else_=0)), 0),
        ).select_from(ProjectTaskRow).join(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
        .where(ProjectTaskRow.batch_id == batch_id)
    ).one()
    return {"total": total, "finished": int(done), "recent": int(recent)}


def _throughput(batch: ProjectBatchRow, tasks: dict[str, int], now: datetime) -> dict[str, Any]:
    active = batch.completed_at is None
    end = now if batch.completed_at is None else aware(batch.completed_at)
    elapsed = max((end - aware(batch.created_at)).total_seconds() / 60, 1.0)
    recent_rate = per_minute(tasks["recent"], min(float(RECENT_WINDOW_MINUTES), elapsed))
    average = per_minute(tasks["finished"], elapsed)
    target = (batch.frozen_request or {}).get("maxTasks")
    remaining = target - tasks["finished"] if isinstance(target, int) and active else None
    return {
        "windowMinutes": RECENT_WINDOW_MINUTES,
        "recentPerMinute": round(recent_rate, 2),
        "averagePerMinute": round(average, 2),
        "etaSeconds": eta_seconds(remaining=remaining, recent_per_minute=recent_rate, average_per_minute=average),
    }


def _running(session: Session, batch: ProjectBatchRow, now: datetime) -> list[dict[str, Any]]:
    rows = session.execute(
        select(ProjectTaskRow.id, ProjectTaskRow.run_id, WorkflowRunRow.started_at, WorkflowRunRow.resource_request,
               ProjectTaskInputSnapshotRow.inputs)
        .join(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
        .join(ProjectTaskInputSnapshotRow, ProjectTaskInputSnapshotRow.task_id == ProjectTaskRow.id)
        .where(ProjectTaskRow.batch_id == batch.id, WorkflowRunRow.status.not_in(TERMINAL_STATUSES))
        .order_by(WorkflowRunRow.started_at.is_(None), WorkflowRunRow.started_at, ProjectTaskRow.ordinal)
        .limit(MAX_RUNNING_TASKS)
    ).all()
    if not rows:
        return []
    last = (
        select(WorkflowRunEventRow.run_id, func.max(WorkflowRunEventRow.sequence).label("sequence"))
        .where(WorkflowRunEventRow.run_id.in_([row.run_id for row in rows]), WorkflowRunEventRow.kind == "nodeAttempt")
        .group_by(WorkflowRunEventRow.run_id).subquery()
    )
    nodes = dict(session.execute(
        select(WorkflowRunEventRow.run_id, WorkflowRunEventRow.node_id)
        .join(last, (last.c.run_id == WorkflowRunEventRow.run_id) & (last.c.sequence == WorkflowRunEventRow.sequence))
    ).tuples().all())
    names = prepared_node_names(
        SqlAlchemyWorkflowRuntimeRepository(session).get_prepared_content(prepared_content_id=batch.prepared_content_id)
    )
    identity_ids = {_identity_id(row.resource_request) for row in rows} - {None}
    identities = (
        dict(session.execute(select(IdentityRow.id, IdentityRow.name).where(IdentityRow.id.in_(identity_ids))).tuples().all())
        if identity_ids else {}
    )
    primary = processing_input(((batch.frozen_request or {}).get("automation") or {}).get("inputPlan") or {})
    displays = _display_names(session, batch.project_id, [_primary_ref(row.inputs, primary) for row in rows])
    result = []
    for row, display in zip(rows, displays, strict=True):
        started = aware(row.started_at) if row.started_at else None
        node = nodes.get(row.run_id)
        result.append({
            "taskId": row.id,
            "displayName": display,
            "identityName": identities.get(_identity_id(row.resource_request) or ""),
            "currentNodeName": names.get(node, "未命名节点") if node else None,
            "startedAt": started,
            "elapsedSeconds": max(0, int((now - started).total_seconds())) if started else None,
        })
    return result


def _identity_id(resource_request: Any) -> str | None:
    identity = resource_request.get("identity") if isinstance(resource_request, dict) else None
    value = identity.get("identityId") if isinstance(identity, dict) else None
    return value if isinstance(value, str) else None


def _primary_ref(inputs: Any, primary: Any) -> dict[str, Any] | None:
    chosen = next((item for item in inputs or [] if isinstance(item, dict) and item.get("inputId") == primary), None)
    ref = chosen.get("recordRef") if chosen else None
    return ref if isinstance(ref, dict) and isinstance(ref.get("recordKey"), dict) else None


def _display_names(session: Session, project_id: str, refs: list[dict[str, Any] | None]) -> list[str | None]:
    """The row's main display field value (the table's identity field); never the internal key."""
    wanted: dict[tuple[str, str], set[str]] = defaultdict(set)
    for ref in refs:
        if ref is not None:
            wanted[(ref["tableId"], ref["datasetGeneration"])].add(str(ref["recordKey"]["value"]))
    found: dict[tuple[str, str, str, str], str | None] = {}
    for (table_id, generation), keys in wanted.items():
        table = session.get(DataTableRow, table_id)
        field_id = table.identity.get("fieldId") if table is not None and table.identity.get("mode") == "field" else None
        if table is None or table.project_id != project_id or field_id is None:
            continue
        for key_type, key_value, values in session.execute(
            select(DataRecordRow.key_type, DataRecordRow.key_value, DataRecordRow.values_json).where(
                DataRecordRow.project_id == project_id, DataRecordRow.table_id == table_id,
                DataRecordRow.dataset_generation == generation, DataRecordRow.key_value.in_(keys),
            )
        ):
            value = (values or {}).get(field_id)
            found[(table_id, generation, key_type, key_value)] = None if value is None or value == "" else str(value)
    return [
        found.get((ref["tableId"], ref["datasetGeneration"], ref["recordKey"]["type"], str(ref["recordKey"]["value"])))
        if ref is not None else None
        for ref in refs
    ]


def _failures(session: Session, batch_id: str) -> list[dict[str, Any]]:
    """Failed units grouped by stable code, in one pass: window functions give each raw group's size and its first 3 units."""
    code = func.json_extract(Ledger.last_error, "$.code")
    partition = (Ledger.last_outcome, code)
    ranked = (
        select(
            Ledger.id.label("unit_id"), Ledger.last_outcome.label("outcome"), code.label("code"),
            Ledger.last_error.label("error"),
            func.row_number().over(partition_by=partition, order_by=Ledger.id).label("rank"),
            func.count().over(partition_by=partition).label("size"),
        ).select_from(Unit).join(Ledger, Ledger.id == Unit.ledger_id).where(Unit.batch_id == batch_id, _FAILED)
    ).subquery()
    groups: dict[str, dict[str, Any]] = {}
    for unit_id, outcome, raw, error, rank, size in session.execute(
        select(ranked.c.unit_id, ranked.c.outcome, ranked.c.code, ranked.c.error, ranked.c.rank, ranked.c.size)
        .where(ranked.c.rank <= SAMPLE_UNITS).order_by(ranked.c.unit_id)
    ):
        key = error_code(outcome, {"code": raw})
        group = groups.setdefault(key, {"errorCode": key, "count": 0, "sampleMessage": None, "sampleUnitIds": []})
        if rank == 1:
            group["count"] += size
        if len(group["sampleUnitIds"]) < SAMPLE_UNITS:
            group["sampleUnitIds"].append(unit_id)
            message = error.get("message") if isinstance(error, dict) else None
            if group["sampleMessage"] is None and isinstance(message, str) and message.strip():
                group["sampleMessage"] = mask_message(message)
    return sorted(groups.values(), key=lambda group: (-group["count"], group["errorCode"]))
