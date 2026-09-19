"""Project lifecycle commands: archive, restore and permanent delete.

The `closing` predicate lives here and nowhere else. Every other module only
reports its own read-only facts, so "closing" can never drift into meaning
"busy" — the same predicate decides whether an accepted archive settles.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast, overload

from sqlalchemy import Table, delete, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.projects.models import (
    ProjectError,
    ProjectOperation,
    ProjectRecord,
    project_to_dict,
)

from .environment_models import (
    ProjectEnvironmentInstanceRow,
    ProjectEnvironmentRow,
    ProjectEnvironmentSaveRow,
    ProjectManualItemRow,
)
from .models import Base, ProjectOperationRow, ProjectRow
from .project_automation_models import ProjectAutomationRow
from .project_data_models import DataImpactRow, DataTableRow
from .project_excel_models import ProjectExcelExportJobRow, ProjectExcelPublicationRow
from .project_run_models import ProjectBatchRow, ProjectTaskRow
from .project_sync_models import SyncOperationRow
from .workflow_runtime_models import (
    WorkflowPreparedContentRow,
    WorkflowRunArtifactRow,
    WorkflowRunEventRow,
    WorkflowRunRow,
)

_LOG = logging.getLogger(__name__)

IMPACT_TTL = timedelta(minutes=10)
IMPACT_ACTIONS = {"archive": "archiveProject", "delete": "deleteProject"}
LIFECYCLE_KINDS = ("archiveProject", "restoreProject", "deleteProject")
OPEN_OPERATION_STATUSES = ("accepted", "running", "reconciling")
FILE_OPERATION_KINDS = ("inspectExcel", "importExcel", "exportXlsx")
TERMINAL_BATCH_STATUSES = ("completed", "stopped", "failed", "interrupted")
RUN_TERMINAL_STATUSES = ("succeeded", "failed", "cancelled", "timed_out", "interrupted")
OPEN_MANUAL_STATUSES = ("waiting", "resume_requested")
# Spec §2.1: an instance still holding a live, closing or cleaning work copy.
BUSY_INSTANCE_STATES = (
    "reserved",
    "starting",
    "active",
    "waiting_manual",
    "closing",
    "saving",
    "cleaning",
)
# Rows owned by the project through a parent key instead of a `project_id` column.
_EXTRA_PURGES = (
    (WorkflowRunEventRow.__table__, "run_id", ProjectTaskRow.run_id),
    (WorkflowRunArtifactRow.__table__, "run_id", ProjectTaskRow.run_id),
    (ProjectExcelPublicationRow.__table__, "operation_id", ProjectExcelExportJobRow.operation_id),
    (WorkflowRunRow.__table__, "id", ProjectTaskRow.run_id),
    (WorkflowPreparedContentRow.__table__, "id", ProjectBatchRow.prepared_content_id),
)


class SqlAlchemyProjectLifecycle:
    """Lifecycle facts, commands and the delete cleanup in one place."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        environment_root: Path | None = None,
    ) -> None:
        self._factory = session_factory
        self._environment_root = (
            Path(environment_root).absolute() if environment_root else None
        )

    # ------------------------------------------------------------------ facts
    def impact(self, project_id: str, action: str) -> dict[str, Any]:
        mapped = _action(action)
        with self._factory() as session:
            session.execute(text("BEGIN"))
            project = _project_row(session, project_id)
            _require_action_state(project, action)
            facts = self._facts(session, project_id, mapped, project)
            revision = project.management_revision
            session.rollback()
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            now = datetime.now(UTC)
            saved = DataImpactRow(
                project_id=project_id,
                action=mapped,
                target={"type": "project", "projectId": project_id},
                change_digest=_digest({"action": action}),
                expected_revisions={"managementRevision": revision},
                facts_digest=_digest(facts),
                report={},
                expires_at=now + IMPACT_TTL,
            )
            session.add(saved)
            session.flush()
            saved.report = {**facts, "impactRevision": saved.id}
            session.commit()
            return saved.report

    # --------------------------------------------------------------- commands
    def archive(
        self,
        project_id: str,
        expected_revision: int,
        impact_revision: int,
        operation: ProjectOperation,
    ) -> ProjectOperation:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = _existing(session, operation)
            if existing is not None:
                session.rollback()
                return existing
            project = _project_row(session, project_id)
            if project.lifecycle_state != "active":
                session.rollback()
                raise ProjectError(
                    "LIFECYCLE_CONFLICT", "项目正在收尾或不是可归档状态", 409
                )
            _require_revision(project, expected_revision)
            self._require_impact(session, project_id, "archiveProject", impact_revision)
            project.lifecycle_state = "closing"
            project.updated_at = datetime.now(UTC)
            session.add(_operation_row(operation))
            session.commit()
            return operation

    def restore(
        self,
        project_id: str,
        expected_revision: int,
        operation: ProjectOperation,
    ) -> ProjectOperation:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = _existing(session, operation)
            if existing is not None:
                session.rollback()
                return existing
            project = _project_row(session, project_id)
            if project.lifecycle_state != "archived":
                session.rollback()
                raise ProjectError("LIFECYCLE_CONFLICT", "只有已归档项目可以恢复", 409)
            _require_revision(project, expected_revision)
            now = datetime.now(UTC)
            project.lifecycle_state = "active"
            project.updated_at = now
            done = operation.with_result(project_id, _record(project))
            session.add(_operation_row(done))
            session.commit()
            return done

    def delete(
        self,
        project_id: str,
        confirmation_name: str,
        expected_revision: int,
        impact_revision: int,
        operation: ProjectOperation,
    ) -> ProjectOperation:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = _existing(session, operation)
            if existing is not None:
                session.rollback()
                return existing
            project = _project_row(session, project_id)
            if project.lifecycle_state not in {"archived", "deleting"}:
                session.rollback()
                raise ProjectError(
                    "LIFECYCLE_CONFLICT", "项目必须先归档才能永久删除", 409
                )
            if project.lifecycle_state == "deleting" and _open_lifecycle_operation(
                session, project_id
            ):
                session.rollback()
                raise ProjectError("LIFECYCLE_CONFLICT", "项目正在删除", 409)
            if confirmation_name != project.name:
                session.rollback()
                raise _validation(
                    "confirmationName", "Confirmation name does not match the project"
                )
            _require_revision(project, expected_revision)
            self._require_impact(session, project_id, "deleteProject", impact_revision)
            project.lifecycle_state = "deleting"
            project.updated_at = datetime.now(UTC)
            session.add(_operation_row(operation))
            session.commit()
            return operation

    # -------------------------------------------------------------- progress
    def pending(self) -> list[str]:
        with self._factory() as session:
            return list(
                session.scalars(
                    select(ProjectRow.id)
                    .where(ProjectRow.lifecycle_state.in_(("closing", "deleting")))
                    .order_by(ProjectRow.updated_at, ProjectRow.id)
                )
            )

    def advance(self, project_id: str) -> None:
        """One convergence step; never invents a terminal fact."""
        with self._factory() as session:
            row = session.get(ProjectRow, project_id)
            state = row.lifecycle_state if row is not None else None
        if state == "closing":
            self._settle_archive(project_id)
        elif state == "deleting":
            self._settle_delete(project_id)

    # ---------------------------------------------------------------- internals
    def _facts(
        self,
        session: Session,
        project_id: str,
        action: str,
        project: ProjectRow,
    ) -> dict[str, Any]:
        return {
            "blockers": _blockers(session, project_id, project),
            "impacts": _impacts(session, project_id, action),
            "unsyncedCount": _unsynced_count(session, project_id),
        }

    def _require_impact(
        self,
        session: Session,
        project_id: str,
        action: str,
        impact_revision: Any,
    ) -> dict[str, Any]:
        """Never begin/commit here: the caller owns the write unit of work."""
        if type(impact_revision) is not int or impact_revision < 1:
            raise _stale()
        saved = session.get(DataImpactRow, impact_revision)
        if (
            saved is None
            or saved.project_id != project_id
            or saved.action != action
            or _utc(saved.expires_at) <= datetime.now(UTC)
        ):
            raise _stale()
        project = _project_row(session, project_id)
        current = self._facts(session, project_id, action, project)
        if saved.facts_digest != _digest(current):
            raise _stale(current["blockers"])
        return saved.report

    def _settle_archive(self, project_id: str) -> None:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            project = session.get(ProjectRow, project_id)
            if project is None or project.lifecycle_state != "closing":
                session.rollback()
                return
            # The command that is converging must never block itself.
            operation = _open_lifecycle_operation(session, project_id)
            excluded = operation.id if operation is not None else None
            if _blockers(
                session, project_id, project, exclude_operation_id=excluded
            ):
                session.rollback()
                return
            now = datetime.now(UTC)
            project.lifecycle_state = "archived"
            project.updated_at = now
            if operation is not None:
                operation.status = "succeeded"
                operation.status_revision += 1
                operation.result = _json_dates(project_to_dict(_record(project)))
                operation.updated_at = now
                operation.completed_at = now
            session.commit()

    def _settle_delete(self, project_id: str) -> None:
        with self._factory() as session:
            session.execute(text("BEGIN"))
            project = session.get(ProjectRow, project_id)
            if project is None or project.lifecycle_state != "deleting":
                session.rollback()
                return
            targets = _local_targets(session, project_id, self._environment_root)
            operation = _open_lifecycle_operation(session, project_id)
            operation_id = operation.id if operation is not None else None
            session.rollback()
        residue = _remove(targets)
        if residue:
            self._fail_cleanup(project_id, operation_id, residue)
            return
        self._purge(project_id, operation_id)

    def _fail_cleanup(
        self, project_id: str, operation_id: str | None, residue: list[str]
    ) -> None:
        _LOG.error(
            "Project delete cleanup left residue project_id=%s paths=%s",
            project_id,
            residue,
        )
        if operation_id is None:
            return
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            operation = session.get(ProjectOperationRow, operation_id)
            if operation is None or operation.status not in OPEN_OPERATION_STATUSES:
                session.rollback()
                return
            now = datetime.now(UTC)
            operation.status = "failed"
            operation.status_revision += 1
            operation.error = {
                "code": "DELETE_CLEANUP_FAILED",
                "message": "本地文件未能完全清理，项目停留在删除中",
                "details": {
                    "cleanup": {
                        "status": "failed",
                        "message": "本地文件未能完全清理",
                        "residue": residue,
                    },
                    "domainCode": "delete_cleanup_failed",
                    "retryable": True,
                },
            }
            operation.updated_at = now
            operation.completed_at = now
            session.commit()

    def _purge(self, project_id: str, operation_id: str | None) -> None:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            session.execute(text("PRAGMA defer_foreign_keys=ON"))
            project = session.get(ProjectRow, project_id)
            if project is None or project.lifecycle_state != "deleting":
                session.rollback()
                return
            for owned, child_column, parent_column in _EXTRA_PURGES:
                # Declarative models type `__table__` as FromClause.
                table = cast(Table, owned)
                session.execute(
                    delete(table).where(
                        table.c[child_column].in_(
                            select(parent_column).where(
                                parent_column.table.c.project_id == project_id
                            )
                        )
                    )
                )
            for table, predicate in _project_scoped_deletes(project_id):
                if table is ProjectOperationRow.__table__:
                    continue
                session.execute(delete(table).where(predicate))
            statement = delete(ProjectOperationRow).where(
                ProjectOperationRow.project_id == project_id
            )
            if operation_id is not None:
                statement = statement.where(ProjectOperationRow.id != operation_id)
            session.execute(statement)
            now = datetime.now(UTC)
            project.lifecycle_state = "deleted"
            # The tombstone frees the name without dropping the row every foreign
            # key in this database still points at.
            project.name_key = f"{project.name_key}\x00{project_id}"
            project.updated_at = now
            if operation_id is not None:
                operation = session.get(ProjectOperationRow, operation_id)
                if operation is not None:
                    operation.status = "succeeded"
                    operation.status_revision += 1
                    operation.result = {
                        "target": {"type": "project", "projectId": project_id},
                        "deleted": True,
                    }
                    operation.updated_at = now
                    operation.completed_at = now
            session.commit()


