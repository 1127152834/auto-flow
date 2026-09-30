from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

REQUIRED_CHECKS = ("boot", "store", "login", "download", "restart", "isolation")


@dataclass(frozen=True)
class VerificationResult:
    status: str
    checked_at: datetime | None
    checks: tuple[dict[str, Any], ...]
    limitations: tuple[str, ...] = ()


def summarize_verification(observations: list[dict[str, Any]]) -> VerificationResult:
    records = tuple(observations)
    if not records:
        return VerificationResult("not_tested", None, records)
    statuses = {record.get("status") for record in records}
    if "failed" in statuses:
        status = "failed"
    elif "blocked" in statuses:
        status = "blocked"
    elif set(REQUIRED_CHECKS).issubset({record.get("checkId") for record in records}) and statuses == {"passed"}:
        status = "passed"
    else:
        status = "not_tested"
    return VerificationResult(status, datetime.now(UTC), records)
