"""Automation schedules: 5-field cron with a time zone (remediation M2 R2-25/R2-26).

A planned fire time is the identity of a timed trigger, so a restart can never
start the same planned run twice. ``latestOnly`` catches up with one run for the
most recent missed time; ``ignore`` only fires when the planned time is current.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CURRENT_TOLERANCE = timedelta(seconds=90)
MAX_SEARCH_DAYS = 366 * 5
_FIELDS = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))


class ScheduleError(Exception):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field, self.message = field, message


@dataclass(frozen=True)
class CronSpec:
    minutes: frozenset[int]
    hours: frozenset[int]
    days: frozenset[int]
    months: frozenset[int]
    weekdays: frozenset[int]  # 0 = Sunday
    day_restricted: bool
    weekday_restricted: bool


def _field(text: str, low: int, high: int) -> frozenset[int]:
    values: set[int] = set()
    for part in text.split(","):
        body, _, step_text = part.partition("/")
        try:
            step = int(step_text) if step_text else 1
            if body == "*":
                start, end = low, high
            elif "-" in body:
                start_text, end_text = body.split("-", 1)
                start, end = int(start_text), int(end_text)
            else:
                start = end = int(body)
        except ValueError as error:
            raise ScheduleError("cron", "定时表达式无效") from error
        if step < 1 or start > end or start < low or end > high:
            raise ScheduleError("cron", "定时表达式超出范围")
        values.update(range(start, end + 1, step))
    return frozenset(values)


def parse_cron(expression: str) -> CronSpec:
    parts = expression.split() if isinstance(expression, str) else []
    if len(parts) != 5:
        raise ScheduleError("cron", "定时表达式需要 5 段：分 时 日 月 周")
    minutes, hours, days, months, weekdays = (_field(part, low, high) for part, (low, high) in zip(parts, _FIELDS, strict=True))
    return CronSpec(minutes, hours, days, months, weekdays, day_restricted=parts[2] != "*", weekday_restricted=parts[4] != "*")


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ScheduleError("timezone", "时区无效") from error


def _day_matches(spec: CronSpec, day: datetime) -> bool:
    weekday = (day.weekday() + 1) % 7
    in_day, in_week = day.day in spec.days, weekday in spec.weekdays
    if spec.day_restricted and spec.weekday_restricted:
        return in_day or in_week  # standard cron: either restriction matches
    return in_day and in_week


def next_fire(spec: CronSpec, timezone: str, after: datetime) -> datetime | None:
    """First planned instant strictly after ``after``, in UTC."""
    zone = _zone(timezone)
    local = after.astimezone(zone).replace(second=0, microsecond=0, tzinfo=None) + timedelta(minutes=1)
    day = local.replace(hour=0, minute=0)
    for offset in range(MAX_SEARCH_DAYS):
        current = day + timedelta(days=offset)
        if current.month not in spec.months or not _day_matches(spec, current):
            continue
        for hour in sorted(spec.hours):
            for minute in sorted(spec.minutes):
                candidate = current.replace(hour=hour, minute=minute)
                if candidate < local:
                    continue
                aware = candidate.replace(tzinfo=zone)
                instant = aware.astimezone(UTC)
                if instant.astimezone(zone).replace(tzinfo=None) != candidate:
                    continue  # a wall-clock time skipped by a DST change
                return instant
    return None


def due_triggers(
    spec: CronSpec, timezone: str, last_fire: datetime | None, now: datetime, *, missed: str
) -> list[datetime]:
    """Planned times to start now. At most one: the latest missed time (latestOnly) or a current one (ignore)."""
    latest: datetime | None = None
    cursor = last_fire if last_fire is not None else now - CURRENT_TOLERANCE
    while True:
        planned = next_fire(spec, timezone, cursor)
        if planned is None or planned > now:
            break
        latest, cursor = planned, planned
    if latest is None:
        return []
    if missed == "ignore" and now - latest > CURRENT_TOLERANCE:
        return []
    return [latest]


Overlap = Literal["skip", "queue", "parallel"]
_KEYS = {"kind", "cron", "timezone", "overlap", "missed", "enabled", "parameters", "maxTasks", "concurrency"}


def validate_schedule(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) - _KEYS or not {"kind", "enabled"} <= set(payload):
        raise ScheduleError("schedule", "调度设置不完整或包含未知字段")
    kind = payload["kind"]
    if kind not in {"cron", "webhook"}:
        raise ScheduleError("kind", "触发方式只能是定时或 Webhook")
    result = {
        "kind": kind,
        "cron": None,
        "timezone": payload.get("timezone") or "Asia/Shanghai",
        "overlap": payload.get("overlap", "skip"),
        "missed": payload.get("missed", "latestOnly"),
        "enabled": payload["enabled"],
        "parameters": payload.get("parameters", {}),
        "maxTasks": payload.get("maxTasks"),
        "concurrency": payload.get("concurrency", 1),
    }
    if type(result["enabled"]) is not bool:
        raise ScheduleError("enabled", "启用状态必须是布尔值")
    if kind == "cron":
        if not isinstance(payload.get("cron"), str):
            raise ScheduleError("cron", "请填写定时表达式")
        parse_cron(payload["cron"])
        result["cron"] = " ".join(payload["cron"].split())
    _zone(result["timezone"])
    if result["overlap"] not in {"skip", "queue", "parallel"}:
        raise ScheduleError("overlap", "重叠策略只能是跳过、排队或并行")
    if result["missed"] not in {"latestOnly", "ignore"}:
        raise ScheduleError("missed", "错过策略只能是补最近一次或忽略")
    if not isinstance(result["parameters"], dict):
        raise ScheduleError("parameters", "参数必须是对象")
    for key in ("maxTasks", "concurrency"):
        value = result[key]
        if value is not None and (type(value) is not int or not 1 <= value <= 100):
            raise ScheduleError(key, "必须是 1–100 的整数")
    return result