def _blockers(
    session: Session,
    project_id: str,
    project: ProjectRow,
    *,
    exclude_operation_id: str | None = None,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for batch_id, status in session.execute(
        select(ProjectBatchRow.id, ProjectBatchRow.status).where(
            ProjectBatchRow.project_id == project_id,
            ProjectBatchRow.status.not_in(TERMINAL_BATCH_STATUSES),
        )
    ):
        blockers.append(
            _blocker(
                "BATCH_ACTIVE",
                {"type": "batch", "projectId": project_id, "batchId": batch_id},
                status,
                "批次尚未结束，先停止或等它收尾",
            )
        )
    for task_id in session.scalars(
        select(ProjectTaskRow.id)
        .join(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
        .where(
            ProjectTaskRow.project_id == project_id,
            WorkflowRunRow.status.not_in(RUN_TERMINAL_STATUSES),
        )
    ):
        blockers.append(
            _blocker(
                "TASK_ACTIVE",
                {"type": "task", "projectId": project_id, "taskId": task_id},
                "running",
                "任务尚未结束",
            )
        )
    for task_id in session.scalars(
        select(ProjectManualItemRow.task_id).where(
            ProjectManualItemRow.project_id == project_id,
            ProjectManualItemRow.status.in_(OPEN_MANUAL_STATUSES),
        )
    ):
        blockers.append(
            _blocker(
                "MANUAL_PENDING",
                {"type": "task", "projectId": project_id, "taskId": task_id},
                "waiting",
                "人工事项等待处理",
            )
        )
    for instance_id, state in session.execute(
        select(ProjectEnvironmentInstanceRow.id, ProjectEnvironmentInstanceRow.state).where(
            ProjectEnvironmentInstanceRow.project_id == project_id,
            ProjectEnvironmentInstanceRow.state.in_(BUSY_INSTANCE_STATES),
        )
    ):
        blockers.append(
            _blocker(
                "ENVIRONMENT_ACTIVE",
                {
                    "type": "environment",
                    "projectId": project_id,
                    "environmentId": instance_id,
                },
                state,
                "环境现场仍在使用中",
            )
        )
    for operation_id, kind, status in session.execute(
        select(
            ProjectOperationRow.id, ProjectOperationRow.kind, ProjectOperationRow.status
        ).where(
            ProjectOperationRow.project_id == project_id,
            ProjectOperationRow.kind.in_(FILE_OPERATION_KINDS),
            ProjectOperationRow.status.in_(OPEN_OPERATION_STATUSES),
        )
    ):
        blockers.append(
            _blocker(
                "FILE_OPERATION_ACTIVE",
                {"type": "project", "projectId": project_id},
                status,
                f"{kind} 尚未结束",
                operation_id=operation_id,
            )
        )
    other = _open_lifecycle_operation(session, project_id)
    if other is not None and other.id != exclude_operation_id:
        blockers.append(
            _blocker(
                "LIFECYCLE_COMMAND_ACTIVE",
                {"type": "project", "projectId": project_id},
                other.status,
                f"{other.kind} 尚未结束",
                operation_id=other.id,
            )
        )
    if project.lifecycle_state == "deleting":
        blockers.append(
            _blocker(
                "PROJECT_DELETING",
                {"type": "project", "projectId": project_id},
                "deleting",
                "项目正在删除",
            )
        )
    return blockers


def _impacts(session: Session, project_id: str, action: str) -> list[dict[str, Any]]:
    tables = (
        session.scalar(
            select(func.count())
            .select_from(DataTableRow)
            .where(DataTableRow.project_id == project_id)
        )
        or 0
    )
    automations = (
        session.scalar(
            select(func.count())
            .select_from(ProjectAutomationRow)
            .where(ProjectAutomationRow.project_id == project_id)
        )
        or 0
    )
    impacts = [
        _impact("PROJECT_TABLES", project_id, f"删除 {tables} 张数据表及其记录"),
        _impact("PROJECT_AUTOMATIONS", project_id, f"删除 {automations} 个自动化"),
    ]
    unsynced = _unsynced_count(session, project_id)
    if unsynced:
        impacts.append(
            _impact(
                "UNSYNCED_CHANGES",
                project_id,
                f"{unsynced} 条变化尚未推送，删除后不会补发",
            )
        )
    if action == "deleteProject":
        impacts.append(
            _impact(
                "EXTERNAL_FILES_KEPT",
                project_id,
                "外部 Excel 原文件、远端 Sheets 与全局资源不会被删除",
            )
        )
    return impacts


def _unsynced_count(session: Session, project_id: str) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(SyncOperationRow)
            .where(
                SyncOperationRow.project_id == project_id,
                SyncOperationRow.status != "confirmed",
                SyncOperationRow.operation_id.is_(None),
            )
        )
        or 0
    )


