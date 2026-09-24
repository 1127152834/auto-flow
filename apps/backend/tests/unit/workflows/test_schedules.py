from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.schedules import (
    WorkflowScheduleService,
    next_occurrence,
)
from autoflow.domain.workflows.models import WorkflowError
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_schedules import (
    SqlAlchemyWorkflowSchedules,
)


class Files:
    def load(self, filename: str, folder: str | None = None):
        del folder
        assert filename == "daily.json"
        return {
            "name": "每日流程",
            "nodes": [{"id": "one", "type": "set_variable", "data": {"moduleType": "set_variable", "name": "x", "value": 1}}],
            "edges": [],
            "variables": [],
        }


class Commands:
    def __init__(self) -> None:
        self.starts: list[tuple[str, dict]] = []
        self.stops: list[tuple[str, str]] = []
        self.on_stop = None

    async def start(self, workflow_id: str, request: dict):
        self.starts.append((workflow_id, request))
        return {"runId": request["runId"], "status": "running"}

    async def stop(self, workflow_id: str, run_id: str):
        self.stops.append((workflow_id, run_id))
        if self.on_stop is not None:
            self.on_stop()
        return {"runId": run_id, "status": "stopping"}


class Runs:
    def __init__(self) -> None:
        self.status = "running"
        self.statuses: dict[str, str] = {}

    def get(self, run_id: str):
        return SimpleNamespace(
            run_id=run_id,
            status=self.statuses.get(run_id, self.status),
            error=None,
        )


class Notifier:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, dict]] = []

    async def notify(self, task: dict, **details):
        self.calls.append((task, details))
        return [{"type": "webhook", "success": True}]


@pytest.mark.asyncio
async def test_execution_command_is_idempotent_and_persists_terminal_log(tmp_path) -> None:
    database = tmp_path / "scheduled.db"
    migrate_database(database)
    repository = SqlAlchemyWorkflowSchedules(create_session_factory(database))
    commands, runs = Commands(), Runs()
    service = WorkflowScheduleService(repository, Files(), commands, runs)
    task = service.create(
        {
            "name": "每日任务",
            "workflow_id": "daily.json",
            "profile_id": "profile-main",
            "enabled": True,
            "trigger": {"type": "time", "schedule_type": "daily", "daily_time": "08:00:00"},
        }
    )

    first = await service.execute(task["id"], command_id="execute-once")
    repeated = await service.execute(task["id"], command_id="execute-once")
    assert repeated == first
    assert service.command("execute-once") == first
    assert len(commands.starts) == 1
    assert commands.starts[0][1]["profileId"] == "profile-main"
    assert commands.starts[0][1]["document"]["id"] == "daily.json"
    with pytest.raises(WorkflowError) as duplicate:
        await service.execute(task["id"], command_id="different-command")
    assert duplicate.value.code == "SCHEDULED_TASK_RUNNING"

    runs.status = "completed"
    for _ in range(20):
        if service.logs(task["id"], 10)[0]["status"] == "success":
            break
        await asyncio.sleep(0.05)
    assert service.logs(task["id"], 10)[0]["status"] == "success"
    assert service.statistics()["success_executions"] == 1
    await service.shutdown()


@pytest.mark.asyncio
async def test_webhook_path_is_normalized_and_command_is_idempotent(tmp_path) -> None:
    database = tmp_path / "scheduled.db"
    migrate_database(database)
    repository = SqlAlchemyWorkflowSchedules(create_session_factory(database))
    commands, runs = Commands(), Runs()
    service = WorkflowScheduleService(repository, Files(), commands, runs)
    task = service.create(
        {
            "name": "Webhook任务",
            "workflow_id": "daily.json",
            "profile_id": "profile-main",
            "trigger": {"type": "webhook", "webhook_path": "/Orders/Ready"},
        }
    )

    first = await service.trigger_webhook("orders/ready/", command_id="delivery-1")
    repeated = await service.trigger_webhook("/ORDERS/READY", command_id="delivery-1")

    assert repeated == first
    assert len(commands.starts) == 1
    assert service.get(task["id"])["next_execution_time"] is None
    runs.status = "completed"
    await service.shutdown()


