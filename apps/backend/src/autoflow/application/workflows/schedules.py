from __future__ import annotations

import asyncio
import builtins
import calendar
import logging
import re
from collections.abc import Mapping
from contextlib import nullcontext
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Protocol
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from autoflow.application.settings.runtime import QuiesceGate
from autoflow.domain.workflows.models import WorkflowError

_LOG = logging.getLogger(__name__)
DEFAULT_TIMEZONE = "Asia/Shanghai"
_CREDENTIAL_REFERENCE = re.compile(r"^\{\{\s*(?:cred|凭据)\s*[:：]\s*[^{}]+\s*\}\}$")
_NOTIFICATION_SECRET_FIELDS = frozenset({"password", "key", "webhook", "access_token", "secret", "sendkey", "url"})


class WorkflowFiles(Protocol):
    def load(self, filename: str, folder: str | None = None) -> dict[str, Any]: ...


class WorkflowCommands(Protocol):
    async def start(self, workflow_id: str, request: dict[str, Any]) -> Mapping[str, Any]: ...
    async def stop(self, workflow_id: str, run_id: str) -> Mapping[str, Any]: ...


class WorkflowRuns(Protocol):
    def get(self, run_id: str) -> Any: ...


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _clock(value: str | None, fallback: str) -> time:
    try:
        return time.fromisoformat(value or fallback)
    except ValueError as error:
        raise WorkflowError("SCHEDULED_TASK_TRIGGER_INVALID", "计划任务时间格式无效", 422) from error


def _local_candidate(day: date, value: time, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, value, zone).astimezone(UTC)


