"""Project overview aggregation: only committed facts, never synthetic numbers."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.projects.models import ProjectError, project_to_dict
from autoflow.infrastructure.database.environment_models import (
    ProjectEnvironmentRow,
    ProjectManualItemRow,
)
from autoflow.infrastructure.database.models import ProfileRow, ProxyRow
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.project_sync_models import SyncOperationRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow

ACTIVE_BATCH_STATUSES = (
    "accepted",
    "running",
    "blocked",
    "draining",
    "stopping",
    "reconciling",
)
TERMINAL_RUN_STATUSES = (
    "succeeded",
    "failed",
    "cancelled",
    "timed_out",
    "interrupted",
)
TERMINAL_BATCH_STATUSES = ("completed", "stopped", "failed", "interrupted")
MANUAL_TERMINAL_STATUSES = ("resolved", "finished", "cancelled", "expired")
SYNC_TERMINAL_STATUSES = ("confirmed", "failed", "unknown")
# ponytail: 30 minutes is a frozen constant, not a tuned threshold. Expose it per
# workspace only when a real project actually reports false positives.
STALE_AFTER = timedelta(minutes=30)
MAX_RECENT_ACTIVITY = 20
MAX_ATTENTION_ITEMS = 40
IN_FLIGHT_TASK_LABELS = {
    "queued": "排队中",
    "running": "运行中",
    "stopping": "停止中",
    "reconciling": "核验中",
}


def resolve_timezone(name: str | None) -> ZoneInfo:
    """An IANA zone: the request's own, else the configured one, else the host's."""
    if name is None:
        name = os.environ.get("TZ") or _host_timezone() or "UTC"
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ProjectError("VALIDATION_ERROR", f"非法时区 {name}", 422) from exc


def _host_timezone() -> str | None:
    """`/etc/localtime` is a symlink into the zoneinfo database on macOS/Linux."""
    try:
        target = os.path.realpath("/etc/localtime")
    except OSError:
        return None
    marker = f"{os.sep}zoneinfo{os.sep}"
    return target.split(marker, 1)[1] if marker in target else None


class ProjectOverviewService:
    """Read-only aggregation behind `GET /projects/{projectId}/overview`."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def get(
        self,
        project_id: str,
        *,
        timezone: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        zone = resolve_timezone(timezone)
        current = now or datetime.now(UTC)
        project = SqlAlchemyProjects(self._factory).get(project_id)
        if project is None or project.lifecycle_state == "deleted":
            raise ProjectError("NOT_FOUND", "项目不存在", 404)
        with self._factory() as session:
            day_start = (
                current.astimezone(zone)
                .replace(hour=0, minute=0, second=0, microsecond=0)
                .astimezone(UTC)
            )
            changes = _day_changes(session, project_id, day_start)
            return {
                "project": project_to_dict(project),
                "counts": _counts(session, project_id),
                "activity": _attention(session, project_id, current),
                "current": _current(session, project_id),
                "recent": _recent(session, project_id, current),
                "dataChanges": {
                    "timezone": str(zone),
                    "dayStart": day_start.isoformat(),
                    "newRecords": changes[0],
                    "updatedRecords": changes[1],
                },
            }


def _count(session: Session, model: Any, project_id: str) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(model).where(model.project_id == project_id)
        )
        or 0
    )


def _counts(session: Session, project_id: str) -> dict[str, int]:
    return {
        "automations": _count(session, ProjectAutomationRow, project_id),
        "tables": int(
            session.scalar(
                select(func.count())
                .select_from(DataTableRow)
                .where(
                    DataTableRow.project_id == project_id,
                    DataTableRow.published.is_(True),
                )
            )
            or 0
        ),
        "batches": _count(session, ProjectBatchRow, project_id),
        "environments": _count(session, ProjectEnvironmentRow, project_id),
    }