def _local_targets(session: Session, project_id: str, root: Path | None) -> list[Path]:
    if root is None:
        return []
    instances = list(
        session.scalars(
            select(ProjectEnvironmentInstanceRow.id).where(
                ProjectEnvironmentInstanceRow.project_id == project_id
            )
        )
    )
    environments = list(
        session.scalars(
            select(ProjectEnvironmentRow.id).where(
                ProjectEnvironmentRow.project_id == project_id
            )
        )
    )
    saves = list(
        session.scalars(
            select(ProjectEnvironmentSaveRow.id).where(
                ProjectEnvironmentSaveRow.project_id == project_id
            )
        )
    )
    return [
        *[root / "instances" / value for value in instances],
        *[root / "environments" / value for value in environments],
        *[root / "candidates" / value for value in saves],
    ]


def _remove(targets: list[Path]) -> list[str]:
    residue: list[str] = []
    for path in targets:
        if not path.exists():
            continue
        try:
            shutil.rmtree(path)
        except OSError:
            _LOG.exception("Project delete could not remove %s", path)
            residue.append(str(path))
    return residue


def _project_scoped_deletes(project_id: str) -> tuple[tuple[Table, Any], ...]:
    """`(table, predicate)` for every row owned by the project, children first.

    Ownership is a `project_id` column, or a parent key for the tables that only
    inherit it. Targets are matched by name: the referenced table may live in a
    different metadata. Order is cosmetic — `_purge` defers foreign keys to the
    commit, so a half-deleted graph is never visible.
    """
    metadata = Base.metadata
    owned = {
        table.name: table
        for table in metadata.tables.values()
        if table.name != "projects" and "project_id" in table.c
    }
    dependents: list[tuple[Table, Any]] = []
    for table in metadata.tables.values():
        if table.name in owned:
            continue
        for foreign_key in table.foreign_keys:
            parent_name, parent_column = str(foreign_key.target_fullname).split(".", 1)
            parent = owned.get(parent_name)
            if parent is None or parent_column not in parent.c:
                continue
            dependents.append(
                (
                    table,
                    foreign_key.parent.in_(
                        select(parent.c[parent_column]).where(
                            parent.c.project_id == project_id
                        )
                    ),
                )
            )
            break
    members = [(table, table.c.project_id == project_id) for table in owned.values()]
    return (*dependents, *reversed(members))