@pytest.mark.asyncio
async def test_terminal_result_dispatches_notification_without_changing_run_truth(tmp_path) -> None:
    database = tmp_path / "scheduled.db"
    migrate_database(database)
    repository = SqlAlchemyWorkflowSchedules(create_session_factory(database))
    commands, runs, notifier = Commands(), Runs(), Notifier()
    service = WorkflowScheduleService(repository, Files(), commands, runs, notifier=notifier)
    task = service.create(
        {
            "name": "通知任务",
            "workflow_id": "daily.json",
            "profile_id": "profile-main",
            "notify_on_success": True,
            "notify_channels": [{"type": "webhook", "url": "{{cred:通知.url}}"}],
            "trigger": {"type": "webhook", "webhook_path": "/notify"},
        }
    )
    await service.execute(task["id"], command_id="notify-1")
    runs.status = "completed"
    for _ in range(20):
        if service.logs(task["id"], 1)[0]["status"] == "success":
            break
        await asyncio.sleep(0.05)

    log = service.logs(task["id"], 1)[0]
    assert log["status"] == "success"
    assert log["notification_results"] == [{"type": "webhook", "success": True}]
    assert notifier.calls[0][1]["status"] == "success"
    await service.shutdown()


def test_notification_secrets_must_use_managed_credential_references(tmp_path) -> None:
    database = tmp_path / "scheduled.db"
    migrate_database(database)
    service = WorkflowScheduleService(
        SqlAlchemyWorkflowSchedules(create_session_factory(database))
    )
    with pytest.raises(WorkflowError) as error:
        service.create(
            {
                "name": "泄露任务",
                "workflow_id": "daily.json",
                "notify_channels": [{"type": "email", "password": "plaintext"}],
                "trigger": {"type": "startup", "startup_delay": 0},
            }
        )
    assert getattr(error.value, "code", None) == "SCHEDULED_TASK_NOTIFICATION_SECRET_REQUIRED"


@pytest.mark.asyncio
async def test_shutdown_stops_active_run_before_monitor_cleanup(tmp_path) -> None:
    database = tmp_path / "scheduled.db"
    migrate_database(database)
    repository = SqlAlchemyWorkflowSchedules(create_session_factory(database))
    commands, runs = Commands(), Runs()
    service = WorkflowScheduleService(repository, Files(), commands, runs)
    task = service.create(
        {
            "name": "任务",
            "workflow_id": "daily.json",
            "profile_id": "profile-main",
            "trigger": {"type": "startup", "startup_delay": 0},
        }
    )
    started = await service.execute(task["id"], command_id="shutdown-run")
    commands.on_stop = lambda: setattr(runs, "status", "stopped")

    await service.shutdown()

    assert commands.stops == [("daily.json", started["run_id"])]


@pytest.mark.asyncio
async def test_stop_returns_after_scheduled_execution_is_terminal(tmp_path) -> None:
    database = tmp_path / "scheduled.db"
    migrate_database(database)
    repository = SqlAlchemyWorkflowSchedules(create_session_factory(database))
    commands, runs = Commands(), Runs()
    service = WorkflowScheduleService(repository, Files(), commands, runs)
    task = service.create(
        {
            "name": "任务",
            "workflow_id": "daily.json",
            "profile_id": "profile-main",
            "trigger": {"type": "startup", "startup_delay": 0},
        }
    )
    await service.execute(task["id"], command_id="stop-run")
    commands.on_stop = lambda: setattr(runs, "status", "stopped")

    stopped = await service.stop(task["id"])

    assert stopped["status"] == "stopped"
    assert service.get(task["id"])["is_running"] is False
    assert service.logs(task["id"], 1)[0]["status"] == "stopped"
    await service.shutdown()


@pytest.mark.asyncio
async def test_distinct_tasks_queue_persistently_behind_active_run(tmp_path) -> None:
    database = tmp_path / "scheduled.db"
    migrate_database(database)
    repository = SqlAlchemyWorkflowSchedules(create_session_factory(database))
    commands, runs = Commands(), Runs()
    service = WorkflowScheduleService(repository, Files(), commands, runs)
    payload = {
        "workflow_id": "daily.json",
        "profile_id": "profile-main",
        "trigger": {"type": "webhook", "webhook_path": "/queue"},
    }
    first_task = service.create({**payload, "name": "队列一"})
    second_task = service.create(
        {
            **payload,
            "name": "队列二",
            "trigger": {"type": "webhook", "webhook_path": "/queue-2"},
        }
    )

    first = await service.execute(first_task["id"], command_id="queue-first")
    second = await service.execute(second_task["id"], command_id="queue-second")

    assert first["status"] == "running"
    assert second["status"] == "queued"
    assert len(commands.starts) == 1
    runs.statuses[str(first["run_id"])] = "completed"
    for _ in range(20):
        if service.command("queue-first")["status"] == "success":
            break
        await asyncio.sleep(0.05)
    await service.tick()
    assert service.command("queue-second")["status"] == "running"
    assert len(commands.starts) == 2
    runs.statuses[str(service.command("queue-second")["run_id"])] = "completed"
    await service.shutdown()


