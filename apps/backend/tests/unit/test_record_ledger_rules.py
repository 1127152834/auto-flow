"""Remediation M2 R2-01/R2-06: ledger scope identity and manual transitions."""

from datetime import UTC, datetime

import pytest

from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.project_runs.ledger import (
    LedgerEntry,
    LedgerError,
    reset_entry,
    resolve_entry,
    scope_for,
    skip_entry,
)

NOW = datetime(2026, 10, 2, tzinfo=UTC)


def ref(key_type="text", value="A-1", generation="g1"):
    return RecordRef("p", "t", generation, RecordKey(key_type, value))


def entry(state, **changes):
    values = {
        "scope": scope_for("auto", "input", ref(), None),
        "state": state,
        "attempts": 2,
        "processing_cycle": 1,
        "cycle_attempts": 2,
        "last_outcome": "failed",
        "last_error": {"code": "X", "message": "m"},
        "last_task_id": "task-1",
        "last_at": NOW,
        "next_eligible_at": None,
        "revision": 4,
        "review": None,
    }
    values.update(changes)
    return LedgerEntry(**values)


def test_scope_keeps_key_type_generation_and_namespace_distinct():
    text_one = scope_for("auto", "input", ref("text", "1"), None)
    integer_one = scope_for("auto", "input", ref("integer", "1"), None)
    regenerated = scope_for("auto", "input", ref("text", "1", "g2"), None)
    rebound = scope_for("auto", "input", ref("text", "1"), "ns-2")
    assert len({text_one, integer_one, regenerated, rebound}) == 4
    assert text_one.identity_namespace == ""
    assert rebound.identity_namespace == "ns-2"


def test_scope_rejects_a_blank_processing_input():
    with pytest.raises(LedgerError):
        scope_for("auto", "", ref(), None)


@pytest.mark.parametrize("state", ["failed_retryable", "quarantined", "skipped", "succeeded"])
def test_reset_starts_a_new_audited_cycle(state):
    current = entry(state)
    after = reset_entry(current, expected_revision=4, reason="人工重试", now=NOW)
    assert after.state == "pending"
    assert after.processing_cycle == 2 and after.cycle_attempts == 0
    assert after.attempts == 2  # 累计尝试保留
    assert after.revision == 5
    assert after.review == {"action": "reset", "reason": "人工重试", "at": NOW.isoformat(), "fromState": state}


def test_skip_records_the_reason():
    after = skip_entry(entry("pending"), expected_revision=4, reason="不需要处理", now=NOW)
    assert after.state == "skipped" and after.revision == 5
    assert after.review["action"] == "skip"


@pytest.mark.parametrize("command", [reset_entry, skip_entry])
def test_needs_review_cannot_be_reset_or_skipped(command):
    with pytest.raises(LedgerError) as raised:
        command(entry("needs_review"), expected_revision=4, reason="x", now=NOW)
    assert raised.value.code == "LEDGER_NEEDS_REVIEW"


def test_stale_revision_is_rejected():
    with pytest.raises(LedgerError) as raised:
        reset_entry(entry("failed_retryable"), expected_revision=3, reason="x", now=NOW)
    assert raised.value.code == "LEDGER_REVISION_CONFLICT"


@pytest.mark.parametrize(
    ("decision", "state"),
    [("confirmedSucceeded", "succeeded"), ("confirmedNotPerformed", "pending"), ("abandon", "skipped")],
)
def test_resolve_keeps_the_original_unknown_fact(decision, state):
    unknown = {"taskId": "task-1", "code": "WORKFLOW_RESULT_UNKNOWN"}
    current = entry("needs_review", review={"unknown": unknown})
    after = resolve_entry(current, expected_revision=4, decision=decision, reason="核实过", now=NOW)
    assert after.state == state
    assert after.review["unknown"] == unknown
    assert after.review["decision"] == decision and after.review["reason"] == "核实过"
    assert after.revision == 5


def test_resolve_only_applies_to_needs_review():
    with pytest.raises(LedgerError) as raised:
        resolve_entry(entry("pending"), expected_revision=4, decision="abandon", reason="x", now=NOW)
    assert raised.value.code == "LEDGER_NOT_IN_REVIEW"


def test_resolve_requires_a_known_decision_and_reason():
    current = entry("needs_review", review={"unknown": {}})
    with pytest.raises(LedgerError):
        resolve_entry(current, expected_revision=4, decision="retry", reason="x", now=NOW)
    with pytest.raises(LedgerError):
        resolve_entry(current, expected_revision=4, decision="abandon", reason="  ", now=NOW)


# Remediation M2 R2-02/R2-04/R2-14: terminal outcome projection.
from datetime import timedelta

from autoflow.domain.project_runs.ledger import (
    TaskOutcome,
    next_ledger_entry,
)

BACKOFF = (60, 300, 1800)


def outcome(kind, task="task-9"):
    return TaskOutcome(kind=kind, task_id=task, run_id="run-9", error={"code": "E", "message": "m"})


def fresh(**changes):
    return entry("pending", attempts=0, cycle_attempts=0, last_error=None, last_outcome=None, last_task_id=None,
                 last_at=None, revision=1, **changes)


def project(current, kind, budget=3):
    return next_ledger_entry(current, outcome(kind), budget=budget, backoff=BACKOFF, now=NOW)


def test_success_counts_the_attempt_and_waits_before_cycle_reuse():
    after = project(fresh(), "succeeded")
    assert (after.state, after.attempts, after.cycle_attempts, after.revision) == ("succeeded", 1, 1, 2)
    assert after.next_eligible_at == NOW + timedelta(seconds=60)
    assert after.last_task_id == "task-9" and after.last_outcome == "succeeded" and after.last_error is None


def test_page_failures_back_off_then_quarantine_within_the_cycle_budget():
    first = project(fresh(), "page")
    assert first.state == "failed_retryable" and first.next_eligible_at == NOW + timedelta(seconds=60)
    second = project(first, "page")
    assert second.state == "failed_retryable" and second.next_eligible_at == NOW + timedelta(seconds=300)
    third = project(second, "page")
    assert third.state == "quarantined" and third.next_eligible_at is None
    assert third.attempts == 3 and third.cycle_attempts == 3


def test_infrastructure_and_cancel_keep_eligibility_and_do_not_spend_budget():
    for kind in ("infrastructure", "cancelled"):
        after = project(fresh(), kind)
        assert after.state == "pending" and after.attempts == 0 and after.cycle_attempts == 0
        assert after.last_outcome == kind and after.revision == 2


def test_unknown_needs_review_and_keeps_the_fact():
    after = project(fresh(), "unknown")
    assert after.state == "needs_review" and after.attempts == 1
    assert after.review["unknown"] == {"taskId": "task-9", "runId": "run-9", "code": "E"}


def test_business_failure_is_skipped_without_technical_budget():
    after = project(fresh(), "business")
    assert after.state == "skipped" and after.last_outcome == "business" and after.cycle_attempts == 1


def test_succeeded_unit_starts_a_new_cycle_on_its_next_attempt():
    done = project(fresh(), "succeeded")
    again = project(done, "page")
    assert again.processing_cycle == 2 and again.cycle_attempts == 1 and again.attempts == 2


def test_a_needs_review_entry_is_never_overwritten_by_a_late_projection():
    review = project(fresh(), "unknown")
    assert project(review, "succeeded") == review
