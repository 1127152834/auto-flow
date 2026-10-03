"""Timed and webhook triggers for automations (remediation M2 R2-25/R2-26/R2-27).

Every trigger has a key (the planned time, or the caller's event id) that is
unique per schedule and also derives the batch start's idempotency key, so a
restart, a repeated webhook delivery or two ticks can never start a trigger
twice. Batches start through the same coordinator use case as a person would.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_automations.schedule import (
    ScheduleError,
    due_triggers,
    parse_cron,
    validate_schedule,
)
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_run_models import ProjectBatchRow
from autoflow.infrastructure.database.schedule_models import (
    AutomationScheduleRow,
    AutomationScheduleTriggerRow,
)

_LOG = logging.getLogger(__name__)
TERMINAL = {"completed", "stopped", "failed", "interrupted"}
RECENT_TRIGGERS = 10


class AutomationScheduleService:
    POLL_SECONDS = 30

    def __init__(self, factory: sessionmaker[Session], coordinator: Any, *, scheduler: Any | None = None) -> None:
        self._factory, self._coordinator, self._scheduler = factory, coordinator, scheduler
        self._loop: asyncio.Task[None] | None = None

    async def startup(self) -> None:
        if self._loop is None:
            self._loop = asyncio.create_task(self._run())

    async def shutdown(self) -> None:
        if self._loop is not None:
            self._loop.cancel()
            await asyncio.gather(self._loop, return_exceptions=True)
            self._loop = None

    async def _run(self) -> None:
        while True:
            try:
                # Starting a batch writes SQLite; keep it off the event loop (remediation rule 3).
                started = await asyncio.to_thread(self.tick)
                if started and self._scheduler is not None:
                    self._scheduler.wake()
            except Exception:  # noqa: BLE001 -- durable triggers retry on the next poll.
                _LOG.exception("Automation schedule polling failed")
            await asyncio.sleep(self.POLL_SECONDS)

    # -- management -------------------------------------------------------
    def schedules(self, project_id: str, automation_id: str) -> list[dict[str, Any]]:
        with self._factory() as session:
            _automation(session, project_id, automation_id)
            rows = session.scalars(
                select(AutomationScheduleRow)
                .where(AutomationScheduleRow.automation_id == automation_id)
                .order_by(AutomationScheduleRow.created_at, AutomationScheduleRow.id)
            )
            return [_view(row) for row in rows]

    def create(self, project_id: str, automation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        value = _validated(payload)
        now = datetime.now(UTC)
        secret = secrets.token_urlsafe(24) if value["kind"] == "webhook" else None
        with self._factory.begin() as session:
            _automation(session, project_id, automation_id)
            row = AutomationScheduleRow(
                id=str(uuid4()), project_id=project_id, automation_id=automation_id, kind=value["kind"],
                cron=value["cron"], timezone=value["timezone"], overlap=value["overlap"], missed=value["missed"],
                enabled=value["enabled"], parameters=value["parameters"], max_tasks=value["maxTasks"],
                concurrency=value["concurrency"], webhook_secret_hash=_hash(secret) if secret else None,
                last_fire_at=None, revision=1, created_at=now, updated_at=now,
            )
            session.add(row)
            session.flush()
            view = _view(row)
        # The secret is shown once; only its hash is stored.
        return {**view, **({"webhookSecret": secret} if secret else {})}

    def update(
        self, project_id: str, automation_id: str, schedule_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        value = _validated(payload)
        with self._factory.begin() as session:
            row = _schedule(session, project_id, automation_id, schedule_id)
            if row.revision != expected_revision:
                raise ProjectError("REVISION_CONFLICT", "调度已被修改，请刷新后再试", 409, {"currentRevision": row.revision})
            if value["kind"] != row.kind:
                raise ProjectError("VALIDATION_ERROR", "不能改变触发方式，请新建调度", 422)
            row.cron, row.timezone, row.overlap, row.missed = value["cron"], value["timezone"], value["overlap"], value["missed"]
            row.enabled, row.parameters = value["enabled"], value["parameters"]
            row.max_tasks, row.concurrency = value["maxTasks"], value["concurrency"]
            row.revision += 1
            row.updated_at = datetime.now(UTC)
            session.flush()
            return _view(row)

    def delete(self, project_id: str, automation_id: str, schedule_id: str) -> None:
        with self._factory.begin() as session:
            row = _schedule(session, project_id, automation_id, schedule_id)
            session.execute(delete(AutomationScheduleTriggerRow).where(AutomationScheduleTriggerRow.schedule_id == row.id))
            session.delete(row)

    def triggers(self, project_id: str, automation_id: str, schedule_id: str) -> list[dict[str, Any]]:
        with self._factory() as session:
            _schedule(session, project_id, automation_id, schedule_id)
            rows = session.scalars(
                select(AutomationScheduleTriggerRow)
                .where(AutomationScheduleTriggerRow.schedule_id == schedule_id)
                .order_by(AutomationScheduleTriggerRow.received_at.desc(), AutomationScheduleTriggerRow.id.desc())
                .limit(RECENT_TRIGGERS)
            )
            return [_trigger_view(row) for row in rows]

    # -- firing -----------------------------------------------------------
    def tick(self, now: datetime | None = None) -> list[str]:
        """Start due timed triggers and queued ones; returns the batch ids started."""
        now = now or datetime.now(UTC)
        started: list[str] = []
        with self._factory() as session:
            schedules = [
                (row.id, row.project_id, row.automation_id, row.cron, row.timezone, row.missed, _aware(row.last_fire_at))
                for row in session.scalars(
                    select(AutomationScheduleRow).where(
                        AutomationScheduleRow.enabled.is_(True), AutomationScheduleRow.kind == "cron"
                    )
                )
            ]
        for schedule_id, project_id, automation_id, cron, timezone, missed, last in schedules:
            started.extend(self._drain_queue(schedule_id))
            for planned in due_triggers(parse_cron(cron or ""), timezone, last, now, missed=missed):
                batch_id = self._fire(schedule_id, f"cron:{planned.isoformat()}", planned, now)
                if batch_id:
                    started.append(batch_id)
        return started

    def webhook(
        self, project_id: str, automation_id: str, schedule_id: str, secret: str | None, event_id: str
    ) -> dict[str, Any]:
        if not isinstance(event_id, str) or not event_id.strip() or len(event_id) > 200:
            raise ProjectError("VALIDATION_ERROR", "需要来源事件编号", 422)
        with self._factory() as session:
            row = _schedule(session, project_id, automation_id, schedule_id)
            expected = row.webhook_secret_hash
            if row.kind != "webhook" or expected is None or not hmac.compare_digest(_hash(secret or ""), expected):
                raise ProjectError("WEBHOOK_SECRET_INVALID", "Webhook 密钥无效", 403)
            if not row.enabled:
                raise ProjectError("SCHEDULE_DISABLED", "调度已停用", 409)
        key = f"webhook:{event_id.strip()}"
        self._fire(schedule_id, key, None, datetime.now(UTC))
        with self._factory() as session:
            trigger = session.scalar(select(AutomationScheduleTriggerRow).where(
                AutomationScheduleTriggerRow.schedule_id == schedule_id, AutomationScheduleTriggerRow.trigger_key == key))
            return _trigger_view(trigger) if trigger else {}

    def _fire(self, schedule_id: str, key: str, planned: datetime | None, now: datetime) -> str | None:
        with self._factory.begin() as session:
            row = session.get(AutomationScheduleRow, schedule_id)
            if row is None:
                return None
            last = _aware(row.last_fire_at)
            if planned is not None and (last is None or planned > last):
                row.last_fire_at = planned
            trigger = AutomationScheduleTriggerRow(
                id=str(uuid4()), schedule_id=schedule_id, trigger_key=key, planned_at=planned,
                received_at=now, state="pending", batch_id=None, reason=None,
            )
            try:
                with session.begin_nested():
                    session.add(trigger)
            except IntegrityError:
                return None  # this trigger was already handled
            active = _active_batch(session, schedule_id)
            if active and row.overlap == "skip":
                trigger.state, trigger.reason = "skipped", "上一批仍在运行，按设置跳过本次触发"
                return None
            if active and row.overlap == "queue":
                trigger.state, trigger.reason = "queued", "上一批仍在运行，结束后开始"
                return None
            trigger_id = trigger.id
        return self._start(schedule_id, trigger_id, key)

    def _drain_queue(self, schedule_id: str) -> list[str]:
        with self._factory() as session:
            if _active_batch(session, schedule_id):
                return []
            queued = session.scalar(
                select(AutomationScheduleTriggerRow)
                .where(AutomationScheduleTriggerRow.schedule_id == schedule_id, AutomationScheduleTriggerRow.state == "queued")
                .order_by(AutomationScheduleTriggerRow.received_at, AutomationScheduleTriggerRow.id)
                .limit(1)
            )
            if queued is None:
                return []
            trigger_id, key = queued.id, queued.trigger_key
        batch_id = self._start(schedule_id, trigger_id, key)
        return [batch_id] if batch_id else []

    def _start(self, schedule_id: str, trigger_id: str, key: str) -> str | None:
        with self._factory() as session:
            row = session.get(AutomationScheduleRow, schedule_id)
            automation = session.get(ProjectAutomationRow, row.automation_id) if row else None
            if row is None or automation is None:
                return None
            payload: dict[str, Any] = {
                "expectedAutomationRevision": automation.management_revision,
                "parameters": dict(row.parameters or {}),
                "concurrency": row.concurrency,
            }
            if row.max_tasks is not None:
                payload["maxTasks"] = row.max_tasks
            project_id, automation_id = row.project_id, row.automation_id
        idempotency = str(uuid5(NAMESPACE_URL, f"autoflow:schedule:{schedule_id}:{key}"))
        batch_id: str | None = None
        state, reason = "started", None
        try:
            batch = self._coordinator.start(project_id, automation_id, idempotency, payload)[0]
            batch_id = batch.batch_id
        except (ProjectRunError, ProjectError) as error:
            state, reason = "failed", f"启动失败：{error.message}"
        with self._factory.begin() as session:
            trigger = session.get(AutomationScheduleTriggerRow, trigger_id)
            if trigger is not None:
                trigger.state, trigger.batch_id, trigger.reason = state, batch_id, reason
        return batch_id


def _validated(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return validate_schedule(payload)
    except ScheduleError as error:
        raise ProjectError("VALIDATION_ERROR", error.message, 422, {"fields": {error.field: error.message}}) from error


def _automation(session: Session, project_id: str, automation_id: str) -> ProjectAutomationRow:
    row = session.get(ProjectAutomationRow, automation_id)
    if row is None or row.project_id != project_id:
        raise ProjectError("NOT_FOUND", "自动化不存在", 404)
    return row


def _schedule(session: Session, project_id: str, automation_id: str, schedule_id: str) -> AutomationScheduleRow:
    row = session.get(AutomationScheduleRow, schedule_id)
    if row is None or row.project_id != project_id or row.automation_id != automation_id:
        raise ProjectError("NOT_FOUND", "调度不存在", 404)
    return row


def _active_batch(session: Session, schedule_id: str) -> bool:
    batch_ids = [
        value for value in session.scalars(
            select(AutomationScheduleTriggerRow.batch_id).where(
                AutomationScheduleTriggerRow.schedule_id == schedule_id,
                AutomationScheduleTriggerRow.batch_id.is_not(None),
            )
        ) if value
    ]
    if not batch_ids:
        return False
    statuses = session.scalars(select(ProjectBatchRow.status).where(ProjectBatchRow.id.in_(batch_ids)))
    return any(status not in TERMINAL for status in statuses)


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def _view(row: AutomationScheduleRow) -> dict[str, Any]:
    return {
        "scheduleId": row.id, "projectId": row.project_id, "automationId": row.automation_id, "kind": row.kind,
        "cron": row.cron, "timezone": row.timezone, "overlap": row.overlap, "missed": row.missed,
        "enabled": row.enabled, "parameters": row.parameters, "maxTasks": row.max_tasks,
        "concurrency": row.concurrency, "lastFireAt": _aware(row.last_fire_at), "revision": row.revision,
    }


def _trigger_view(row: AutomationScheduleTriggerRow) -> dict[str, Any]:
    planned = _aware(row.planned_at)
    return {
        "triggerId": row.id, "kind": "cron" if row.trigger_key.startswith("cron:") else "webhook",
        "plannedAt": planned.isoformat() if planned else None, "receivedAt": _aware(row.received_at),
        "state": row.state, "batchId": row.batch_id, "reason": row.reason,
    }