@pytest.mark.asyncio
async def test_repeat_trigger_is_durable_and_uses_stable_occurrence_ids(tmp_path) -> None:
    database = tmp_path / "scheduled.db"
    migrate_database(database)
    repository = SqlAlchemyWorkflowSchedules(create_session_factory(database))
    commands, runs = Commands(), Runs()
    service = WorkflowScheduleService(repository, Files(), commands, runs)
    task = service.create(
        {
            "name": "重复任务",
            "workflow_id": "daily.json",
            "profile_id": "profile-main",
            "trigger": {
                "type": "webhook",
                "webhook_path": "/repeat",
                "repeat_enabled": True,
                "repeat_count": 2,
                "repeat_interval": 1,
            },
        }
    )
    first = await service.execute(task["id"], command_id="repeat-root")
    runs.statuses[str(first["run_id"])] = "completed"
    for _ in range(20):
        logs = service.logs(task["id"], 10)
        if logs and logs[0].get("command_id") == "repeat-root:repeat:2":
            break
        await asyncio.sleep(0.05)
    repeat = service.command("repeat-root:repeat:2")
    assert repeat["status"] == "queued"
    assert repeat["repeat_index"] == 2
    await service.shutdown()

    commands2, runs2 = Commands(), Runs()
    resumed = WorkflowScheduleService(repository, Files(), commands2, runs2)
    await resumed.tick(datetime.fromisoformat(repeat["trigger_time"]) + timedelta(seconds=1))
    assert resumed.command("repeat-root:repeat:2")["status"] == "running"
    assert len(commands2.starts) == 1
    runs2.statuses[str(resumed.command("repeat-root:repeat:2")["run_id"])] = "completed"
    await resumed.shutdown()


def test_next_occurrence_uses_china_timezone_and_skips_missed_intervals() -> None:
    after = datetime(2026, 9, 21, 1, 0, tzinfo=UTC)  # 09:00 Asia/Shanghai
    assert next_occurrence(
        {"type": "time", "schedule_type": "daily", "daily_time": "08:30:00"},
        after=after,
        timezone_name="Asia/Shanghai",
    ) == datetime(2026, 9, 22, 0, 30, tzinfo=UTC)
    assert next_occurrence(
        {
            "type": "time",
            "schedule_type": "weekly",
            "weekly_days": [0],
            "weekly_time": "10:00:00",
        },
        after=after,
        timezone_name="Asia/Shanghai",
    ) == datetime(2026, 9, 27, 2, 0, tzinfo=UTC)
    assert next_occurrence(
        {
            "type": "time",
            "schedule_type": "monthly",
            "monthly_day": 31,
            "monthly_time": "10:00:00",
        },
        after=datetime(2026, 9, 30, 3, 0, tzinfo=UTC),
        timezone_name="Asia/Shanghai",
    ) == datetime(2026, 10, 31, 2, 0, tzinfo=UTC)
    assert next_occurrence(
        {"type": "time", "schedule_type": "interval", "interval_seconds": 60},
        after=datetime(2026, 9, 21, 1, 3, 5, tzinfo=UTC),
        previous=datetime(2026, 9, 21, 1, 0, tzinfo=UTC),
        timezone_name="Asia/Shanghai",
    ) == datetime(2026, 9, 21, 1, 4, tzinfo=UTC)


@pytest.mark.asyncio
async def test_tick_claims_persisted_occurrence_once_and_honours_quiesce(tmp_path) -> None:
    database = tmp_path / "scheduled.db"
    migrate_database(database)
    repository = SqlAlchemyWorkflowSchedules(create_session_factory(database))
    commands, runs, gate = Commands(), Runs(), QuiesceGate()
    service = WorkflowScheduleService(repository, Files(), commands, runs, gate=gate)
    task = service.create(
        {
            "name": "间隔任务",
            "workflow_id": "daily.json",
            "profile_id": "profile-main",
            "enabled": True,
            "trigger": {"type": "time", "schedule_type": "interval", "interval_seconds": 60},
        },
        now=datetime(2026, 9, 21, 1, 0, tzinfo=UTC),
    )
    due = datetime(2026, 9, 21, 1, 1, tzinfo=UTC)

    assert gate.pause(service.blockers) == []
    await service.tick(due)
    assert commands.starts == []
    gate.resume()

    await service.tick(due)
    await service.tick(due)
    assert len(commands.starts) == 1
    scheduled = service.get(task["id"])
    assert scheduled["next_execution_time"] == datetime(2026, 9, 21, 1, 2, tzinfo=UTC).isoformat()

    runs.status = "completed"
    await service.shutdown()
