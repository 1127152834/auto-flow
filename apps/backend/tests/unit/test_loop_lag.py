import asyncio
import logging
import time

import pytest

from autoflow.infrastructure.observability import LoopLagMonitor


@pytest.mark.asyncio
async def test_blocking_the_loop_is_measured_and_logged(caplog):
    monitor = LoopLagMonitor(interval=0.01, warn_ms=100)
    await monitor.start()
    try:
        with caplog.at_level(logging.WARNING, logger="autoflow.loop_lag"):
            time.sleep(0.3)  # noqa: ASYNC251 -- deliberately inject loop starvation
            await asyncio.sleep(0.05)
        snapshot = monitor.snapshot()
    finally:
        await monitor.stop()
    assert snapshot.max_ms >= 250
    assert snapshot.samples >= 3
    assert any("event loop lag" in record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_start_is_idempotent_and_stop_can_repeat():
    monitor = LoopLagMonitor(interval=0.01)
    await monitor.stop()  # never started
    await monitor.start()
    await monitor.start()
    assert monitor.running
    await asyncio.sleep(0.2)
    await monitor.stop()
    await monitor.stop()
    assert not monitor.running
    snapshot = monitor.snapshot()
    assert snapshot.samples >= 5
    assert snapshot.p50_ms < 50
    monitor.reset()
    assert monitor.snapshot().samples == 0


@pytest.mark.asyncio
async def test_samples_are_bounded_and_expire_after_five_minutes(monkeypatch):
    from autoflow.infrastructure.observability import loop_lag

    monitor = LoopLagMonitor(interval=0.01, capacity=3)
    await monitor.start()
    await asyncio.sleep(0.08)
    await monitor.stop()
    assert monitor.snapshot().samples == 3
    future = loop_lag.perf_counter() + 301
    monkeypatch.setattr(loop_lag, "perf_counter", lambda: future)
    assert monitor.snapshot().samples == 0
    assert monitor.snapshot().max_ms == 0


@pytest.mark.parametrize(
    "options", [{"interval": 0}, {"interval": float("nan")}, {"capacity": 0}]
)
def test_invalid_monitor_configuration_is_rejected(options):
    with pytest.raises(ValueError):
        LoopLagMonitor(**options)
