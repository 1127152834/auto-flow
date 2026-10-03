"""Failure categories from durable run facts (remediation M2 R2-13).

Every node attempt is persisted and acknowledged before the node runs, together
with its side-effect declaration. A failed Task is only safe to run again as a
whole when no node that may act outside the run had started; missing evidence
counts as a possible side effect.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

FailureCategory = Literal["infrastructure", "page", "unknown", "cancelled"]


@dataclass(frozen=True)
class AttemptFact:
    visit: str
    status: str
    side_effect: str | None


def classify(
    status: str, error: Mapping[str, Any] | None, attempts: Iterable[AttemptFact]
) -> FailureCategory | None:
    del error  # The code alone never decides; the started-node facts do (R2-05/R2-13).
    if status == "succeeded":
        return None
    started: dict[str, bool] = {}
    finished: set[str] = set()
    for fact in attempts:
        if fact.status == "started":
            started[fact.visit] = fact.side_effect != "none"
        else:
            finished.add(fact.visit)
    if not started:
        return "infrastructure"
    if status == "cancelled":
        in_flight = any(possible and visit not in finished for visit, possible in started.items())
        return "unknown" if in_flight else "cancelled"
    return "unknown" if any(started.values()) else "page"
