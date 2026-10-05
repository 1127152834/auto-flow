"""Remediation M4 S6 (R4-05; AC4-04): the exit region must match the identity before a browser starts."""

import pytest

from autoflow.domain.identities.region import check_exit, may_start

SHANGHAI = {"timezone": "Asia/Shanghai"}


def test_a_mismatch_names_both_regions_and_rejects_by_default():
    check = check_exit(SHANGHAI, "America/New_York", "203.0.113.9")
    assert check.outcome == "mismatched"
    assert check.message == "出口 IP 203.0.113.9 位于 America/New_York，与身份地区 Asia/Shanghai 不一致"
    assert not may_start(check, SHANGHAI)
    assert may_start(check, {**SHANGHAI, "mismatchPolicy": "warn"})


@pytest.mark.parametrize(("policy", "allowed"), [(None, True), ("warn", True), ("reject", False)])
def test_an_unlocatable_exit_follows_the_unverified_policy(policy, allowed):
    region = {**SHANGHAI, **({"unverifiedPolicy": policy} if policy else {})}
    check = check_exit(region, None, None)
    assert check.outcome == "unverified" and "Asia/Shanghai" in check.message
    assert may_start(check, region) is allowed


def test_matching_or_unconstrained_identities_start():
    assert check_exit(SHANGHAI, "Asia/Shanghai", "1.2.3.4").outcome == "matched"
    assert check_exit({}, "Europe/Berlin", "1.2.3.4").outcome == "unconstrained"
    assert may_start(check_exit({}, None, None), {})