def _project_row(session: Session, project_id: str) -> ProjectRow:
    row = session.get(ProjectRow, project_id)
    if row is None or row.lifecycle_state == "deleted":
        raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)
    return row


def _require_action_state(project: ProjectRow, action: str) -> None:
    allowed = {"archive": {"active"}, "delete": {"archived", "deleting"}}[action]
    if project.lifecycle_state not in allowed:
        raise ProjectError(
            "LIFECYCLE_CONFLICT",
            "归档需要活动项目，删除需要已归档项目",
            409,
            {
                "lifecycleState": project.lifecycle_state,
                "domainCode": "lifecycle_conflict",
                "retryable": False,
            },
        )


def _require_revision(project: ProjectRow, expected: int) -> None:
    if project.management_revision != expected:
        raise ProjectError(
            "REVISION_CONFLICT",
            "项目资料已更新，请刷新后重试",
            409,
            {
                "expectedRevision": expected,
                "currentRevision": project.management_revision,
                "domainCode": "revision_conflict",
                "retryable": False,
            },
        )


def _existing(session: Session, operation: ProjectOperation) -> ProjectOperation | None:
    row = session.scalar(
        select(ProjectOperationRow).where(
            ProjectOperationRow.idempotency_key == operation.idempotency_key
        )
    )
    if row is None:
        return None
    if row.kind != operation.kind or row.request_digest != operation.request_digest:
        raise ProjectError(
            "OPERATION_PAYLOAD_MISMATCH",
            "Idempotency key was used for another request",
            409,
            {"domainCode": "operation_payload_mismatch", "retryable": False},
        )
    return _operation(row)


