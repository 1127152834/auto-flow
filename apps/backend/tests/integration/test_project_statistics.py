"""PM7-B: statistics aggregation, frozen result sets and drill-down."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.project_statistics import project_statistics_router
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.projects.statistics import ProjectStatisticsService
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.integration.test_project_failure_followup import _fail_run
from tests.integration.test_project_run_data_start import _setup, uid

BASE = datetime(2026, 3, 10, 4, 0, tzinfo=UTC)


def _stock_inputs(factory, project_id, automation, count: int) -> None:
    """One consumed row per Task: a failed Task keeps its lease until reconcile."""
    records = DataRecordService(SqlAlchemyProjectDataRecords(factory))
    for item in automation.input_plan["inputs"]:
        field_id = item["fieldBindings"][0]["fieldRef"]["fieldId"]
        for index in range(count):
            records.create(
                project_id,
                item["tableId"],
                uid(),
                {
                    "datasetGeneration": item["datasetGeneration"],
                    "values": [
                        {"fieldId": field_id, "value": f"{item['alias']}-{index}"}
                    ],
                },
            )


def _project(tmp_path, tasks: int):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    _stock_inputs(factory, project_id, automation, tasks)
    return factory, project_id, automation, coordinator


def _start_and_fail(factory, project_id, automation, coordinator):
    batch, _operation, _replayed = coordinator.start(
        project_id,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )
    assert ProjectBatchScheduler.claim_data_task(factory, project_id, batch.batch_id) == (
        "ready"
    )
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    _fail_run(factory, task.run_id)
    return task


def _seed(
    factory,
    project_id,
    automation,
    coordinator,
    *,
    status: str,
    started_at: datetime | None,
    completed_at: datetime,
    error: dict | None = None,
):
    """Real accepted Batch + real terminal transition, then pinned clock.

    Only `started_at` / `completed_at` / `status` are rewritten: the aggregation
    under test reads those columns, and the lifecycle itself is covered by the
    runtime tests. Everything else stays a genuine fact.
    """
    task = _start_and_fail(factory, project_id, automation, coordinator)
    with factory() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        assert run is not None
        run.status = status
        run.started_at = started_at
        run.completed_at = completed_at
        run.error = error
        session.commit()
    return task


def _finish(factory, project_id, automation, coordinator, started_at, completed_at):
    return _seed(
        factory,
        project_id,
        automation,
        coordinator,
        status="succeeded",
        started_at=started_at,
        completed_at=completed_at,
    )


def test_fixed_scenario_success_rate_and_durations(tmp_path):
    factory, project_id, automation, coordinator = _project(tmp_path, 5)
    for offset in (0, 1):
        _finish(
            factory,
            project_id,
            automation,
            coordinator,
            BASE + timedelta(seconds=10 + offset),
            BASE + timedelta(seconds=20 + offset),
        )
    _seed(
        factory,
        project_id,
        automation,
        coordinator,
        status="failed",
        started_at=BASE + timedelta(seconds=30),
        completed_at=BASE + timedelta(seconds=60),
        error={"code": "RUN_FAILED", "message": "节点执行失败"},
    )
    for terminal in ("cancelled", "interrupted"):
        _seed(
            factory,
            project_id,
            automation,
            coordinator,
            status=terminal,
            started_at=BASE + timedelta(minutes=2),
            completed_at=BASE + timedelta(minutes=3),
        )

    service = ProjectStatisticsService(factory)
    stats = service.get(
        project_id,
        now=BASE + timedelta(hours=1),
        to=BASE + timedelta(minutes=5),
    )

    assert stats["sample"] == {
        "succeeded": 2,
        "failed": 1,
        "cancelled": 1,
        "timed_out": 0,
        "interrupted": 1,
    }
    # cancelled / interrupted are listed but never enter the rate denominator.
    assert stats["successRate"] == pytest.approx(2 / 3)
    # Only succeeded+failed with both ends present: 10s, 10s, 30s -> 16.67s.
    assert stats["averageDurationMs"] == 16667
    assert stats["trend"] == [
        {
            "bucketStart": stats["trend"][0]["bucketStart"],
            "succeeded": 2,
            "failed": 1,
            "cancelled": 1,
            "timed_out": 0,
            "interrupted": 1,
            "averageDurationMs": 16667,
        }
    ]


def test_zero_denominator_and_missing_start_are_omitted(tmp_path):
    factory, project_id, automation, coordinator = _project(tmp_path, 2)
    _seed(
        factory,
        project_id,
        automation,
        coordinator,
        status="cancelled",
        started_at=BASE,
        completed_at=BASE + timedelta(minutes=1),
    )
    _finish(
        factory,
        project_id,
        automation,
        coordinator,
        None,
        BASE + timedelta(minutes=4),
    )
    service = ProjectStatisticsService(factory)
    only_cancelled = service.get(
        project_id,
        from_=BASE,
        to=BASE + timedelta(minutes=1),
        now=BASE + timedelta(hours=1),
    )

    # No succeeded and no failed in window: the rate is omitted, not 0 and not 100%.
    assert only_cancelled["sample"]["cancelled"] == 1
    assert only_cancelled["successRate"] is None
    assert only_cancelled["averageDurationMs"] is None
    assert only_cancelled["trend"][0]["averageDurationMs"] is None

    # A succeeded run without `started_at` contributes no duration sample.
    both = service.get(project_id, now=BASE + timedelta(hours=1))
    assert both["sample"] == {
        "succeeded": 1,
        "failed": 0,
        "cancelled": 1,
        "timed_out": 0,
        "interrupted": 0,
    }
    assert both["successRate"] == 1
    assert both["averageDurationMs"] is None


def test_window_uses_completed_at_and_half_open_edges(tmp_path):
    factory, project_id, automation, coordinator = _project(tmp_path, 3)
    _finish(factory, project_id, automation, coordinator, BASE, BASE)
    _finish(
        factory,
        project_id,
        automation,
        coordinator,
        BASE,
        BASE + timedelta(minutes=5),
    )
    _finish(
        factory,
        project_id,
        automation,
        coordinator,
        BASE,
        BASE + timedelta(minutes=5, microseconds=1),
    )

    stats = ProjectStatisticsService(factory).get(
        project_id,
        from_=BASE,
        to=BASE + timedelta(minutes=5),
        now=BASE + timedelta(hours=1),
    )

    assert stats["sample"]["succeeded"] == 2


def test_bucket_honours_request_timezone_and_assigns_once(tmp_path):
    factory, project_id, automation, coordinator = _project(tmp_path, 1)
    # 2026-01-01 00:30 in +08:00, which is still 2025-12-31 in UTC.
    _finish(
        factory,
        project_id,
        automation,
        coordinator,
        datetime(2025, 12, 31, 16, 0, tzinfo=UTC),
        datetime(2025, 12, 31, 16, 30, tzinfo=UTC),
    )
    service = ProjectStatisticsService(factory)
    window = {
        "from_": datetime(2025, 12, 31, 0, 0, tzinfo=UTC),
        "to": datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
        "now": datetime(2026, 3, 10, tzinfo=UTC),
    }

    shanghai = service.get(project_id, timezone="Asia/Shanghai", **window)
    utc = service.get(project_id, timezone="UTC", **window)

    assert len(shanghai["trend"]) == 1
    assert shanghai["trend"][0]["bucketStart"].startswith("2026-01-01T00:00:00+08:00")
    assert len(utc["trend"]) == 1
    assert utc["trend"][0]["bucketStart"].startswith("2025-12-31T00:00:00+00:00")


def test_week_and_month_buckets(tmp_path):
    factory, project_id, automation, coordinator = _project(tmp_path, 1)
    _finish(
        factory,
        project_id,
        automation,
        coordinator,
        BASE,
        datetime(2026, 3, 11, 4, 0, tzinfo=UTC),
    )
    service = ProjectStatisticsService(factory)
    common = {
        "timezone": "UTC",
        "from_": datetime(2026, 3, 1, tzinfo=UTC),
        "to": datetime(2026, 4, 1, tzinfo=UTC),
        "now": datetime(2026, 4, 2, tzinfo=UTC),
    }

    week = service.get(project_id, interval="week", **common)
    month = service.get(project_id, interval="month", **common)

    assert week["trend"][0]["bucketStart"].startswith("2026-03-09T00:00:00+00:00")
    assert month["trend"][0]["bucketStart"].startswith("2026-03-01T00:00:00+00:00")


def test_invalid_timezone_range_and_interval_are_rejected(tmp_path):
    factory, project_id, _automation, _coordinator = _project(tmp_path, 0)
    service = ProjectStatisticsService(factory)

    with pytest.raises(ProjectError) as zone:
        service.get(project_id, timezone="Nope/Nowhere")
    assert zone.value.code == "VALIDATION_ERROR" and zone.value.status == 422

    with pytest.raises(ProjectError) as backwards:
        service.get(project_id, from_=BASE, to=BASE - timedelta(days=1))
    assert backwards.value.code == "STATISTICS_RANGE_INVALID"

    with pytest.raises(ProjectError) as naive:
        service.get(project_id, from_=datetime(2026, 3, 1, tzinfo=None))  # noqa: DTZ001
    assert naive.value.code == "STATISTICS_RANGE_INVALID"

    with pytest.raises(ProjectError) as interval:
        service.get(project_id, interval="hour")
    assert interval.value.code == "STATISTICS_RANGE_INVALID"

    with pytest.raises(ProjectError) as missing:
        service.get(str(uuid4()))
    assert missing.value.status == 404


def test_failures_by_automation_groups_failed_runs(tmp_path):
    factory, project_id, automation, coordinator = _project(tmp_path, 3)
    _finish(factory, project_id, automation, coordinator, BASE, BASE)
    for _ in range(2):
        _seed(
            factory,
            project_id,
            automation,
            coordinator,
            status="failed",
            started_at=BASE,
            completed_at=BASE + timedelta(minutes=1),
            error={"code": "RUN_FAILED", "message": "节点执行失败"},
        )

    stats = ProjectStatisticsService(factory).get(
        project_id, now=BASE + timedelta(hours=1)
    )

    assert stats["failuresByAutomation"] == [
        {
            "automationId": automation.automation_id,
            "name": "首条三表链",
            "count": 2,
            "reasonSummary": "节点执行失败",
        }
    ]


def test_drill_down_matches_metrics_and_ignores_later_finishes(tmp_path):
    factory, project_id, automation, coordinator = _project(tmp_path, 3)
    calculated_at = BASE + timedelta(minutes=10)
    _finish(factory, project_id, automation, coordinator, BASE, BASE)
    _seed(
        factory,
        project_id,
        automation,
        coordinator,
        status="failed",
        started_at=BASE,
        completed_at=BASE + timedelta(minutes=1),
        error={"code": "RUN_FAILED"},
    )
    service = ProjectStatisticsService(factory)
    stats = service.get(
        project_id,
        from_=BASE - timedelta(days=1),
        to=BASE + timedelta(days=1),
        now=calculated_at,
    )

    items, total = service.tasks(
        project_id,
        stats["resultSetId"],
        result="failed",
        page=1,
        page_size=50,
        now=calculated_at,
    )
    assert total == 1 and items[0]["status"] == "failed"

    # A run finishing *after* calculatedAt is outside the frozen predicate, and
    # stays outside on every later read of the same resultSetId.
    _seed(
        factory,
        project_id,
        automation,
        coordinator,
        status="failed",
        started_at=BASE,
        completed_at=calculated_at + timedelta(seconds=1),
        error={"code": "RUN_FAILED"},
    )
    again, total_again = service.tasks(
        project_id,
        stats["resultSetId"],
        result="failed",
        page=1,
        page_size=50,
        now=calculated_at,
    )
    assert total_again == 1
    assert [item["taskId"] for item in again] == [items[0]["taskId"]]

    live = service.get(
        project_id,
        from_=BASE - timedelta(days=1),
        to=BASE + timedelta(days=1),
        now=calculated_at + timedelta(hours=1),
    )
    assert live["sample"]["failed"] == 2


def test_interval_start_narrows_to_one_bucket(tmp_path):
    factory, project_id, automation, coordinator = _project(tmp_path, 2)
    first_bucket = datetime(2026, 3, 9, 4, 0, tzinfo=UTC)
    _seed(
        factory,
        project_id,
        automation,
        coordinator,
        status="failed",
        started_at=first_bucket,
        completed_at=first_bucket,
        error={"code": "RUN_FAILED"},
    )
    _seed(
        factory,
        project_id,
        automation,
        coordinator,
        status="failed",
        started_at=first_bucket,
        completed_at=first_bucket + timedelta(days=1),
        error={"code": "RUN_FAILED"},
    )
    service = ProjectStatisticsService(factory)
    stats = service.get(
        project_id,
        from_=first_bucket,
        to=first_bucket + timedelta(days=2),
        timezone="UTC",
        now=first_bucket + timedelta(days=2),
    )
    assert len(stats["trend"]) == 2

    items, total = service.tasks(
        project_id,
        stats["resultSetId"],
        result="failed",
        interval_start=datetime.fromisoformat(stats["trend"][0]["bucketStart"]),
        now=first_bucket + timedelta(days=2),
    )
    assert total == 1 and items[0]["completedAt"] is not None

    with pytest.raises(ProjectError) as outside:
        service.tasks(
            project_id,
            stats["resultSetId"],
            result="failed",
            interval_start=first_bucket - timedelta(days=5),
            now=first_bucket + timedelta(days=2),
        )
    assert outside.value.code == "STATISTICS_RANGE_INVALID"


def test_tampered_and_expired_result_sets(tmp_path):
    factory, project_id, _automation, _coordinator = _project(tmp_path, 0)
    service = ProjectStatisticsService(factory)
    stats = service.get(project_id, now=BASE)

    with pytest.raises(ProjectError) as forged:
        service.tasks(project_id, "bm90LWEtdG9rZW4.deadbeefdeadbeef", result="failed")
    assert forged.value.code == "NOT_FOUND" and forged.value.status == 404

    body, _, mac = stats["resultSetId"].partition(".")
    with pytest.raises(ProjectError) as tampered:
        service.tasks(project_id, f"{body}.{'0' * len(mac)}", result="failed")
    assert tampered.value.code == "NOT_FOUND"

    with pytest.raises(ProjectError) as other_project:
        service.tasks(str(uuid4()), stats["resultSetId"], result="failed")
    assert other_project.value.code == "NOT_FOUND"

    with pytest.raises(ProjectError) as unknown_result:
        service.tasks(project_id, stats["resultSetId"], result="running")
    assert unknown_result.value.code == "VALIDATION_ERROR"

    # 24h TTL: a result set minted two days ago is gone, not silently re-read.
    old = service.get(project_id, now=BASE - timedelta(days=2))
    with pytest.raises(ProjectError) as expired:
        service.tasks(project_id, old["resultSetId"], result="failed")
    assert expired.value.code == "STATISTICS_RESULT_EXPIRED"
    assert expired.value.status == 410


def test_http_routes_serve_the_frozen_dto(tmp_path):
    factory, project_id, automation, coordinator = _project(tmp_path, 1)
    _seed(
        factory,
        project_id,
        automation,
        coordinator,
        status="failed",
        started_at=BASE,
        completed_at=BASE + timedelta(seconds=5),
        error={"code": "RUN_FAILED", "message": "节点执行失败"},
    )
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(project_statistics_router(ProjectStatisticsService(factory)))
    client = TestClient(app)

    response = client.get(
        f"/api/v1/projects/{project_id}/statistics",
        params={
            "from": (BASE - timedelta(days=1)).isoformat(),
            "to": (BASE + timedelta(days=1)).isoformat(),
            "timezone": "Asia/Shanghai",
            "interval": "day",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "from",
        "to",
        "timezone",
        "sample",
        "successRate",
        "averageDurationMs",
        "trend",
        "failuresByAutomation",
        "resultSetId",
        "calculatedAt",
        "expiresAt",
    }
    assert body["sample"] == {
        "succeeded": 0,
        "failed": 1,
        "cancelled": 0,
        "timed_out": 0,
        "interrupted": 0,
    }
    assert body["successRate"] == 0
    assert body["averageDurationMs"] == 5000

    drill = client.get(
        f"/api/v1/projects/{project_id}/statistics/{body['resultSetId']}/tasks",
        params={"result": "failed", "page": 1, "pageSize": 50},
    )
    assert drill.status_code == 200, drill.text
    page = drill.json()
    assert page["total"] == 1
    assert page["items"][0]["status"] == "failed"

    assert (
        client.get(
            f"/api/v1/projects/{project_id}/statistics", params={"timezone": "Nope"}
        ).status_code
        == 422
    )
    assert (
        client.get(
            f"/api/v1/projects/{project_id}/statistics/{body['resultSetId']}/tasks",
            params={"result": "failed"},
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/projects/{project_id}/statistics/{body['resultSetId']}"
            "/tasks",
            params={"result": "bogus"},
        ).status_code
        == 422
    )
