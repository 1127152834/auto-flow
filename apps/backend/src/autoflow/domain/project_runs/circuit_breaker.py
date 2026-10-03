"""Batch circuit breaker (remediation M2 R2-15).

Pauses a batch when technical failures say the site or environment is broken,
rather than letting every remaining row fail the same way. Business results and
unknown outcomes never count: business failures are expected data, unknown ones
already wait for a person.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

WINDOW = 20
MIN_RATE_SAMPLE = 10
PAGE_RATE = 0.5
INFRASTRUCTURE_STREAK = 5
SAME_CODE_STREAK = 10
SAMPLE_SIZE = 5
_TECHNICAL = frozenset({"page", "infrastructure"})
_IGNORED = frozenset({"business", "unknown", "cancelled"})


@dataclass(frozen=True)
class FinishedTask:
    task_id: str
    kind: str
    code: str | None


@dataclass(frozen=True)
class PauseReason:
    kind: str
    message: str
    sample_task_ids: tuple[str, ...]
    code: str | None = None


def evaluate(history: Sequence[FinishedTask]) -> PauseReason | None:
    """``history`` is ordered oldest first and holds only tasks finished since the last resume."""
    relevant = [task for task in history if task.kind not in _IGNORED]
    streak: list[FinishedTask] = []
    for task in reversed(relevant):
        if task.kind != "infrastructure":
            break
        streak.append(task)
    if len(streak) >= INFRASTRUCTURE_STREAK:
        return PauseReason(
            "infrastructureStreak",
            f"连续 {len(streak)} 个任务在开始前因环境或代理问题失败，已暂停批次",
            tuple(task.task_id for task in streak[:SAMPLE_SIZE]),
            streak[0].code,
        )
    same: list[FinishedTask] = []
    for task in reversed(relevant):
        if task.kind not in _TECHNICAL or task.code is None or (same and task.code != same[0].code):
            break
        same.append(task)
    if len(same) >= SAME_CODE_STREAK:
        return PauseReason(
            "sameErrorStreak",
            f"连续 {len(same)} 个任务以相同原因失败，已暂停批次",
            tuple(task.task_id for task in same[:SAMPLE_SIZE]),
            same[0].code,
        )
    window = list(history)[-WINDOW:]
    pages = [task for task in window if task.kind == "page"]
    if len(window) >= MIN_RATE_SAMPLE and len(pages) > len(window) * PAGE_RATE:
        return PauseReason(
            "pageFailureRate",
            f"最近 {len(window)} 个任务中有 {len(pages)} 个页面类失败，已暂停批次",
            tuple(task.task_id for task in pages[-SAMPLE_SIZE:]),
        )
    return None
