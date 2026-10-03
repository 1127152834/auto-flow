"""Remediation M2 R2-25/R2-26 / AC2-09: timed and webhook triggers start one batch per trigger."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from autoflow.application.project_automations.schedules import AutomationScheduleService
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_run_models import ProjectBatchRow
from tests.integration.test_project_run_data_start import _setup

NINE = datetime(2026, 10, 3, 1, 0, tzinfo=UTC)  # 09:00 Asia/Shanghai


def schedule(**changes):
    return {"kind": "cron", "cron": "0 9 * * *", "timezone": "Asia/Shanghai", "overlap": "skip",
            "missed": "latestOnly", "enabled": True, "parameters": {}, "maxTasks": 1, "concurrency": 1, **changes}


@pytest.fixture
def world(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    service = AutomationScheduleService(factory, coordinator)
    yield factory, project_id, automation, coordinator, service
    factory.dispose()


def batches(factory):
    with factory() as session:
        return session.scalar(select(func.count()).select_from(ProjectBatchRow))


def finish_all(factory):
    with factory.begin() as session:
        session.execute(update(ProjectBatchRow).values(status="completed"))


def test_a_planned_time_starts_exactly_one_batch_even_across_restarts(world):
    factory, project_id, automation, coordinator, service = world
    created = service.create(project_id, automation.automation_id, schedule())
    assert service.tick(NINE - timedelta(minutes=1)) == []
    assert len(service.tick(NINE + timedelta(seconds=5))) == 1
    assert service.tick(NINE + timedelta(seconds=40)) == []
    restarted = AutomationScheduleService(factory, coordinator)
    assert restarted.tick(NINE + timedelta(seconds=50)) == []
    assert batches(factory) == 1
    triggers = service.triggers(project_id, automation.automation_id, created["scheduleId"])
    assert [(item["state"], item["plannedAt"]) for item in triggers] == [("started", NINE.isoformat())]


def test_overlap_skip_records_the_skipped_trigger(world):
    factory, project_id, automation, _coordinator, service = world
    created = service.create(project_id, automation.automation_id, schedule(cron="*/5 * * * *"))
    service.tick(NINE)
    service.tick(NINE + timedelta(minutes=5))
    assert batches(factory) == 1
    states = [item["state"] for item in service.triggers(project_id, automation.automation_id, created["scheduleId"])]
    assert states == ["skipped", "started"]


def test_overlap_queue_starts_after_the_previous_batch_finishes(world):
    factory, project_id, automation, _coordinator, service = world
    created = service.create(project_id, automation.automation_id, schedule(cron="*/5 * * * *", overlap="queue"))
    service.tick(NINE)
    service.tick(NINE + timedelta(minutes=5))
    assert batches(factory) == 1
    finish_all(factory)
    service.tick(NINE + timedelta(minutes=6))
    assert batches(factory) == 2
    states = [item["state"] for item in service.triggers(project_id, automation.automation_id, created["scheduleId"])]
    assert states == ["started", "started"]


def test_missed_runs_catch_up_once_or_not_at_all(world):
    factory, project_id, automation, _coordinator, service = world
    service.create(project_id, automation.automation_id, schedule(cron="0 * * * *"))
    service.tick(NINE)
    finish_all(factory)
    service.tick(NINE + timedelta(hours=5, minutes=20))
    assert batches(factory) == 2, "latestOnly starts one batch for the latest missed hour"
    finish_all(factory)
    ignoring = service.create(project_id, automation.automation_id, schedule(cron="30 * * * *", missed="ignore"))
    service.tick(NINE + timedelta(hours=7, minutes=50))
    assert service.triggers(project_id, automation.automation_id, ignoring["scheduleId"]) == [], "ignore never fires a stale planned time"


def test_webhook_needs_its_secret_and_one_event_starts_one_batch(world):
    factory, project_id, automation, _coordinator, service = world
    created = service.create(project_id, automation.automation_id, schedule(kind="webhook", cron=None))
    secret = created["webhookSecret"]
    first = service.webhook(project_id, automation.automation_id, created["scheduleId"], secret, "order-42")
    again = service.webhook(project_id, automation.automation_id, created["scheduleId"], secret, "order-42")
    assert first["batchId"] == again["batchId"] and batches(factory) == 1
    with pytest.raises(ProjectError) as denied:
        service.webhook(project_id, automation.automation_id, created["scheduleId"], "wrong", "order-43")
    assert denied.value.status == 403 and batches(factory) == 1
    assert "webhookSecret" not in service.schedules(project_id, automation.automation_id)[0]


def test_disabled_and_updated_schedules(world):
    factory, project_id, automation, _coordinator, service = world
    created = service.create(project_id, automation.automation_id, schedule(enabled=False))
    service.tick(NINE)
    assert batches(factory) == 0
    updated = service.update(project_id, automation.automation_id, created["scheduleId"], created["revision"], schedule(enabled=True))
    assert updated["revision"] == created["revision"] + 1
    with pytest.raises(ProjectError) as stale:
        service.update(project_id, automation.automation_id, created["scheduleId"], created["revision"], schedule())
    assert stale.value.code == "REVISION_CONFLICT"
    service.tick(NINE + timedelta(days=1))
    assert batches(factory) == 1


def test_http_routes_create_list_update_and_call_webhook(world):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from autoflow.adapters.http.automation_schedules import automation_schedules_router
    from autoflow.adapters.http.errors import install_error_handlers

    factory, project_id, automation, _coordinator, service = world
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(automation_schedules_router(service))
    client = TestClient(app)
    base = f"/api/v1/projects/{project_id}/automations/{automation.automation_id}/schedules"

    created = client.post(base, json=schedule(kind="webhook", cron=None))
    assert created.status_code == 201, created.text
    secret, schedule_id = created.json()["webhookSecret"], created.json()["scheduleId"]
    assert client.get(base).json()[0]["webhookSecret"] is None
    bad = client.post(f"{base}/{schedule_id}/webhook", json={"eventId": "e1"}, headers={"X-AutoFlow-Webhook-Secret": "x"})
    assert bad.status_code == 403
    called = client.post(f"{base}/{schedule_id}/webhook", json={"eventId": "e1"}, headers={"X-AutoFlow-Webhook-Secret": secret})
    assert called.status_code == 202 and called.json()["state"] == "started"
    again = client.post(f"{base}/{schedule_id}/webhook", json={"eventId": "e1"}, headers={"X-AutoFlow-Webhook-Secret": secret})
    assert again.json()["triggerId"] == called.json()["triggerId"]
    assert batches(factory) == 1
    stale = client.put(f"{base}/{schedule_id}", json={**schedule(kind="webhook", cron=None, enabled=False), "expectedRevision": 9})
    assert stale.status_code == 409
    updated = client.put(f"{base}/{schedule_id}", json={**schedule(kind="webhook", cron=None, enabled=False), "expectedRevision": 1})
    assert updated.status_code == 200 and updated.json()["enabled"] is False
    assert len(client.get(f"{base}/{schedule_id}/triggers").json()) == 1
    assert client.delete(f"{base}/{schedule_id}").status_code == 204
    assert client.get(base).json() == []