def next_occurrence(
    trigger: Mapping[str, Any],
    *,
    after: datetime,
    timezone_name: str = DEFAULT_TIMEZONE,
    previous: datetime | None = None,
) -> datetime | None:
    """Return the first scheduled instant strictly after ``after``."""

    if trigger.get("type") != "time":
        return None
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise WorkflowError("SCHEDULED_TASK_TIMEZONE_INVALID", "计划任务时区无效", 422) from error
    after = _aware(after).astimezone(UTC)
    local_after = after.astimezone(zone)
    mode = trigger.get("schedule_type")
    try:
        end_date = date.fromisoformat(str(trigger["end_date"])) if trigger.get("end_date") else None
    except ValueError as error:
        raise WorkflowError("SCHEDULED_TASK_TRIGGER_INVALID", "计划任务结束日期无效", 422) from error

    if mode == "once":
        try:
            once_candidate = _local_candidate(
                date.fromisoformat(str(trigger["start_date"])),
                _clock(str(trigger["start_time"]), "00:00:00"),
                zone,
            )
        except (KeyError, ValueError) as error:
            raise WorkflowError("SCHEDULED_TASK_TRIGGER_INVALID", "一次性任务日期或时间无效", 422) from error
        return once_candidate if once_candidate > after else None

    if mode == "interval":
        seconds = trigger.get("interval_seconds")
        if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds <= 0:
            raise WorkflowError("SCHEDULED_TASK_TRIGGER_INVALID", "间隔秒数必须大于0", 422)
        interval_candidate = _aware(previous).astimezone(UTC) if previous else after
        steps = max(1, int((after - interval_candidate).total_seconds() // seconds) + 1)
        return interval_candidate + timedelta(seconds=steps * seconds)

    candidate: datetime | None = None
    if mode == "daily":
        clock = _clock(str(trigger.get("daily_time") or ""), "08:00:00")
        day = local_after.date()
        candidate = _local_candidate(day, clock, zone)
        if candidate <= after:
            candidate = _local_candidate(day + timedelta(days=1), clock, zone)
    elif mode == "weekly":
        values = trigger.get("weekly_days")
        if not isinstance(values, list) or not values or any(not isinstance(item, int) or item < 0 or item > 6 for item in values):
            raise WorkflowError("SCHEDULED_TASK_TRIGGER_INVALID", "每周任务至少选择一个有效星期", 422)
        clock = _clock(str(trigger.get("weekly_time") or ""), "08:00:00")
        for offset in range(8):
            day = local_after.date() + timedelta(days=offset)
            sunday_based = (day.weekday() + 1) % 7
            value = _local_candidate(day, clock, zone)
            if sunday_based in values and value > after:
                candidate = value
                break
        assert candidate is not None
    elif mode == "monthly":
        day_number = trigger.get("monthly_day")
        if not isinstance(day_number, int) or isinstance(day_number, bool) or not 1 <= day_number <= 31:
            raise WorkflowError("SCHEDULED_TASK_TRIGGER_INVALID", "每月执行日期必须为1到31", 422)
        clock = _clock(str(trigger.get("monthly_time") or ""), "08:00:00")
        year, month = local_after.year, local_after.month
        for _ in range(24):
            if day_number <= calendar.monthrange(year, month)[1]:
                value = _local_candidate(date(year, month, day_number), clock, zone)
                if value > after:
                    candidate = value
                    break
            month += 1
            if month == 13:
                month, year = 1, year + 1
        assert candidate is not None
    else:
        raise WorkflowError("SCHEDULED_TASK_TRIGGER_INVALID", "时间触发方式无效", 422)

    assert candidate is not None
    if end_date and candidate.astimezone(zone).date() > end_date:
        return None
    return candidate


class WorkflowScheduleService:
    def __init__(
        self,
        repository: Any,
        workflow_files: WorkflowFiles | None = None,
        commands: WorkflowCommands | None = None,
        runs: WorkflowRuns | None = None,
        *,
        gate: QuiesceGate | None = None,
        notifier: Any | None = None,
    ) -> None:
        self._repository = repository
        self._files = workflow_files
        self._commands = commands
        self._runs = runs
        self._gate = gate
        self._notifier = notifier
        self._monitors: dict[str, asyncio.Task[None]] = {}
        self._dispatch_lock = asyncio.Lock()
        self._loop: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()
        self._closed = False

    async def startup(self) -> None:
        now = datetime.now(UTC)
        self._repository.recover_interrupted(now)
        for task in self.list():
            if not task["enabled"] or task["is_running"]:
                continue
            trigger = task["trigger"]
            if trigger["type"] == "startup":
                delay = max(0, int(trigger.get("startup_delay") or 0))
                self._repository.set_next_execution(task["id"], now + timedelta(seconds=delay), now)
            elif trigger["type"] == "time":
                current = datetime.fromisoformat(task["next_execution_time"]) if task.get("next_execution_time") else None
                if current is None or _aware(current) <= now:
                    value = next_occurrence(
                        trigger,
                        after=now,
                        previous=current,
                        timezone_name=str(task.get("timezone") or DEFAULT_TIMEZONE),
                    )
                    self._repository.set_next_execution(task["id"], value, now)
        if self._loop is None:
            self._closed = False
            self._loop = asyncio.create_task(self._run())

    def list(self) -> builtins.list[dict[str, Any]]:
        return self._repository.list()

    def get(self, task_id: str) -> dict[str, Any]:
        task = self._repository.get(task_id)
        if task is None:
            raise WorkflowError("SCHEDULED_TASK_NOT_FOUND", "计划任务不存在", 404)
        return task

    def create(self, payload: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
        self._validate(payload)
        self._validate_unique_trigger(payload)
        now = _aware(now or datetime.now(UTC))
        normalized = {
            **payload,
            "timezone": str(payload.get("timezone") or DEFAULT_TIMEZONE),
            "missed_trigger_policy": "skip",
            "total_executions": 0,
            "success_executions": 0,
            "failed_executions": 0,
            "notify_channels": list(payload.get("notify_channels") or []),
        }
        created = self._repository.create(uuid4().hex, normalized, now)
        if created["enabled"]:
            created = self._repository.set_next_execution(created["id"], self._next_for_task(created, now), now)
        self.wake()
        return created

    def update(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.get(task_id)
        changes = dict(payload)
        expected = changes.pop("expected_revision", None)
        merged = {**current, **changes}
        self._validate(merged)
        self._validate_unique_trigger(merged, exclude_task_id=task_id)
        now = datetime.now(UTC)
        updated = self._repository.update(task_id, changes, expected, now)
        if any(key in changes for key in ("trigger", "timezone", "enabled")):
            value = self._next_for_task(updated, now) if updated["enabled"] else None
            updated = self._repository.set_next_execution(task_id, value, now)
        self.wake()
        return updated

    def toggle(self, task_id: str, enabled: bool) -> dict[str, Any]:
        now = datetime.now(UTC)
        updated = self._repository.update(task_id, {"enabled": enabled}, None, now)
        value = self._next_for_task(updated, now) if enabled else None
        updated = self._repository.set_next_execution(task_id, value, now)
        self.wake()
        return updated

    def delete(self, task_id: str) -> None:
        self._repository.delete(task_id)
        self.wake()

    async def execute(
        self,
        task_id: str,
        *,
        command_id: str,
        trigger_type: str = "manual",
        scheduled_for: datetime | None = None,
        next_execution_time: datetime | None = None,
        advance_schedule: bool = False,
        disable_after_claim: bool = False,
    ) -> dict[str, Any]:
        task = self.get(task_id)
        if self._files is None or self._commands is None or self._runs is None:
            raise WorkflowError("SCHEDULED_TASK_RUNTIME_UNAVAILABLE", "计划任务运行服务不可用", 503)
        profile_id = str(task.get("profile_id") or "").strip()
        if not profile_id:
            raise WorkflowError("SCHEDULED_TASK_PROFILE_REQUIRED", "请选择主应用浏览器配置", 422)
        execution_id = uuid4().hex
        now = datetime.now(UTC)
        log = {
            "id": execution_id,
            "task_id": task_id,
            "task_name": task["name"],
            "workflow_id": task["workflow_id"],
            "workflow_name": task.get("workflow_name") or "",
            "start_time": None,
            "status": "queued",
            "trigger_type": trigger_type,
            "trigger_time": _aware(scheduled_for or now).isoformat(),
            "executed_nodes": 0,
            "failed_nodes": 0,
            "collected_data_count": 0,
            "run_id": None,
            "run_status": "queued",
            "command_id": command_id,
            "root_command_id": command_id,
            "repeat_index": 1,
        }
        gate = self._gate.mutation() if self._gate is not None else nullcontext(True)
        with gate as admitted:
            if not admitted:
                raise WorkflowError(
                    "SCHEDULED_TASK_ADMISSION_CLOSED", "计划任务准入已关闭", 503
                )
            existing, created = self._repository.enqueue_execution(
                task_id,
                execution_id,
                command_id,
                log,
                now,
                next_execution_time=next_execution_time,
                advance_schedule=advance_schedule,
                disable_after_claim=disable_after_claim,
            )
            if not created:
                return existing
            await self._dispatch_pending(now)
            return self.command(command_id)

    async def _dispatch_pending(self, now: datetime | None = None) -> None:
        if self._files is None or self._commands is None or self._runs is None:
            return
        async with self._dispatch_lock:
            claimed = self._repository.claim_next(_aware(now or datetime.now(UTC)))
            if claimed is None:
                return
            execution_id = str(claimed["id"])
            task_id = str(claimed["task_id"])
            task = self.get(task_id)
            run_id = f"schedule-{execution_id}-{uuid4().hex[:8]}"
            try:
                document = {
                    **self._files.load(task["workflow_id"]),
                    "id": task["workflow_id"],
                }
                started = await self._commands.start(
                    task["workflow_id"],
                    {
                        "runId": run_id,
                        "documentId": task["workflow_id"],
                        "profileId": str(task["profile_id"]),
                        "headless": bool(task.get("headless", False)),
                        "document": document,
                    },
                )
            except Exception as error:
                if getattr(error, "code", None) in {
                    "WORKFLOW_RUN_BUSY",
                    "WORKFLOW_BROWSER_BUSY",
                }:
                    self._repository.requeue_execution(
                        execution_id,
                        due_at=datetime.now(UTC) + timedelta(seconds=1),
                        now=datetime.now(UTC),
                    )
                    self.wake()
                    return
                self._repository.finish_execution(
                    execution_id,
                    status="failed",
                    error=str(error),
                    run_id=None,
                    now=datetime.now(UTC),
                )
                raise
            attached = self._repository.attach_run(
                execution_id,
                run_id=run_id,
                run_status=str(started.get("status") or "running"),
                now=datetime.now(UTC),
            )
            self._monitors[execution_id] = asyncio.create_task(
                self._monitor(
                    execution_id,
                    task_id,
                    run_id,
                    str(attached["start_time"]),
                )
            )

    async def tick(self, now: datetime | None = None) -> None:
        now = _aware(now or datetime.now(UTC))
        gate = self._gate.mutation() if self._gate is not None else nullcontext(True)
        with gate as admitted:
            if not admitted:
                return
            for task in self._repository.due(now):
                scheduled_for = datetime.fromisoformat(task["next_execution_time"])
                trigger = task["trigger"]
                if trigger["type"] == "time":
                    next_time = next_occurrence(
                        trigger,
                        after=now,
                        previous=scheduled_for,
                        timezone_name=str(task.get("timezone") or DEFAULT_TIMEZONE),
                    )
                    disable = trigger.get("schedule_type") == "once" and next_time is None
                else:
                    next_time, disable = None, False
                occurrence = f"{trigger['type']}:{_aware(scheduled_for).isoformat()}"
                try:
                    await self.execute(
                        task["id"],
                        command_id=occurrence,
                        trigger_type=str(trigger["type"]),
                        scheduled_for=scheduled_for,
                        next_execution_time=next_time,
                        advance_schedule=True,
                        disable_after_claim=disable,
                    )
                except WorkflowError as error:
                    if error.code != "SCHEDULED_TASK_RUNNING":
                        _LOG.exception("Scheduled workflow could not start")
                except Exception:  # noqa: BLE001 - persisted failure remains queryable
                    _LOG.exception("Scheduled workflow could not start")
            await self._dispatch_pending(now)

    def command(self, command_id: str) -> dict[str, Any]:
        value = self._repository.execution_by_occurrence(command_id)
        if value is None:
            raise WorkflowError("SCHEDULED_COMMAND_NOT_FOUND", "计划任务命令不存在", 404)
        return value

    async def trigger_webhook(self, path: str, *, command_id: str) -> dict[str, Any]:
        normalized = self._normalize_webhook(path)
        task = next(
            (
                item for item in self.list()
                if item["enabled"]
                and item["trigger"]["type"] == "webhook"
                and self._normalize_webhook(str(item["trigger"].get("webhook_path") or "")) == normalized
            ),
            None,
        )
        if task is None:
            raise WorkflowError("SCHEDULED_WEBHOOK_NOT_FOUND", "Webhook路径未注册", 404)
        return await self.execute(task["id"], command_id=command_id, trigger_type="webhook")

    def hotkeys(self) -> builtins.list[dict[str, str]]:
        return [
            {"task_id": str(task["id"]), "hotkey": str(task["trigger"]["hotkey"])}
            for task in self.list()
            if task["enabled"] and task["trigger"]["type"] == "hotkey"
        ]

    async def trigger_hotkey(self, task_id: str, *, command_id: str) -> dict[str, Any]:
        task = self.get(task_id)
        if not task["enabled"] or task["trigger"]["type"] != "hotkey":
            raise WorkflowError(
                "SCHEDULED_HOTKEY_NOT_REGISTERED", "计划任务热键未启用", 409
            )
        return await self.execute(task_id, command_id=command_id, trigger_type="hotkey")

    async def stop(self, task_id: str) -> dict[str, Any]:
        task = self.get(task_id)
        running = next((item for item in self._repository.list_logs(task_id, 100) if item.get("status") == "running"), None)
        if running is None:
            queued = self._repository.stop_queued(task_id, datetime.now(UTC))
            if queued is not None:
                return queued
            raise WorkflowError("SCHEDULED_TASK_NOT_RUNNING", "计划任务未在执行", 409)
        if not running.get("run_id"):
            raise WorkflowError("SCHEDULED_TASK_NOT_RUNNING", "计划任务正在启动，请稍后重试", 409)
        assert self._commands is not None
        result = dict(await self._commands.stop(task["workflow_id"], str(running["run_id"])))
        monitor = self._monitors.get(str(running["id"]))
        if monitor is not None:
            await monitor
            return self.command(str(running["command_id"]))
        return result

    def logs(self, task_id: str | None, limit: int) -> builtins.list[dict[str, Any]]:
        return self._repository.list_logs(task_id, limit)

    def clear_logs(self, task_id: str | None) -> None:
        self._repository.clear_logs(task_id)

    def statistics(self) -> dict[str, Any]:
        tasks = self.list()
        total = sum(int(task.get("total_executions", 0)) for task in tasks)
        success = sum(int(task.get("success_executions", 0)) for task in tasks)
        failed = sum(int(task.get("failed_executions", 0)) for task in tasks)
        return {
            "total_tasks": len(tasks),
            "enabled_tasks": sum(task["enabled"] is True for task in tasks),
            "disabled_tasks": sum(task["enabled"] is False for task in tasks),
            "total_executions": total,
            "success_executions": success,
            "failed_executions": failed,
            "success_rate": round(success * 100 / total, 2) if total else 0,
            "trigger_types": {kind: sum(task["trigger"]["type"] == kind for task in tasks) for kind in ("time", "hotkey", "startup", "webhook")},
        }

    def blockers(self) -> builtins.list[str]:
        return ["workflow_schedule_active"] if self._repository.has_pending() else []

    def wake(self) -> None:
        self._wake.set()

    async def _run(self) -> None:
        while not self._closed:
            self._wake.clear()
            try:
                await self.tick()
            except Exception:  # noqa: BLE001 - the next poll retries durable schedules
                _LOG.exception("Scheduled workflow polling failed")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=1)
            except TimeoutError:
                pass

    async def _monitor(
        self, execution_id: str, task_id: str, run_id: str, started_at: str
    ) -> None:
        assert self._runs is not None
        try:
            while True:
                run = self._runs.get(run_id)
                if run.status in {"completed", "failed", "stopped", "interrupted"}:
                    status = "success" if run.status == "completed" else "stopped" if run.status == "stopped" else "failed"
                    error = None if status in {"success", "stopped"} else str(run.error or "工作流执行失败")
                    ended_at = datetime.now(UTC)
                    task = self.get(task_id)
                    notification_results = None
                    if self._notifier is not None:
                        try:
                            notification_results = await self._notifier.notify(
                                task,
                                status=status,
                                started_at=started_at,
                                ended_at=ended_at.isoformat(),
                                error=error,
                            )
                        except Exception:  # noqa: BLE001 - notification failure cannot replace run truth
                            _LOG.exception("Scheduled workflow notification failed")
                    finished = self._repository.finish_execution(
                        execution_id,
                        status=status,
                        error=error,
                        run_id=run_id,
                        now=ended_at,
                        notification_results=notification_results,
                    )
                    self._enqueue_repeat(task, finished, ended_at)
                    self.wake()
                    return
                await asyncio.sleep(0.2)
        finally:
            self._monitors.pop(execution_id, None)

    def _enqueue_repeat(
        self, task: Mapping[str, Any], finished: Mapping[str, Any], now: datetime
    ) -> None:
        trigger = task["trigger"]
        if not trigger.get("repeat_enabled") or finished.get("status") == "stopped":
            return
        current = int(finished.get("repeat_index") or 1)
        count = trigger.get("repeat_count")
        if count is not None and current >= int(count):
            return
        interval = int(trigger.get("repeat_interval") or 0)
        root = str(finished.get("root_command_id") or finished["command_id"])
        repeat_index = current + 1
        execution_id = uuid4().hex
        due_at = now + timedelta(seconds=interval)
        payload = {
            **finished,
            "id": execution_id,
            "status": "queued",
            "trigger_type": "repeat",
            "trigger_time": due_at.isoformat(),
            "start_time": None,
            "end_time": None,
            "duration": None,
            "error": None,
            "run_id": None,
            "run_status": "queued",
            "command_id": f"{root}:repeat:{repeat_index}",
            "root_command_id": root,
            "repeat_index": repeat_index,
            "notification_results": [],
        }
        self._repository.enqueue_execution(
            str(task["id"]),
            execution_id,
            str(payload["command_id"]),
            payload,
            now,
            due_at=due_at,
        )

    async def shutdown(self) -> None:
        self._closed = True
        self.wake()
        if self._loop is not None:
            await self._loop
            self._loop = None
        if self._commands is not None:
            for log in self._repository.list_logs(None, 1000):
                if log.get("status") == "running" and log.get("run_id"):
                    await self._commands.stop(str(log["workflow_id"]), str(log["run_id"]))
        monitors = list(self._monitors.values())
        if monitors:
            try:
                async with asyncio.timeout(30):
                    await asyncio.gather(*monitors, return_exceptions=True)
            except TimeoutError:
                for monitor in monitors:
                    monitor.cancel()
                await asyncio.gather(*monitors, return_exceptions=True)

    def _next_for_task(self, task: Mapping[str, Any], now: datetime) -> datetime | None:
        trigger = task["trigger"]
        if trigger["type"] == "startup":
            return None
        return next_occurrence(trigger, after=now, timezone_name=str(task.get("timezone") or DEFAULT_TIMEZONE))

    @staticmethod
    def _normalize_webhook(path: str) -> str:
        return path.strip().strip("/").lower()

    def _validate_unique_trigger(
        self, payload: Mapping[str, Any], *, exclude_task_id: str | None = None
    ) -> None:
        trigger = payload["trigger"]
        kind = trigger["type"]
        if kind not in {"hotkey", "webhook"}:
            return
        key = (
            str(trigger.get("hotkey") or "").strip().lower()
            if kind == "hotkey"
            else self._normalize_webhook(str(trigger.get("webhook_path") or ""))
        )
        for task in self.list():
            if task["id"] == exclude_task_id or task["trigger"]["type"] != kind:
                continue
            other = (
                str(task["trigger"].get("hotkey") or "").strip().lower()
                if kind == "hotkey"
                else self._normalize_webhook(
                    str(task["trigger"].get("webhook_path") or "")
                )
            )
            if other == key:
                label = "热键" if kind == "hotkey" else "Webhook路径"
                raise WorkflowError(
                    "SCHEDULED_TASK_TRIGGER_CONFLICT",
                    f"{label}已被其他计划任务使用",
                    409,
                )

    @staticmethod
    def _validate(payload: Mapping[str, Any]) -> None:
        if not str(payload.get("name") or "").strip():
            raise WorkflowError("SCHEDULED_TASK_INVALID", "任务名称不能为空", 422)
        if not str(payload.get("workflow_id") or "").strip():
            raise WorkflowError("SCHEDULED_TASK_INVALID", "请选择工作流", 422)
        try:
            ZoneInfo(str(payload.get("timezone") or DEFAULT_TIMEZONE))
        except ZoneInfoNotFoundError as error:
            raise WorkflowError("SCHEDULED_TASK_TIMEZONE_INVALID", "计划任务时区无效", 422) from error
        trigger = payload.get("trigger")
        if not isinstance(trigger, Mapping) or trigger.get("type") not in {"time", "hotkey", "startup", "webhook"}:
            raise WorkflowError("SCHEDULED_TASK_TRIGGER_INVALID", "计划任务触发器无效", 422)
        if trigger["type"] == "time":
            next_occurrence(trigger, after=datetime.now(UTC), timezone_name=str(payload.get("timezone") or DEFAULT_TIMEZONE))
        elif trigger["type"] == "hotkey" and not str(trigger.get("hotkey") or "").strip():
            raise WorkflowError("SCHEDULED_TASK_TRIGGER_INVALID", "计划任务热键不能为空", 422)
        elif trigger["type"] == "startup":
            delay = trigger.get("startup_delay", 0)
            if not isinstance(delay, int) or isinstance(delay, bool) or delay < 0:
                raise WorkflowError("SCHEDULED_TASK_TRIGGER_INVALID", "启动延迟必须为非负整数", 422)
        elif trigger["type"] == "webhook":
            path = str(trigger.get("webhook_path") or "")
            if not path.startswith("/") or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/" for character in path):
                raise WorkflowError("SCHEDULED_TASK_TRIGGER_INVALID", "Webhook路径格式无效", 422)
        if trigger.get("repeat_enabled"):
            count = trigger.get("repeat_count")
            interval = trigger.get("repeat_interval")
            if count is not None and (not isinstance(count, int) or isinstance(count, bool) or count <= 0):
                raise WorkflowError("SCHEDULED_TASK_TRIGGER_INVALID", "重复次数必须大于0", 422)
            if not isinstance(interval, int) or isinstance(interval, bool) or interval <= 0:
                raise WorkflowError("SCHEDULED_TASK_TRIGGER_INVALID", "重复间隔必须大于0", 422)
        channels = payload.get("notify_channels") or []
        if not isinstance(channels, list):
            raise WorkflowError("SCHEDULED_TASK_NOTIFICATION_INVALID", "通知渠道配置无效", 422)
        for channel in channels:
            if not isinstance(channel, Mapping) or channel.get("type") not in {"email", "wecom", "dingtalk", "serverchan", "webhook"}:
                raise WorkflowError("SCHEDULED_TASK_NOTIFICATION_INVALID", "通知渠道配置无效", 422)
            for key in _NOTIFICATION_SECRET_FIELDS:
                value = channel.get(key)
                if value and not _CREDENTIAL_REFERENCE.fullmatch(str(value)):
                    raise WorkflowError(
                        "SCHEDULED_TASK_NOTIFICATION_SECRET_REQUIRED",
                        "通知密码、令牌和Webhook地址必须引用凭据库",
                        422,
                        details={"field": key},
                    )
