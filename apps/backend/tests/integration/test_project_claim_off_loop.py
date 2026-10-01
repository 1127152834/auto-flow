"""Remediation M1 R1-12: data claims never run on the event-loop thread."""

import threading

import pytest

from tests.integration.test_project_data_scheduler import (  # noqa: F401 - fixture reuse
    data_services,
    start,
)


@pytest.mark.asyncio
async def test_data_claims_run_off_the_event_loop(data_services, monkeypatch):  # noqa: F811
    _factory, _project, _automation, _coordinator, _worker, core, scheduler = data_services
    loop_thread = threading.get_ident()
    seen: list[int] = []
    original = scheduler._claim_data_task

    def spy(project_id, batch_id):
        seen.append(threading.get_ident())
        return original(project_id, batch_id)

    monkeypatch.setattr(scheduler, "_claim_data_task", spy)
    start(data_services, 1)
    await scheduler.tick()
    await core.wait_idle()
    assert seen, "the batch never claimed a row"
    assert all(ident != loop_thread for ident in seen)


@pytest.mark.asyncio
async def test_cancelling_a_tick_during_a_claim_settles_it_and_never_starts_a_second_claim(data_services, monkeypatch):  # noqa: F811
    import asyncio
    import time

    _factory, _project, _automation, _coordinator, _worker, core, scheduler = data_services
    original = scheduler._claim_data_task
    entered, release = threading.Event(), threading.Event()
    running, peak, claims = [0], [0], []
    guard = threading.Lock()

    def spy(project_id, batch_id):
        with guard:
            running[0] += 1
            peak[0] = max(peak[0], running[0])
        try:
            if not entered.is_set():
                entered.set()
                assert release.wait(10)
            outcome = original(project_id, batch_id)
            claims.append(outcome)
            return outcome
        finally:
            with guard:
                running[0] -= 1

    monkeypatch.setattr(scheduler, "_claim_data_task", spy)
    start(data_services, 3)
    first = asyncio.create_task(scheduler.tick())
    while not entered.is_set():
        await asyncio.sleep(0.01)
    first.cancel()
    second = asyncio.create_task(scheduler.tick())
    await asyncio.sleep(0.3)  # the cancelled tick keeps its lock until the claim settles; no second claim
    with guard:
        assert running[0] == 1 and peak[0] == 1
    assert not first.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await first
    await second
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and running[0]:
        await asyncio.sleep(0.01)
    await core.wait_idle()
    assert peak[0] == 1
