"""Sticky proxy members for identities (remediation M4 R4-04).

An identity keeps the pool member it first got. When that member can no longer be used, its
replacement policy decides: ``sameRegion`` moves to a usable member of the same region,
``confirm`` waits for a person, ``never`` makes the identity unavailable. A same member id does
not promise the same exit IP; that is checked separately before launch (R4-05).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Policy = Literal["sameRegion", "confirm", "never"]
POLICIES: tuple[Policy, ...] = ("sameRegion", "confirm", "never")
DEFAULT_POLICY: Policy = "sameRegion"


@dataclass(frozen=True)
class Member:
    member_id: str
    region: str | None
    usable: bool


@dataclass(frozen=True)
class Choice:
    outcome: Literal["use", "bind", "replace", "confirm", "unavailable"]
    member_id: str | None = None
    reason: str | None = None


def choose_member(binding: dict | None, pool_id: str, members: list[Member]) -> Choice:
    """Pick the member for this run; ``bind``/``replace`` mean the binding must be stored."""
    usable = [member for member in members if member.usable]
    bound = binding if isinstance(binding, dict) and binding.get("poolId") == pool_id else None
    if bound is None:
        if not usable:
            return Choice("unavailable", reason="代理池中没有可用成员")
        return Choice("bind", usable[0].member_id)
    current = next((member for member in members if member.member_id == bound.get("memberId")), None)
    if current is not None and current.usable:
        return Choice("use", current.member_id)
    policy = bound.get("policy") if bound.get("policy") in POLICIES else DEFAULT_POLICY
    if policy == "never":
        return Choice("unavailable", reason="身份固定的代理已失效，且设置为不更换")
    if policy == "confirm":
        return Choice("confirm", reason="身份固定的代理已失效，需要人工确认更换")
    region = bound.get("region")
    same = [member for member in usable if region and member.region == region]
    if not same:
        return Choice("unavailable", reason=f"身份固定的代理已失效，代理池中没有同地区（{region or '未知地区'}）的可用成员")
    return Choice("replace", same[0].member_id)


def bind(pool_id: str, member: Member, previous: dict | None) -> dict:
    policy = previous.get("policy") if isinstance(previous, dict) and previous.get("policy") in POLICIES else DEFAULT_POLICY
    return {"poolId": pool_id, "memberId": member.member_id, "region": member.region, "policy": policy}
