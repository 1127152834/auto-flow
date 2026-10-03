"""Remediation M2 R2-25/R2-26: cron schedules with a time zone and trigger planning."""

from datetime import UTC, datetime

import pytest

from autoflow.domain.project_automations.schedule import (
    ScheduleError,
    due_triggers,
    next_fire,
    parse_cron,
    validate_schedule,
)


def at(text):
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


@pytest.mark.parametrize(
    ("expression", "after", "expected"),
    [
        ("*/15 * * * *", "2026-10-03T08:07:00", "2026-10-03T08:15:00"),
        ("0 9 * * *", "2026-10-03T08:00:00", "2026-10-03T09:00:00"),
        ("0 9 * * *", "2026-10-03T09:00:00", "2026-10-04T09:00:00"),
        ("30 8 * * 1-5", "2026-10-03T10:00:00", "2026-10-05T08:30:00"),  # 10-03 is a Saturday
        ("0 0 1 * *", "2026-10-03T00:00:00", "2026-11-01T00:00:00"),
        ("5,35 * * * *", "2026-10-03T08:06:00", "2026-10-03T08:35:00"),
    ],
)
def test_next_fire_in_utc(expression, after, expected):
    assert next_fire(parse_cron(expression), "UTC", at(after)) == at(expected)


def test_time_zone_decides_the_wall_clock():
    # 09:00 in Shanghai is 01:00 UTC.
    assert next_fire(parse_cron("0 9 * * *"), "Asia/Shanghai", at("2026-10-03T00:00:00")) == at("2026-10-03T01:00:00")


@pytest.mark.parametrize("expression", ["", "* * * *", "61 * * * *", "* 24 * * *", "*/0 * * * *", "a b c d e", "5-1 * * * *"])
def test_invalid_expressions_are_refused(expression):
    with pytest.raises(ScheduleError):
        parse_cron(expression)


def test_latest_only_fires_once_for_missed_runs_and_ignore_fires_none():
    spec = parse_cron("0 * * * *")
    last = at("2026-10-03T01:00:00")
    now = at("2026-10-03T05:00:30")
    assert due_triggers(spec, "UTC", last, now, missed="latestOnly") == [at("2026-10-03T05:00:00")]
    assert due_triggers(spec, "UTC", last, now, missed="ignore") == [at("2026-10-03T05:00:00")]
    late = at("2026-10-03T05:20:00")
    assert due_triggers(spec, "UTC", last, late, missed="latestOnly") == [at("2026-10-03T05:00:00")]
    assert due_triggers(spec, "UTC", last, late, missed="ignore") == []
    assert due_triggers(spec, "UTC", at("2026-10-03T05:00:00"), late, missed="latestOnly") == []


def test_schedule_payload_is_validated():
    good = {"kind": "cron", "cron": "0 9 * * *", "timezone": "Asia/Shanghai", "overlap": "skip", "missed": "latestOnly",
            "enabled": True, "parameters": {}, "maxTasks": 10, "concurrency": 1}
    assert validate_schedule(good)["cron"] == "0 9 * * *"
    assert validate_schedule({**good, "kind": "webhook", "cron": None})["kind"] == "webhook"
    for bad in ({**good, "timezone": "Mars/Base"}, {**good, "overlap": "always"}, {**good, "missed": "all"},
                {**good, "cron": "bad"}, {**good, "maxTasks": 0}, {**good, "extra": 1}):
        with pytest.raises(ScheduleError):
            validate_schedule(bad)
