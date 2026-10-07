"""Remediation M5 5B-A4: stable failure codes, throughput/ETA and input-match counting rules."""

import pytest

from autoflow.domain.project_runs.input_match import sample_row, unprocessed_count
from autoflow.domain.project_runs.progress import (
    ERROR_CODES,
    error_code,
    eta_seconds,
    mask_message,
    per_minute,
)


@pytest.mark.parametrize(
    ("outcome", "error", "expected"),
    [
        ("page", {"code": "WORKFLOW_NODE_FAILED"}, "page_error"),
        ("infrastructure", None, "environment_error"),
        ("business", {"code": "END_BUSINESS_FAILED"}, "business_failed"),
        ("unknown", {"code": "X"}, "outcome_unknown"),
        ("cancelled", None, "cancelled"),
        ("page", {"code": "INPUT_VALUE_INVALID"}, "input_invalid"),
        (None, None, "unknown"),
        ("surprise", {"code": 7}, "unknown"),
    ],
)
def test_error_code_is_a_closed_set(outcome, error, expected):
    assert error_code(outcome, error) == expected
    assert error_code(outcome, error) in ERROR_CODES


def test_mask_message_hides_credentials_ids_and_contact_data():
    text = (
        "Input field 0b5a2c1e-1111-4222-8333-444455556666 failed {\"password\":\"hunter2\"} "
        "for a@b.com url https://u:secret@host/x"
    )
    masked = mask_message(text)
    for leaked in ("hunter2", "secret", "a@b.com", "0b5a2c1e"):
        assert leaked not in masked
    plain = mask_message("登录失败 password=abc123, 密码：xyz789 token: t0k")
    for leaked in ("abc123", "xyz789", "t0k"):
        assert leaked not in plain
    assert len(mask_message("x" * 500)) <= 200


def test_rates_and_eta():
    assert per_minute(10, 5) == 2
    assert per_minute(3, 0) == 0
    assert eta_seconds(remaining=10, recent_per_minute=2, average_per_minute=1) == 300
    assert eta_seconds(remaining=10, recent_per_minute=0, average_per_minute=1) == 600
    assert eta_seconds(remaining=10, recent_per_minute=0, average_per_minute=0) is None
    assert eta_seconds(remaining=None, recent_per_minute=2, average_per_minute=2) is None
    assert eta_seconds(remaining=0, recent_per_minute=2, average_per_minute=2) is None


def test_unprocessed_excludes_succeeded_and_occupied_matches_only():
    matched = [("text", "a"), ("text", "b"), ("text", "c"), ("text", "d")]
    done = {("text", "a"), ("text", "zzz")}
    busy = {("text", "b")}
    assert unprocessed_count(matched, done, busy) == 2
    assert unprocessed_count([], done, busy) == 0


def test_sample_row_uses_bound_fields_only_and_masks_sensitive_ones():
    bindings = [
        {"inputFieldAlias": "账号", "fieldRef": {"fieldId": "f1"}},
        {"inputFieldAlias": "密码", "fieldRef": {"fieldId": "f2"}, "signatureField": "pwd"},
    ]
    values = {"f1": "alice", "f2": "p@ss", "f3": "不应出现"}
    assert sample_row(bindings, values, sensitive_fields={"pwd"}) == {"账号": "alice", "密码": "已隐藏"}
    assert sample_row(bindings, {}, sensitive_fields=set()) == {"账号": None, "密码": None}
