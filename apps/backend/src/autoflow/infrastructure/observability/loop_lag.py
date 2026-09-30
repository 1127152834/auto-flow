"""Event-loop lag monitor (remediation M0, R0-05)."""

from __future__ import annotations

import asyncio
import logging
import math
from collections import deque
from dataclasses import dataclass
from time import perf_counter

LOGGER = logging.getLogger("autoflow.loop_lag")


@dataclass(frozen=True)
class LoopLagSnapshot:
    p50_ms: float
    p99_ms: float
    max_ms: float
    samples: int


def _percentile(ordered: list[float], fraction: float) -> float:
    if not ordered:
        return 0.0
    return ordered[min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))]


class LoopLagMonitor:
    """Schedules a heartbeat and records how late the event loop ran it."""

    def __init__(
        self, *, interval: float = 0.05, warn_ms: float = 100.0, capacity: int = 6000
    ) -> None:
        if (
            not math.isfinite(interval)
            or interval <= 0
            or capacity < 1
            or not math.isfinite(warn_ms)
            or warn_ms < 0
        ):
            raise ValueError(
                "Monitor interval/capacity must be positive and threshold finite"
            )
        self._interval = interval
        self._warn_ms = warn_ms
        self._samples: deque[tuple[float, float]] = deque(maxlen=capacity)
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if not self.running:
            self._task = asyncio.create_task(self._run(), name="autoflow-loop-lag")
            await asyncio.sleep(0)  # Arm heartbeat before startup can block the loop.

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def snapshot(self) -> LoopLagSnapshot:
        cutoff = perf_counter() - 300
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()
        ordered = sorted(value for _, value in self._samples)
        return LoopLagSnapshot(
            p50_ms=_percentile(ordered, 0.50),
            p99_ms=_percentile(ordered, 0.99),
            max_ms=ordered[-1] if ordered else 0.0,
            samples=len(ordered),
        )

    def reset(self) -> None:
        self._samples.clear()

    async def _run(self) -> None:
        while True:
            expected = perf_counter() + self._interval
            await asyncio.sleep(self._interval)
            now = perf_counter()
            lag_ms = max(0.0, (now - expected) * 1000)
            self._samples.append((now, lag_ms))
            if lag_ms > self._warn_ms:
                LOGGER.warning("event loop lag %.0f ms", lag_ms)
