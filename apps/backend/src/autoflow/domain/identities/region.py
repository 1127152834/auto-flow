"""Exit region versus an identity's region (remediation M4 R4-05).

Only what the identity actually fixes is compared: its timezone. A run whose exit could not be
located is "unverified" — the identity's policy decides whether that may still start.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

MismatchPolicy = Literal["reject", "warn"]


@dataclass(frozen=True)
class RegionCheck:
    outcome: Literal["matched", "mismatched", "unverified", "unconstrained"]
    message: str | None = None


def check_exit(region: dict[str, Any] | None, exit_timezone: str | None, exit_ip: str | None) -> RegionCheck:
    expected = (region or {}).get("timezone")
    if not expected:
        return RegionCheck("unconstrained")
    if not exit_timezone:
        return RegionCheck("unverified", f"无法确认出口 IP{f' {exit_ip}' if exit_ip else ''} 的地区，身份地区为 {expected}")
    if exit_timezone == expected:
        return RegionCheck("matched")
    return RegionCheck(
        "mismatched",
        f"出口 IP{f' {exit_ip}' if exit_ip else ''} 位于 {exit_timezone}，与身份地区 {expected} 不一致",
    )


def may_start(check: RegionCheck, region: dict[str, Any] | None) -> bool:
    """Mismatch rejects by default; an unverifiable exit warns and continues by default."""
    policies = region or {}
    if check.outcome == "mismatched":
        return bool(policies.get("mismatchPolicy", "reject") == "warn")
    if check.outcome == "unverified":
        return bool(policies.get("unverifiedPolicy", "warn") == "warn")
    return True
