"""Remediation M2 R2-08: the unified node error policy and old-setting candidates."""

import json
from pathlib import Path

import pytest

from autoflow.domain.workflows.error_policy import (
    active_policy,
    candidate_policy,
    retry_delay,
)

CASES = json.loads((Path(__file__).parents[1] / "fixtures" / "error_policy_candidates.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_old_settings_convert_to_the_same_candidate_as_the_editor(case):
    assert candidate_policy(case["config"]) == case["candidate"]


def test_only_an_explicit_new_policy_takes_effect():
    for case in CASES:
        if case["candidate"] is not None:
            assert active_policy(case["config"]) is None, case["name"]
    enabled = CASES[-1]["config"]
    assert active_policy(enabled).on_error == "retry"


@pytest.mark.parametrize(
    "policy",
    [
        {"version": 2, "onError": "explode"},
        {"version": 2, "onError": "retry", "maxRetries": 99},
        {"version": 2, "onError": "goto", "gotoNodeId": ""},
        {"version": 3, "onError": "stop"},
    ],
)
def test_invalid_new_policies_are_ignored_not_guessed(policy):
    assert active_policy({"errorPolicy": policy}) is None


def test_backoff_is_fixed_or_exponential_and_capped():
    fixed = active_policy({"errorPolicy": {"version": 2, "onError": "retry", "maxRetries": 3, "backoff": {"kind": "fixed", "initialSeconds": 2, "maxSeconds": 2, "jitter": False}}})
    assert [retry_delay(fixed, attempt) for attempt in (1, 2, 3)] == [2, 2, 2]
    growing = active_policy({"errorPolicy": {"version": 2, "onError": "retry", "maxRetries": 4, "backoff": {"kind": "exponential", "initialSeconds": 1, "maxSeconds": 5, "jitter": False}}})
    assert [retry_delay(growing, attempt) for attempt in (1, 2, 3, 4)] == [1, 2, 4, 5]
