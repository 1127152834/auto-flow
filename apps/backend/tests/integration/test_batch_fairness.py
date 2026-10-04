"""Remediation M3 R3-08: batches share execution slots fairly by priority and take turns."""

from uuid import uuid4

import pytest

from tests.integration.test_project_parameter_concurrency import configure, core_services, until
from tests.integration.test_project_run_start import setup, start_payload


def start(coordinator, project, automation, *, concurrency=2, priority=None):
    payload = {**start_payload(automation, max_tasks=4), "concurrency": concurrency}
    if priority is not None:
        payload["priority"] = priority
    return coordinator.start(project.project_id, automation.automation_id, str(uuid4()), payload)[0]


def running(coordinator, project, batch, workers):
    runs = {task.run_id for task in coordinator.list_tasks(project.project_id, batch.batch_id)}
    return len(runs & set(workers.active))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("first", "second", "second_concurrency", "expected"),
    [
        (None, None, 2, (1, 1)),          # equals take turns instead of the older batch taking every slot
        ("normal", "high", 2, (0, 2)),    # the high batch is served first even though it started later
        ("normal", "high", 1, (1, 1)),    # a batch's own concurrency limit leaves the rest to others
        ("low", None, 2, (0, 2)),         # low waits behind normal
    ],
)
async def test_slots_follow_priority_turns_and_batch_limits(tmp_path, first, second, second_concurrency, expected):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    configure(factory, automation, concurrency=4, instances=4)
    older = start(coordinator, project, automation, priority=first)
    newer = start(coordinator, project, automation, priority=second, concurrency=second_concurrency)
    workers, core, scheduler = core_services(factory, capacity=2)
    try:
        await scheduler.tick()
        await until(lambda: len(workers.calls) >= 2)
        assert (running(coordinator, project, older, workers), running(coordinator, project, newer, workers)) == expected
    finally:
        await core.shutdown()
        factory.dispose()


def test_unknown_priority_is_rejected(tmp_path):
    from autoflow.domain.project_runs.models import ProjectRunError

    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    with pytest.raises(ProjectRunError) as rejected:
        start(coordinator, project, automation, priority="urgent")
    assert rejected.value.details["fields"]["priority"] == "必须是 high、normal 或 low"
    factory.dispose()


@pytest.mark.asyncio
async def test_the_next_turn_starts_after_the_batch_served_last(tmp_path):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    older = start(coordinator, project, automation)
    newer = start(coordinator, project, automation)
    _workers, core, scheduler = core_services(factory, capacity=1)
    try:
        assert [batch for _project, batch in scheduler._fair_rounds()[0]] == [older.batch_id, newer.batch_id]
        scheduler._last_served = older.batch_id
        assert [batch for _project, batch in scheduler._fair_rounds()[0]] == [newer.batch_id, older.batch_id]
    finally:
        await core.shutdown()
        factory.dispose()
