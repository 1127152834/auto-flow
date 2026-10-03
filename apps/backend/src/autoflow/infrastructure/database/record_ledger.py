"""Record processing ledger persistence (remediation M2 Task 1).

Only complete :class:`LedgerScope` values are accepted; there is no lookup by a
bare record key. State transitions live in ``domain.project_runs.ledger``; this
module persists them with a compare-and-set on ``revision``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from autoflow.domain.project_automations.rules import AMBIGUOUS, processing_input
from autoflow.domain.project_runs.ledger import (
    LedgerEntry,
    LedgerError,
    LedgerScope,
    TaskOutcome,
    new_entry,
    next_ledger_entry,
    quarantine_entry,
    reset_entry,
    resolve_entry,
    skip_entry,
)

from .project_automation_models import ProjectAutomationRow
from .record_ledger_models import AutomationRecordLedgerRow, ProjectBatchUnitRow

MAX_PAGE = 200


@dataclass(frozen=True)
class StoredLedgerEntry:
    id: str
    entry: LedgerEntry


class SqlAlchemyRecordLedger:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, scope: LedgerScope) -> LedgerEntry | None:
        row = self._row(scope)
        return None if row is None else ledger_entry(row)

    def by_id(self, automation_id: str, unit_id: str) -> StoredLedgerEntry | None:
        row = self.session.get(AutomationRecordLedgerRow, unit_id)
        if row is None or row.automation_id != automation_id:
            return None
        return StoredLedgerEntry(row.id, ledger_entry(row))

    def ensure(self, scope: LedgerScope, now: datetime) -> LedgerEntry:
        row = self._row(scope)
        if row is None:
            fresh = new_entry(scope)
            row = AutomationRecordLedgerRow(
                id=str(uuid4()), **_scope_columns(scope), **_state_columns(fresh),
                created_at=now, updated_at=now,
            )
            self.session.add(row)
            self.session.flush()
        return ledger_entry(row)

    def list(
        self,
        automation_id: str,
        *,
        state: str | None = None,
        after: str | None = None,
        limit: int = 50,
    ) -> list[StoredLedgerEntry]:
        query = select(AutomationRecordLedgerRow).where(
            AutomationRecordLedgerRow.automation_id == automation_id
        )
        if state is not None:
            query = query.where(AutomationRecordLedgerRow.state == state)
        if after is not None:
            query = query.where(AutomationRecordLedgerRow.id > after)
        rows = self.session.scalars(
            query.order_by(AutomationRecordLedgerRow.id).limit(max(1, min(limit, MAX_PAGE)))
        )
        return [StoredLedgerEntry(row.id, ledger_entry(row)) for row in rows]

    def reset(self, scope: LedgerScope, *, expected_revision: int, reason: str, now: datetime) -> LedgerEntry:
        current = self._required(scope)
        return self._save(current, reset_entry(current, expected_revision=expected_revision, reason=reason, now=now), now)

    def skip(self, scope: LedgerScope, *, expected_revision: int, reason: str, now: datetime) -> LedgerEntry:
        current = self._required(scope)
        return self._save(current, skip_entry(current, expected_revision=expected_revision, reason=reason, now=now), now)

    def resolve(
        self, scope: LedgerScope, *, expected_revision: int, decision: str, reason: str, now: datetime
    ) -> LedgerEntry:
        current = self._required(scope)
        after = resolve_entry(current, expected_revision=expected_revision, decision=decision, reason=reason, now=now)
        return self._save(current, after, now)

    def project(
        self,
        scope: LedgerScope,
        outcome: TaskOutcome,
        *,
        budget: int,
        backoff: tuple[int, ...],
        now: datetime,
    ) -> LedgerEntry:
        """Apply one Task terminal to its unit (remediation M2 Task 3)."""
        current = self.ensure(scope, now)
        after = next_ledger_entry(current, outcome, budget=budget, backoff=backoff, now=now)
        return current if after == current else self._save(current, after, now)

    def quarantine(self, scope: LedgerScope, error: dict[str, Any], now: datetime) -> LedgerEntry:
        current = self.ensure(scope, now)
        after = quarantine_entry(current, error, now)
        return current if after == current else self._save(current, after, now)

    def add_batch_unit(self, batch_id: str, scope: LedgerScope, task_id: str, now: datetime) -> None:
        """Record that a batch took in this primary unit; repeated attempts add nothing."""
        row = self._row(scope)
        if row is None:
            raise LedgerError("LEDGER_NOT_FOUND", "处理记录不存在", 404)
        exists = self.session.scalar(
            select(ProjectBatchUnitRow.id).where(
                ProjectBatchUnitRow.batch_id == batch_id, ProjectBatchUnitRow.ledger_id == row.id
            )
        )
        if exists is None:
            self.session.add(ProjectBatchUnitRow(
                id=str(uuid4()), batch_id=batch_id, ledger_id=row.id, first_task_id=task_id, created_at=now,
            ))
            self.session.flush()

    def _required(self, scope: LedgerScope) -> LedgerEntry:
        entry = self.get(scope)
        if entry is None:
            raise LedgerError("LEDGER_NOT_FOUND", "处理记录不存在", 404)
        return entry

    def _save(self, before: LedgerEntry, after: LedgerEntry, now: datetime) -> LedgerEntry:
        result = self.session.execute(
            update(AutomationRecordLedgerRow)
            .where(
                *_scope_filter(before.scope),
                AutomationRecordLedgerRow.revision == before.revision,
            )
            .values(**_state_columns(after), updated_at=now)
            .execution_options(synchronize_session="fetch")
        )
        if getattr(result, "rowcount", 0) != 1:
            raise LedgerError("LEDGER_REVISION_CONFLICT", "这条数据已被更新，请刷新后再试")
        return after

    def _row(self, scope: LedgerScope) -> AutomationRecordLedgerRow | None:
        return self.session.scalar(select(AutomationRecordLedgerRow).where(*_scope_filter(scope)))


def processing_input_report(session: Session) -> list[dict[str, Any]]:
    """Automations whose primary processing input must be chosen before a new batch starts."""
    report = []
    for row in session.scalars(select(ProjectAutomationRow).order_by(ProjectAutomationRow.id)):
        plan = row.input_plan if isinstance(row.input_plan, dict) else {}
        if processing_input(plan) is AMBIGUOUS:
            report.append({
                "automationId": row.id,
                "projectId": row.project_id,
                "requiredInputIds": [
                    item.get("inputId") for item in plan.get("inputs", []) if item.get("required") is True
                ],
            })
    return report


def _scope_columns(scope: LedgerScope) -> dict[str, str]:
    return {
        "automation_id": scope.automation_id,
        "processing_input_id": scope.processing_input_id,
        "project_id": scope.project_id,
        "table_id": scope.table_id,
        "dataset_generation": scope.dataset_generation,
        "key_type": scope.key_type,
        "key_value": scope.key_value,
        "identity_namespace": scope.identity_namespace,
    }


def _scope_filter(scope: LedgerScope) -> list[Any]:
    return [getattr(AutomationRecordLedgerRow, name) == value for name, value in _scope_columns(scope).items()]


def _state_columns(entry: LedgerEntry) -> dict[str, Any]:
    return {
        "state": entry.state,
        "attempts": entry.attempts,
        "processing_cycle": entry.processing_cycle,
        "cycle_attempts": entry.cycle_attempts,
        "last_outcome": entry.last_outcome,
        "last_error": entry.last_error,
        "last_task_id": entry.last_task_id,
        "last_at": entry.last_at,
        "next_eligible_at": entry.next_eligible_at,
        "revision": entry.revision,
        "review": entry.review,
    }


def ledger_entry(row: AutomationRecordLedgerRow) -> LedgerEntry:
    return LedgerEntry(
        scope=LedgerScope(
            row.automation_id, row.processing_input_id, row.project_id, row.table_id,
            row.dataset_generation, row.key_type, row.key_value, row.identity_namespace,
        ),
        state=row.state,  # type: ignore[arg-type]
        attempts=row.attempts,
        processing_cycle=row.processing_cycle,
        cycle_attempts=row.cycle_attempts,
        last_outcome=row.last_outcome,
        last_error=row.last_error,
        last_task_id=row.last_task_id,
        last_at=_aware(row.last_at),
        next_eligible_at=_aware(row.next_eligible_at),
        revision=row.revision,
        review=row.review,
    )


def _aware(value: datetime | None) -> datetime | None:
    # SQLite drops the offset; ledger times are always written in UTC.
    from datetime import UTC

    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value
