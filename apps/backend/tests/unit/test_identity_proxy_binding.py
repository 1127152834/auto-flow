"""Remediation M4 S5 (R4-04): an identity keeps its proxy member; a broken one follows the policy."""

import pytest

from autoflow.domain.identities.proxy_binding import Member, bind, choose_member

POOL = "pool-1"
SHANGHAI_A = Member("a", "上海", True)
SHANGHAI_B = Member("b", "上海", True)
BEIJING_C = Member("c", "北京", True)


def test_first_use_binds_a_usable_member_and_later_runs_keep_it():
    first = choose_member(None, POOL, [Member("x", "上海", False), SHANGHAI_A, SHANGHAI_B])
    assert (first.outcome, first.member_id) == ("bind", "a")
    binding = bind(POOL, SHANGHAI_A, None)
    assert binding == {"poolId": POOL, "memberId": "a", "region": "上海", "policy": "sameRegion"}
    # The pool rotates, the identity does not.
    assert choose_member(binding, POOL, [SHANGHAI_B, BEIJING_C, SHANGHAI_A]) .member_id == "a"


@pytest.mark.parametrize(("policy", "outcome", "member"), [
    ("sameRegion", "replace", "b"),
    ("confirm", "confirm", None),
    ("never", "unavailable", None),
])
def test_a_broken_member_follows_the_identity_policy(policy, outcome, member):
    binding = {**bind(POOL, SHANGHAI_A, None), "policy": policy}
    choice = choose_member(binding, POOL, [Member("a", "上海", False), BEIJING_C, SHANGHAI_B])
    assert (choice.outcome, choice.member_id) == (outcome, member)


def test_same_region_never_crosses_regions_and_a_deleted_member_counts_as_broken():
    binding = bind(POOL, SHANGHAI_A, None)
    choice = choose_member(binding, POOL, [BEIJING_C])  # member "a" was removed from the pool
    assert choice.outcome == "unavailable" and "上海" in choice.reason


def test_a_binding_to_another_pool_starts_over_and_keeps_the_policy():
    binding = {**bind("old-pool", SHANGHAI_A, None), "policy": "confirm"}
    choice = choose_member(binding, POOL, [BEIJING_C])
    assert (choice.outcome, choice.member_id) == ("bind", "c")
    assert bind(POOL, BEIJING_C, binding)["policy"] == "confirm"


def test_an_empty_pool_is_unavailable():
    assert choose_member(None, POOL, []).outcome == "unavailable"
