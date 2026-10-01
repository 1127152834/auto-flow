"""Remediation M1 R1-12: data claims never run on the event-loop thread."""

import threading

import pytest

from tests.integration.test_project_data_scheduler import data_services, start  # noqa: F401 - fixture reuse


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