def _open_lifecycle_operation(
    session: Session, project_id: str
) -> ProjectOperationRow | None:
    return session.scalar(
        select(ProjectOperationRow)
        .where(
            ProjectOperationRow.project_id == project_id,
            ProjectOperationRow.kind.in_(LIFECYCLE_KINDS),
            ProjectOperationRow.status.in_(OPEN_OPERATION_STATUSES),
        )
        .order_by(ProjectOperationRow.created_at.desc(), ProjectOperationRow.id)
    )


def _blocker(
    code: str,
    resource: dict[str, Any],
    state: str,
    message: str,
    *,
    operation_id: str | None = None,
) -> dict[str, Any]:
    blocker = {"code": code, "resource": resource, "state": state, "message": message}
    if operation_id is not None:
        blocker["operationId"] = operation_id
    return blocker


def _impact(code: str, project_id: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "resource": {"type": "project", "projectId": project_id},
        "message": message,
        "blocking": False,
    }


def _validation(field: str, message: str) -> ProjectError:
    return ProjectError(
        "VALIDATION_ERROR",
        "Request validation failed",
        422,
        {
            "fields": {field: message},
            "domainCode": "validation_error",
            "retryable": False,
        },
    )


def _stale(blockers: list[dict[str, Any]] | None = None) -> ProjectError:
    return ProjectError(
        "PRECONDITION_FAILED",
        "重新执行生命周期影响检查后再提交",
        412,
        {"blockers": blockers or [], "retryable": False},
    )


