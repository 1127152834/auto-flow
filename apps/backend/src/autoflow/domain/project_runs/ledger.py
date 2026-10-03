"""Record processing ledger rules (remediation M2 R2-01/R2-06).

A ledger entry tracks one primary processing unit of a data automation: the
automation, its processing input, and the complete record identity. Content
revisions are not part of the scope, so editing a row does not clear its state;
a new dataset generation or Sheets namespace is a new scope.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Literal

from autoflow.domain.project_runs.input_selection import RecordRef

LedgerState = Literal[
    "pending", "succeeded", "failed_retryable", "quarantined", "needs_review", "skipped"
]
ReviewDecision = Literal["confirmedSucceeded", "confirmedNotPerformed", "abandon"]
LEDGER_STATES: frozenset[str] = frozenset(
    {"pending", "succeeded", "failed_retryable", "quarantined", "needs_review", "skipped"}
)
_RESOLVED_STATE: dict[str, LedgerState] = {
    "confirmedSucceeded": "succeeded",
    "confirmedNotPerformed": "pending",
    "abandon": "skipped",
}
MAX_REASON_CHARS = 500


class LedgerError(Exception):
    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class LedgerScope:
    automation_id: str
    processing_input_id: str
    project_id: str
    table_id: str
    dataset_generation: str
    key_type: str
    key_value: str
    # Empty for local tables so the unique scope also holds without a namespace.
    identity_namespace: str


@dataclass(frozen=True)
class LedgerEntry:
    scope: LedgerScope
    state: LedgerState
    attempts: int
    processing_cycle: int
    cycle_attempts: int
    last_outcome: str | None
    last_error: dict[str, Any] | None
    last_task_id: str | None
    last_at: datetime | None
    next_eligible_at: datetime | None
    revision: int
    review: dict[str, Any] | None


def scope_for(
    automation_id: str,
    processing_input_id: str,
    record_ref: RecordRef,
    identity_namespace: str | None,
) -> LedgerScope:
    if not automation_id or not processing_input_id:
        raise LedgerError("LEDGER_SCOPE_INVALID", "处理单位不完整", 422)
    return LedgerScope(
        automation_id,
        processing_input_id,
        record_ref.project_id,
        record_ref.table_id,
        record_ref.dataset_generation,
        record_ref.record_key.type,
        record_ref.record_key.value,
        identity_namespace or "",
    )


def new_entry(scope: LedgerScope) -> LedgerEntry:
    return LedgerEntry(scope, "pending", 0, 1, 0, None, None, None, None, None, 1, None)


def reset_entry(
    entry: LedgerEntry, *, expected_revision: int, reason: str, now: datetime
) -> LedgerEntry:
    """An explicit, audited new processing cycle; unknown outcomes must be resolved instead."""
    _check(entry, expected_revision)
    if entry.state == "needs_review":
        raise LedgerError("LEDGER_NEEDS_REVIEW", "这条数据的上次结果需要先核实")
    return replace(
        entry,
        state="pending",
        processing_cycle=entry.processing_cycle + 1,
        cycle_attempts=0,
        next_eligible_at=None,
        revision=entry.revision + 1,
        review=_audit("reset", reason, now, entry.state),
    )


def skip_entry(
    entry: LedgerEntry, *, expected_revision: int, reason: str, now: datetime
) -> LedgerEntry:
    _check(entry, expected_revision)
    if entry.state == "needs_review":
        raise LedgerError("LEDGER_NEEDS_REVIEW", "这条数据的上次结果需要先核实")
    return replace(
        entry,
        state="skipped",
        next_eligible_at=None,
        revision=entry.revision + 1,
        review=_audit("skip", reason, now, entry.state),
    )


def resolve_entry(
    entry: LedgerEntry,
    *,
    expected_revision: int,
    decision: str,
    reason: str,
    now: datetime,
) -> LedgerEntry:
    """A person's verified decision about an unknown outcome; the original fact is kept."""
    _check(entry, expected_revision)
    if entry.state != "needs_review":
        raise LedgerError("LEDGER_NOT_IN_REVIEW", "这条数据不需要核实")
    if decision not in _RESOLVED_STATE:
        raise LedgerError("LEDGER_DECISION_INVALID", "核实结论无效", 422)
    review = dict(entry.review or {})
    review.update(_audit("resolve", reason, now, entry.state))
    review["decision"] = decision
    return replace(
        entry,
        state=_RESOLVED_STATE[decision],
        next_eligible_at=None,
        revision=entry.revision + 1,
        review=review,
    )


def _check(entry: LedgerEntry, expected_revision: int) -> None:
    if entry.revision != expected_revision:
        raise LedgerError("LEDGER_REVISION_CONFLICT", "这条数据已被更新，请刷新后再试")


def _audit(action: str, reason: str, now: datetime, from_state: str) -> dict[str, Any]:
    text = reason.strip() if isinstance(reason, str) else ""
    if not text or len(text) > MAX_REASON_CHARS:
        raise LedgerError("LEDGER_REASON_REQUIRED", "请填写原因（不超过 500 字）", 422)
    return {"action": action, "reason": text, "at": now.isoformat(), "fromState": from_state}
