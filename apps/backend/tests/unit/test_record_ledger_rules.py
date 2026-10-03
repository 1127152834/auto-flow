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