def _record(row: ProjectRow) -> ProjectRecord:
    return ProjectRecord(
        row.id,
        row.name,
        row.description,
        row.default_resources,
        row.management_revision,
        row.lifecycle_state,
        _utc(row.created_at),
        _utc(row.updated_at),
        _utc(row.last_opened_at) if row.last_opened_at else None,
    )


def _operation(row: ProjectOperationRow) -> ProjectOperation:
    return ProjectOperation(
        row.id,
        row.project_id,
        row.idempotency_key,
        row.kind,
        row.request_digest,
        row.status,
        row.status_revision,
        row.resource,
        row.result,
        row.error,
        _utc(row.created_at),
        _utc(row.updated_at),
        _utc(row.completed_at) if row.completed_at else None,
    )


def _operation_row(value: ProjectOperation) -> ProjectOperationRow:
    return ProjectOperationRow(
        id=value.operation_id,
        project_id=value.project_id,
        idempotency_key=value.idempotency_key,
        kind=value.kind,
        request_digest=value.request_digest,
        status=value.status,
        status_revision=value.status_revision,
        resource=value.resource,
        result=_json_dates(value.result) if value.result else None,
        error=value.error,
        created_at=value.created_at,
        updated_at=value.updated_at,
        completed_at=value.completed_at,
    )


def _json_dates(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: (item.isoformat() if isinstance(item, datetime) else item)
        for key, item in value.items()
    }


def _action(action: str) -> str:
    if action not in IMPACT_ACTIONS:
        raise _validation("action", "Must be archive or delete")
    return IMPACT_ACTIONS[action]


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


@overload
def _utc(value: datetime) -> datetime: ...


@overload
def _utc(value: None) -> None: ...


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