def _day_changes(session: Session, project_id: str, day_start: datetime) -> tuple[int, int]:
    rows = session.execute(
        select(DataChangeRow.before, DataChangeRow.after).where(
            DataChangeRow.project_id == project_id,
            DataChangeRow.created_at >= day_start,
        )
    ).all()
    new_records = sum(1 for before, after in rows if before is None and after is not None)
    updated = sum(1 for before, after in rows if before is not None and after is not None)
    return new_records, updated


def _attention(
    session: Session, project_id: str, now: datetime
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    batches = list(
        session.scalars(
            select(ProjectBatchRow)
            .where(
                ProjectBatchRow.project_id == project_id,
                ProjectBatchRow.status.in_(ACTIVE_BATCH_STATUSES),
            )
            .order_by(ProjectBatchRow.created_at)
        )
    )
    for batch in batches:
        # D6: 非终态且停滞才是关注项。进行中的批次属于 `current`（项目活动·当前），
        # 在这里再报一次会变成同一条事实出现在两个面板。
        if now - _aware(batch.created_at) > STALE_AFTER:
            items.append(
                {
                    "kind": "batch",
                    "resource": {
                        "type": "batch",
                        "projectId": project_id,
                        "batchId": batch.id,
                    },
                    "severity": "warning",
                    "message": f"批次已停滞超过 {int(STALE_AFTER.total_seconds() // 60)} 分钟",
                    "occurredAt": _aware(batch.created_at).isoformat(),
                }
            )
        items.extend(_missing_resource_items(session, project_id, batch, now))

    failures = session.execute(
        select(ProjectTaskRow.id, WorkflowRunRow.completed_at, WorkflowRunRow.error)
        .join(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
        .where(
            ProjectTaskRow.project_id == project_id,
            WorkflowRunRow.status == "failed",
        )
        .order_by(WorkflowRunRow.completed_at.desc())
        .limit(50)
    ).all()
    for task_id, completed_at, error in failures:
        items.append(
            {
                "kind": "task",
                "resource": {
                    "type": "task",
                    "projectId": project_id,
                    "taskId": task_id,
                },
                "severity": "error",
                "message": _error_summary(error),
                "occurredAt": (completed_at or now).isoformat(),
            }
        )

    manual_items = list(
        session.scalars(
            select(ProjectManualItemRow)
            .where(
                ProjectManualItemRow.project_id == project_id,
                ProjectManualItemRow.status == "waiting",
            )
            .order_by(ProjectManualItemRow.created_at)
        )
    )
    for item in manual_items:
        expires_at = _aware(item.expires_at) if item.expires_at else None
        if expires_at is not None and expires_at <= now:
            continue
        items.append(
            {
                "kind": "manual",
                "resource": {
                    "type": "task",
                    "projectId": project_id,
                    "taskId": item.task_id,
                },
                "severity": "warning",
                "message": item.reason or "等待人工处理",
                "occurredAt": _aware(item.created_at).isoformat(),
            }
        )

    sync_operations = list(
        session.scalars(
            select(SyncOperationRow)
            .where(
                SyncOperationRow.project_id == project_id,
                SyncOperationRow.status.in_(("failed", "unknown")),
            )
            .order_by(SyncOperationRow.updated_at.desc())
            .limit(20)
        )
    )
    for operation in sync_operations:
        items.append(
            {
                "kind": "sync",
                "resource": {
                    "type": "sync",
                    "projectId": project_id,
                    "tableId": operation.table_id,
                    "syncOperationId": operation.id,
                },
                "severity": "error" if operation.status == "failed" else "warning",
                "message": (
                    "表格同步失败"
                    if operation.status == "failed"
                    else "表格同步结果尚未核验"
                ),
                "occurredAt": _aware(operation.updated_at).isoformat(),
            }
        )
    return items[:MAX_ATTENTION_ITEMS]


def _missing_resource_items(
    session: Session, project_id: str, batch: ProjectBatchRow, now: datetime
) -> list[dict[str, Any]]:
    request = (batch.frozen_request or {}).get("resourceRequest")
    if not isinstance(request, dict):
        return []
    checks = (
        ("profileId", ProfileRow),
        ("proxyId", ProxyRow),
    )
    items: list[dict[str, Any]] = []
    for key, model in checks:
        identifier = request.get(key)
        if not isinstance(identifier, str):
            continue
        if session.get(model, identifier) is not None:
            continue
        items.append(
            {
                "kind": "resource",
                "resource": {
                    "type": "batch",
                    "projectId": project_id,
                    "batchId": batch.id,
                },
                "severity": "warning",
                "message": f"批次冻结的{key}已不存在，无法重新使用",
                "occurredAt": _aware(batch.created_at).isoformat(),
            }
        )
    return items


def _current(session: Session, project_id: str) -> list[dict[str, Any]]:
    """D5: in-flight work only. Terminal objects belong to `recent`."""
    entries: list[tuple[datetime, dict[str, Any]]] = []

    batches = list(
        session.scalars(
            select(ProjectBatchRow)
            .where(
                ProjectBatchRow.project_id == project_id,
                ProjectBatchRow.status.in_(ACTIVE_BATCH_STATUSES),
            )
            .order_by(ProjectBatchRow.created_at.desc())
            .limit(MAX_RECENT_ACTIVITY)
        )
    )
    for batch in batches:
        occurred = _aware(batch.created_at)
        entries.append(
            (
                occurred,
                {
                    "activityId": batch.id,
                    "kind": "batch",
                    "resource": {
                        "type": "batch",
                        "projectId": project_id,
                        "batchId": batch.id,
                    },
                    "summary": f"批次处理中（{batch.status}）",
                    "occurredAt": occurred.isoformat(),
                },
            )
        )

    manual_items = list(
        session.scalars(
            select(ProjectManualItemRow)
            .where(
                ProjectManualItemRow.project_id == project_id,
                ProjectManualItemRow.status == "waiting",
            )
            .order_by(ProjectManualItemRow.updated_at.desc())
            .limit(MAX_RECENT_ACTIVITY)
        )
    )
    for item in manual_items:
        occurred = _aware(item.updated_at)
        entries.append(
            (
                occurred,
                {
                    "activityId": item.id,
                    "kind": "manual",
                    "resource": {
                        "type": "task",
                        "projectId": project_id,
                        "taskId": item.task_id,
                    },
                    "summary": item.reason or "人工事项等待处理",
                    "occurredAt": occurred.isoformat(),
                },
            )
        )

    tasks = session.execute(
        select(
            ProjectTaskRow.id,
            WorkflowRunRow.started_at,
            WorkflowRunRow.status,
        )
        .join(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
        .where(
            ProjectTaskRow.project_id == project_id,
            WorkflowRunRow.status.not_in(TERMINAL_RUN_STATUSES),
        )
        .order_by(WorkflowRunRow.started_at.desc())
        .limit(MAX_RECENT_ACTIVITY)
    ).all()
    for task_id, started_at, status in tasks:
        occurred = _aware(started_at)
        entries.append(
            (
                occurred,
                {
                    "activityId": task_id,
                    "kind": "task",
                    "resource": {
                        "type": "task",
                        "projectId": project_id,
                        "taskId": task_id,
                    },
                    "summary": f"任务{IN_FLIGHT_TASK_LABELS.get(status, status)}",
                    "occurredAt": occurred.isoformat(),
                },
            )
        )

    entries.sort(key=lambda entry: entry[0], reverse=True)
    return [entry for _, entry in entries[:MAX_RECENT_ACTIVITY]]


def _recent(
    session: Session, project_id: str, now: datetime
) -> list[dict[str, Any]]:
    entries: list[tuple[datetime, dict[str, Any]]] = []

    changes = list(
        session.scalars(
            select(DataChangeRow)
            .where(DataChangeRow.project_id == project_id)
            .order_by(DataChangeRow.created_at.desc())
            .limit(MAX_RECENT_ACTIVITY)
        )
    )
    for change in changes:
        entries.append(
            (
                _aware(change.created_at),
                {
                    "activityId": change.id,
                    "kind": "data",
                    "resource": change.resource,
                    "summary": _change_summary(change),
                    "occurredAt": _aware(change.created_at).isoformat(),
                },
            )
        )

    batches = list(
        session.scalars(
            select(ProjectBatchRow)
            .where(
                ProjectBatchRow.project_id == project_id,
                ProjectBatchRow.status.in_(TERMINAL_BATCH_STATUSES),
                ProjectBatchRow.completed_at.is_not(None),
            )
            .order_by(ProjectBatchRow.completed_at.desc())
            .limit(MAX_RECENT_ACTIVITY)
        )
    )
    for batch in batches:
        occurred = _aware(batch.completed_at)
        entries.append(
            (
                occurred,
                {
                    "activityId": batch.id,
                    "kind": "batch",
                    "resource": {
                        "type": "batch",
                        "projectId": project_id,
                        "batchId": batch.id,
                    },
                    "summary": f"批次{batch.status}",
                    "occurredAt": occurred.isoformat(),
                },
            )
        )

    manual_items = list(
        session.scalars(
            select(ProjectManualItemRow)
            .where(
                ProjectManualItemRow.project_id == project_id,
                ProjectManualItemRow.status.in_(MANUAL_TERMINAL_STATUSES),
            )
            .order_by(ProjectManualItemRow.updated_at.desc())
            .limit(MAX_RECENT_ACTIVITY)
        )
    )
    for item in manual_items:
        occurred = _aware(item.updated_at)
        entries.append(
            (
                occurred,
                {
                    "activityId": item.id,
                    "kind": "manual",
                    "resource": {
                        "type": "task",
                        "projectId": project_id,
                        "taskId": item.task_id,
                    },
                    "summary": f"人工事项{item.status}",
                    "occurredAt": occurred.isoformat(),
                },
            )
        )

    sync_operations = list(
        session.scalars(
            select(SyncOperationRow)
            .where(
                SyncOperationRow.project_id == project_id,
                SyncOperationRow.status.in_(SYNC_TERMINAL_STATUSES),
            )
            .order_by(SyncOperationRow.updated_at.desc())
            .limit(MAX_RECENT_ACTIVITY)
        )
    )
    for operation in sync_operations:
        occurred = _aware(operation.updated_at)
        entries.append(
            (
                occurred,
                {
                    "activityId": operation.id,
                    "kind": "sync",
                    "resource": {
                        "type": "sync",
                        "projectId": project_id,
                        "tableId": operation.table_id,
                        "syncOperationId": operation.id,
                    },
                    "summary": f"表格同步{operation.status}",
                    "occurredAt": occurred.isoformat(),
                },
            )
        )

    entries.sort(key=lambda entry: entry[0], reverse=True)
    return [entry for _, entry in entries[:MAX_RECENT_ACTIVITY]]


def _change_summary(change: DataChangeRow) -> str:
    resource = change.resource if isinstance(change.resource, dict) else {}
    kind = resource.get("type")
    if resource.get("recordRef") is not None or kind == "record":
        return "记录已创建" if change.before is None else "记录已更新"
    if kind == "table":
        return "数据表已创建" if change.before is None else "数据表已修改"
    if kind == "field":
        return "字段已新增" if change.before is None else "字段已修改"
    if kind == "status":
        return "业务状态已新增" if change.before is None else "业务状态已修改"
    return "数据已变更"


def _error_summary(error: Any) -> str:
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message:
            return f"任务失败：{message}"
        code = error.get("code")
        if isinstance(code, str) and code:
            return f"任务失败：{code}"
    return "任务失败"


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
