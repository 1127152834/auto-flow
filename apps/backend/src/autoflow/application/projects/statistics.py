"""Project statistics: a signed, deterministic recomputation window.

The frozen predicate `status ∈ TERMINAL ∧ from ≤ completed_at ≤ min(to, calculatedAt)`
is monotone because terminal Runs never leave their terminal status and
`completed_at` is written exactly once on entering one (see
`domain/workflows/runtime.py`). Recomputing the same `resultSetId` therefore
returns the same set until it expires, with no snapshot table and no migration.

ponytail: results are recomputed, not stored. Add a `project_statistics_results`
table plus one migration only if terminal Runs become correctable, results must
be audited, or a set must outlive the 24h TTL.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.application.project_runs.queries import ProjectRunQueries
from autoflow.application.projects.overview import resolve_timezone
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects, guard_project
from autoflow.infrastructure.database.workflow_models import (
    ScheduledTaskExecutionRow,
    WorkflowRunArtifactRow,
    WorkflowRunEventRow,
)
from autoflow.infrastructure.database.workflow_models import (
    WorkflowRunRow as StudioRunRow,
)
from autoflow.infrastructure.database.workflow_project_scope import (
    studio_run_project_expression,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow

TERMINAL_STATUSES = ("succeeded", "failed", "cancelled", "timed_out", "interrupted")
SAMPLE_KEYS = {
    "succeeded": "succeeded",
    "failed": "failed",
    "cancelled": "cancelled",
    "timed_out": "timed_out",
    "interrupted": "interrupted",
}
INTERVALS = ("day", "week", "month")
DEFAULT_WINDOW = timedelta(days=7)
RESULT_TTL = timedelta(hours=24)


def _secret(session_factory: sessionmaker[Session]) -> bytes:
    configured = os.environ.get("AUTOFLOW_STATISTICS_SECRET")
    if configured:
        return hashlib.sha256(configured.encode()).digest()
    bind = session_factory.kw.get("bind")
    database = getattr(getattr(bind, "url", None), "database", None) or "autoflow"
    return hashlib.sha256(f"autoflow-statistics::{database}".encode()).digest()


class ProjectStatisticsService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        queries: ProjectRunQueries | None = None,
    ) -> None:
        self._factory = session_factory
        self._queries = queries or ProjectRunQueries(session_factory)
        self._secret = _secret(session_factory)

    def studio(
        self, project_id: str, *, from_: datetime | None = None,
        to: datetime | None = None, workflow_id: str | None = None,
        status: str | None = None, cursor: int = 0, limit: int = 50,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Read one transaction of Studio facts, filtered by run start time.

        Active runs may change on refresh; this is not the frozen task result set.
        The result never loads document snapshots, result values or error secrets.
        """
        from typing import get_args

        from autoflow.domain.workflows.runs import RunStatus

        calculated = _aware(now or datetime.now(UTC))
        upper = min(_aware(to), calculated) if to is not None else calculated
        lower = _aware(from_) if from_ is not None else upper - DEFAULT_WINDOW
        if lower > upper or cursor < 0 or not 1 <= limit <= 200 or (status is not None and status not in get_args(RunStatus)):
            raise ProjectError("STATISTICS_RANGE_INVALID", "运行统计筛选无效", 422)
        run, event, artifact = StudioRunRow, WorkflowRunEventRow, WorkflowRunArtifactRow
        query = select(
            run.id.label("runId"), run.workflow_id.label("workflowId"),
            run.payload["workflowName"].as_string().label("workflowName"),
            run.payload["mode"].as_string().label("mode"),
            run.payload["status"].as_string().label("status"),
            run.started_at.label("startedAt"), run.payload["finishedAt"].as_string().label("finishedAt"),
        ).where(
            studio_run_project_expression() == project_id,
            func.julianday(run.started_at) >= func.julianday(lower.isoformat()),
            func.julianday(run.started_at) <= func.julianday(upper.isoformat()),
        )
        if workflow_id is not None:
            query = query.where(run.workflow_id == workflow_id)
        if status is not None:
            query = query.where(run.payload["status"].as_string() == status)
        cohort = query.subquery()
        ids = select(cohort.c.runId)
        events = select(event).where(event.run_id.in_(ids)).subquery()
        event_type = events.c.payload["type"].as_string()
        event_node = events.c.payload["nodeId"].as_string()
        duration = (func.julianday(cohort.c.finishedAt) - func.julianday(cohort.c.startedAt)) * 86400000
        scheduled_source = select(ScheduledTaskExecutionRow.payload["trigger_type"].as_string()).where(
            ScheduledTaskExecutionRow.payload["run_id"].as_string() == cohort.c.runId,
        ).order_by(ScheduledTaskExecutionRow.created_at, ScheduledTaskExecutionRow.id).limit(1).scalar_subquery()
        source = func.coalesce(scheduled_source, "unknown")
        with self._factory() as session:
            session.execute(text("BEGIN"))
            guard_project(session, project_id, writable=False)
            by_status = {state: count for state, count in session.execute(select(cohort.c.status, func.count()).group_by(cohort.c.status))}
            total = sum(by_status.values())
            average = session.scalar(select(func.avg(duration)).where(cohort.c.status.in_(("completed", "failed")), duration >= 0))
            node_count = session.scalar(select(func.count()).select_from(events).where(event_type == "execution:node_start")) or 0
            result_count = session.scalar(select(func.count()).select_from(events).where(
                event_type == "execution:node-succeeded", event_node.is_not(None),
                func.json_type(events.c.payload, "$.payload.result.data").not_in(("null",)),
            )) or 0
            files = {purpose: count for purpose, count in session.execute(select(artifact.purpose, func.count()).where(artifact.run_id.in_(ids)).group_by(artifact.purpose))}
            failures = [{"nodeId": node, "count": count} for node, count in session.execute(
                select(event_node, func.count()).where(event_type == "execution:node-failed", event_node.is_not(None)).group_by(event_node).order_by(func.count().desc(), event_node).limit(10)
            )]
            workflows = [{"workflowId": identifier, "name": name, "count": count} for identifier, name, count in session.execute(
                select(cohort.c.workflowId, func.max(cohort.c.workflowName), func.count()).group_by(cohort.c.workflowId).order_by(func.count().desc(), cohort.c.workflowId).limit(10)
            )]
            triggers = {trigger: count for trigger, count in session.execute(select(source, func.count()).select_from(cohort).group_by(source))}
            debug = session.scalar(select(func.count()).select_from(cohort).where(cohort.c.mode == "debug")) or 0
            run_time = func.coalesce(cohort.c.finishedAt, cohort.c.startedAt)
            event_time = events.c.payload["occurredAt"].as_string()
            latest_run = session.scalar(select(run_time).order_by(func.julianday(run_time).desc()).limit(1))
            latest_event = session.scalar(select(event_time).order_by(func.julianday(event_time).desc()).limit(1))
            items = [dict(row) for row in session.execute(select(cohort).order_by(func.julianday(cohort.c.startedAt).desc(), cohort.c.runId).offset(cursor).limit(limit)).mappings()]
        decided = by_status.get("completed", 0) + by_status.get("failed", 0)
        return {
            "projectId": project_id, "from": lower.isoformat(), "to": upper.isoformat(), "calculatedAt": calculated.isoformat(),
            "totalRuns": total, "byStatus": by_status,
            "successRate": by_status.get("completed", 0) / decided if decided else None,
            "averageDurationMs": round(average) if average is not None else None,
            "nodeExecutionCount": node_count, "extractionExecutionCount": result_count,
            "artifactCount": files.get("result", 0), "diagnosticCount": files.get("diagnostic", 0),
            "debugCount": debug, "recordingCount": None,
            "recordingUnavailableReason": "历史录制尚未保存项目归属，不能据工作区总量推算项目次数",
            "latestActivityAt": max(filter(None, (latest_run, latest_event)), key=lambda value: _aware(datetime.fromisoformat(value)), default=None),
            "failuresByNode": failures, "runsByWorkflow": workflows, "byTrigger": triggers,
            "items": items, "nextCursor": cursor + len(items) if cursor + len(items) < total else None,
        }

    def get(
        self,
        project_id: str,
        *,
        from_: datetime | None = None,
        to: datetime | None = None,
        timezone: str | None = None,
        automation_id: str | None = None,
        table_id: str | None = None,
        interval: str = "day",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if interval not in INTERVALS:
            raise ProjectError("STATISTICS_RANGE_INVALID", f"非法区间 {interval}", 422)
        if SqlAlchemyProjects(self._factory).get(project_id) is None:
            raise ProjectError("NOT_FOUND", "项目不存在", 404)
        zone = resolve_timezone(timezone)
        calculated_at = now or datetime.now(UTC)
        upper = _aware(to) if to is not None else calculated_at
        lower = _aware(from_) if from_ is not None else upper - DEFAULT_WINDOW
        if lower > upper:
            raise ProjectError(
                "STATISTICS_RANGE_INVALID", "开始时间不能晚于结束时间", 422
            )
        frozen_upper = min(upper, calculated_at)
        with self._factory() as session:
            rows = _frozen_rows(
                session,
                project_id,
                lower=lower,
                upper=frozen_upper,
                automation_id=automation_id,
                table_id=table_id,
            )
            names = _automation_names(session, {row["automationId"] for row in rows})
        sample = dict.fromkeys(TERMINAL_STATUSES, 0)
        for row in rows:
            sample[SAMPLE_KEYS[row["status"]]] += 1
        decided = sample["succeeded"] + sample["failed"]
        durations = [
            row["durationMs"]
            for row in rows
            if row["durationMs"] is not None
            and row["status"] in ("succeeded", "failed")
        ]
        payload = {
            "projectId": project_id,
            "from": lower.isoformat(),
            "to": upper.isoformat(),
            "timezone": str(zone),
            "automationId": automation_id,
            "tableId": table_id,
            "interval": interval,
            "calculatedAt": calculated_at.isoformat(),
        }
        return {
            "from": lower.isoformat(),
            "to": upper.isoformat(),
            "timezone": str(zone),
            "sample": sample,
            "successRate": (sample["succeeded"] / decided) if decided else None,
            "averageDurationMs": _mean_ms(durations),
            "trend": _trend(rows, zone, interval),
            "failuresByAutomation": _failures(rows, names),
            "resultSetId": _sign(payload, self._secret),
            "calculatedAt": calculated_at.isoformat(),
            "expiresAt": (calculated_at + RESULT_TTL).isoformat(),
        }

    def tasks(
        self,
        project_id: str,
        result_set_id: str,
        *,
        result: str,
        interval_start: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
        sort: str = "-createdAt",
        now: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        payload = _verify(result_set_id, self._secret)
        if payload.get("projectId") != project_id:
            raise ProjectError("NOT_FOUND", "统计结果不存在", 404)
        if result not in TERMINAL_STATUSES:
            raise ProjectError("VALIDATION_ERROR", "结果筛选无效", 422)
        current = now or datetime.now(UTC)
        if current > datetime.fromisoformat(payload["calculatedAt"]) + RESULT_TTL:
            raise ProjectError(
                "STATISTICS_RESULT_EXPIRED", "统计结果已过期，请刷新统计", 410
            )
        zone = resolve_timezone(payload["timezone"])
        window_from = datetime.fromisoformat(payload["from"])
        window_to = min(
            datetime.fromisoformat(payload["to"]),
            datetime.fromisoformat(payload["calculatedAt"]),
        )
        lower, frozen_upper = window_from, window_to
        if interval_start is not None:
            start = _aware(interval_start).astimezone(zone)
            lower = start.astimezone(UTC)
            frozen_upper = min(_bucket_end(start, payload["interval"]).astimezone(UTC), window_to)
            if frozen_upper <= window_from or lower >= window_to:
                raise ProjectError(
                    "STATISTICS_RANGE_INVALID", "区间起始时间超出统计范围", 422
                )
        return self._queries.list_tasks(
            project_id,
            status=result,
            ended_from=lower,
            ended_to=frozen_upper,
            automation_id=payload.get("automationId"),
            table_id=payload.get("tableId"),
            page=page,
            page_size=page_size,
            sort=sort,
        )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProjectError("STATISTICS_RANGE_INVALID", "时间范围必须包含时区", 422)
    return value.astimezone(UTC)


def _mean_ms(values: list[int]) -> int | None:
    return round(sum(values) / len(values)) if values else None


def _frozen_rows(
    session: Session,
    project_id: str,
    *,
    lower: datetime,
    upper: datetime,
    automation_id: str | None,
    table_id: str | None,
) -> list[dict[str, Any]]:
    query = (
        select(
            ProjectTaskRow.id,
            ProjectBatchRow.automation_id,
            WorkflowRunRow.status,
            WorkflowRunRow.completed_at,
            WorkflowRunRow.started_at,
            WorkflowRunRow.error,
        )
        .join(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
        .join(ProjectBatchRow, ProjectBatchRow.id == ProjectTaskRow.batch_id)
        .where(
            ProjectTaskRow.project_id == project_id,
            WorkflowRunRow.status.in_(TERMINAL_STATUSES),
            WorkflowRunRow.completed_at.is_not(None),
            WorkflowRunRow.completed_at >= lower,
            WorkflowRunRow.completed_at <= upper,
        )
    )
    if automation_id:
        query = query.where(ProjectBatchRow.automation_id == automation_id)
    rows = [
        {
            "taskId": task_id,
            "automationId": batch_automation_id,
            "status": status,
            "completedAt": completed_at,
            "startedAt": started_at,
            "error": error,
        }
        for task_id, batch_automation_id, status, completed_at, started_at, error in session.execute(
            query
        ).all()
    ]
    if table_id:
        allowed = set(
            session.scalars(
                select(ProjectTaskInputSnapshotRow.task_id).where(
                    ProjectTaskInputSnapshotRow.task_id.in_(
                        [row["taskId"] for row in rows]
                    )
                )
            )
        )
        snapshots = {
            snapshot.task_id: snapshot.inputs
            for snapshot in session.scalars(
                select(ProjectTaskInputSnapshotRow).where(
                    ProjectTaskInputSnapshotRow.task_id.in_(allowed)
                )
            )
        }
        rows = [
            row
            for row in rows
            if any(
                isinstance(item, dict)
                and isinstance(item.get("recordRef"), dict)
                and item["recordRef"].get("tableId") == table_id
                for item in snapshots.get(row["taskId"], [])
            )
        ]
    for row in rows:
        started, completed = row.pop("startedAt"), row["completedAt"]
        row["durationMs"] = (
            int((completed - started).total_seconds() * 1000)
            if started is not None and completed is not None
            else None
        )
        row["completedAt"] = _as_utc(completed)
    return rows


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _automation_names(session: Session, ids: set[str | None]) -> dict[str, str]:
    wanted = sorted(item for item in ids if isinstance(item, str))
    if not wanted:
        return {}
    return {
        row.id: row.name
        for row in session.scalars(
            select(ProjectAutomationRow).where(ProjectAutomationRow.id.in_(wanted))
        )
    }


def _trend(
    rows: list[dict[str, Any]], zone: ZoneInfo, interval: str
) -> list[dict[str, Any]]:
    buckets: dict[datetime, dict[str, Any]] = {}
    for row in rows:
        start = _bucket_start(row["completedAt"].astimezone(zone), interval)
        bucket = buckets.setdefault(start, {"counts": dict.fromkeys(TERMINAL_STATUSES, 0), "durations": []})
        bucket["counts"][row["status"]] += 1
        if row["durationMs"] is not None and row["status"] in ("succeeded", "failed"):
            bucket["durations"].append(row["durationMs"])
    return [
        {
            "bucketStart": start.isoformat(),
            **bucket["counts"],
            "averageDurationMs": _mean_ms(bucket["durations"]),
        }
        for start, bucket in sorted(buckets.items())
    ]


def _failures(
    rows: list[dict[str, Any]], names: dict[str, str]
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["status"] != "failed":
            continue
        automation_id = row["automationId"]
        entry = grouped.setdefault(
            automation_id,
            {"automationId": automation_id, "name": names.get(automation_id, "已删除的自动化"), "count": 0, "reasonSummary": None},
        )
        entry["count"] += 1
        if entry["reasonSummary"] is None:
            entry["reasonSummary"] = _reason(row["error"])
    return sorted(grouped.values(), key=lambda item: (-item["count"], item["automationId"]))


def _reason(error: Any) -> str | None:
    if isinstance(error, dict):
        for key in ("message", "code"):
            value = error.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _bucket_start(moment: datetime, interval: str) -> datetime:
    if interval == "day":
        return moment.replace(hour=0, minute=0, second=0, microsecond=0)
    if interval == "week":
        day = moment.replace(hour=0, minute=0, second=0, microsecond=0)
        return day - timedelta(days=day.weekday())
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _bucket_end(start: datetime, interval: str) -> datetime:
    if interval == "day":
        return start + timedelta(days=1)
    if interval == "week":
        return start + timedelta(days=7)
    year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    return start.replace(year=year, month=month)


def _sign(payload: dict[str, Any], secret: bytes) -> str:
    body = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    signature = hmac.new(secret, body, hashlib.sha256).hexdigest()[:16]
    return f"{base64.urlsafe_b64encode(body).decode().rstrip('=')}.{signature}"


def _verify(result_set_id: str, secret: bytes) -> dict[str, Any]:
    token, _, signature = str(result_set_id).partition(".")
    try:
        body = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (binascii.Error, ValueError) as exc:
        raise ProjectError("NOT_FOUND", "统计结果不存在", 404) from exc
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(expected, signature):
        raise ProjectError("NOT_FOUND", "统计结果不存在", 404)
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise ProjectError("NOT_FOUND", "统计结果不存在", 404) from exc
    if not isinstance(payload, dict):
        raise ProjectError("NOT_FOUND", "统计结果不存在", 404)
    return payload
