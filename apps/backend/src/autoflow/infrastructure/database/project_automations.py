import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import Table, delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_automations.models import (
    AutomationRecord,
    automation_to_dict,
)
from autoflow.domain.projects.models import ProjectError, ProjectOperation

from .models import ProjectOperationRow
from .project_automation_models import ProjectAutomationRow
from .project_data_models import DataImpactRow
from .project_run_models import (
    ProjectBatchRow,
    ProjectRecordLeaseRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRecordCursorRow,
    ProjectTaskRecordQueryItemRow,
    ProjectTaskRecordQueryRow,
    ProjectTaskRecordReadRow,
    ProjectTaskRow,
)
from .projects import _json_dates, _operation, _operation_row, guard_project
from .workflow_models import WorkflowDocumentRow
from .workflow_project_scope import workflow_project_id
from .workflow_runtime_models import (
    WorkflowPreparedContentRow,
    WorkflowRunArtifactRow,
    WorkflowRunEventRow,
    WorkflowRunRow,
)

IMPACT_TTL = timedelta(minutes=10)
IMPACT_ACTIONS = {"delete": "deleteAutomation", "unlinkWorkflow": "unlinkWorkflow"}
TERMINAL_BATCH_STATUSES = ("completed", "stopped", "failed", "interrupted")


class SqlAlchemyProjectAutomations:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def create(self, record, operation):
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = self._operation_by_key(session, operation)
            if existing:
                saved = _from_result(existing.result)
                session.rollback()
                return saved, _operation(existing), True
            self._guard_project(session, record.project_id)
            if session.get(WorkflowDocumentRow, record.workflow_id) is None:
                session.rollback()
                raise ProjectError(
                    "WORKFLOW_NOT_FOUND",
                    "Workflow was not found",
                    404,
                    {
                        "fields": {"workflowId": "Workflow was not found"},
                        "domainCode": "workflow_not_found",
                        "retryable": False,
                    },
                )
            owner = workflow_project_id(session, record.workflow_id)
            if owner is not None and owner != record.project_id:
                raise ProjectError("WORKFLOW_NOT_FOUND", "Workflow was not found", 404)
            try:
                session.add(_row(record))
                session.flush()
                done = _complete(operation, record)
                session.add(_operation_row(done))
                session.commit()
                return record, done, False
            except IntegrityError as error:
                session.rollback()
                message = str(error.orig).lower()
                code, field = (
                    ("WORKFLOW_ALREADY_BOUND", "workflowId")
                    if "workflow" in message
                    else ("AUTOMATION_NAME_CONFLICT", "name")
                )
                raise ProjectError(
                    code,
                    "Automation identity is already in use",
                    409,
                    {
                        "fields": {field: "Already in use"},
                        "domainCode": code.lower(),
                        "retryable": False,
                    },
                )

    def update(self, project_id, automation_id, values, expected_revision, operation):
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = self._operation_by_key(session, operation)
            if existing:
                saved = _from_result(existing.result)
                session.rollback()
                return saved, _operation(existing)
            self._guard_project(session, project_id)
            row = session.get(ProjectAutomationRow, automation_id)
            if row is None or row.project_id != project_id:
                session.rollback()
                raise ProjectError(
                    "AUTOMATION_NOT_FOUND", "Automation was not found", 404
                )
            current = _record(row)
            if current.management_revision != expected_revision:
                session.rollback()
                raise ProjectError(
                    "REVISION_CONFLICT",
                    "Automation was modified",
                    409,
                    {
                        "expectedRevision": expected_revision,
                        "currentRevision": current.management_revision,
                        "current": automation_to_dict(current),
                        "domainCode": "revision_conflict",
                        "retryable": False,
                    },
                )
            if current.workflow_id != values["workflowId"]:
                session.rollback()
                raise ProjectError(
                    "WORKFLOW_BINDING_IMMUTABLE",
                    "Workflow binding cannot be replaced",
                    409,
                    {"domainCode": "workflow_binding_immutable", "retryable": False},
                )
            record = current.updated(values, datetime.now(UTC))
            try:
                _apply(row, record)
                session.flush()
                done = _complete(operation, record)
                session.add(_operation_row(done))
                session.commit()
                return record, done
            except IntegrityError:
                session.rollback()
                raise ProjectError(
                    "AUTOMATION_NAME_CONFLICT",
                    "Automation name is already in use",
                    409,
                    {"fields": {"name": "Already in use"}},
                )

    def get(self, project_id, automation_id):
        with self._session_factory() as session:
            row = session.get(ProjectAutomationRow, automation_id)
            return _record(row) if row and row.project_id == project_id else None

    def list(self, project_id, q=None, page=1, page_size=50, sort="-updatedAt"):
        with self._session_factory() as session:
            self._guard_project(session, project_id, writable=False)
            query = select(ProjectAutomationRow).where(
                ProjectAutomationRow.project_id == project_id
            )
            if q:
                query = query.where(
                    ProjectAutomationRow.search_text.contains(
                        q.strip().casefold(), autoescape=True
                    )
                )
            orders = {
                "name": (ProjectAutomationRow.name_key, ProjectAutomationRow.id),
                "-name": (
                    ProjectAutomationRow.name_key.desc(),
                    ProjectAutomationRow.id,
                ),
                "updatedAt": (ProjectAutomationRow.updated_at, ProjectAutomationRow.id),
                "-updatedAt": (
                    ProjectAutomationRow.updated_at.desc(),
                    ProjectAutomationRow.id,
                ),
            }
            if sort not in orders:
                raise ProjectError(
                    "VALIDATION_ERROR",
                    "Invalid sort",
                    422,
                    {"fields": {"sort": "Invalid sort"}},
                )
            total = (
                session.scalar(select(func.count()).select_from(query.subquery())) or 0
            )
            rows = session.scalars(
                query.order_by(*orders[sort])
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return [_record(row) for row in rows], total

    def impact(self, project_id: str, automation_id: str, action: str) -> dict[str, Any]:
        """Describe what deleting one automation really touches.

        The confirmation is persisted in the shared impact table so a command
        can prove the user confirmed the *same* facts, not a stale screen.
        """
        mapped = _impact_action(action)
        with self._session_factory() as session:
            session.execute(text("BEGIN"))
            row = _owned_automation(session, project_id, automation_id)
            facts = _facts(session, project_id, row)
            revision = row.management_revision
            session.rollback()
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            saved = DataImpactRow(
                project_id=project_id,
                action=mapped,
                target={
                    "type": "automation",
                    "projectId": project_id,
                    "automationId": automation_id,
                },
                change_digest=_digest({"action": action}),
                expected_revisions={"managementRevision": revision},
                facts_digest=_digest(facts),
                report={},
                expires_at=datetime.now(UTC) + IMPACT_TTL,
            )
            session.add(saved)
            session.flush()
            saved.report = {
                "impacts": facts["impacts"],
                "blockers": facts["blockers"],
                "impactRevision": saved.id,
            }
            session.commit()
            return saved.report

    def delete(
        self,
        project_id: str,
        automation_id: str,
        operation: ProjectOperation,
        *,
        impact_revision: int,
        expected_revision: int,
        disposition: str,
    ) -> ProjectOperation:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = self._operation_by_key(session, operation)
            if existing:
                session.rollback()
                return _operation(existing)
            self._guard_project(session, project_id)
            row = _owned_automation(session, project_id, automation_id)
            if row.management_revision != expected_revision:
                session.rollback()
                raise ProjectError(
                    "REVISION_CONFLICT",
                    "Automation was modified",
                    409,
                    {
                        "expectedRevision": expected_revision,
                        "currentRevision": row.management_revision,
                        "current": automation_to_dict(_record(row)),
                        "domainCode": "revision_conflict",
                        "retryable": False,
                    },
                )
            facts = _facts(session, project_id, row)
            _require_impact(session, project_id, automation_id, impact_revision, facts)
            if facts["blockers"]:
                session.rollback()
                raise ProjectError(
                    "AUTOMATION_BUSY",
                    "Automation still has live work",
                    409,
                    {
                        "blockers": facts["blockers"],
                        "domainCode": "automation_busy",
                        "retryable": False,
                    },
                )
            if disposition != "unlink":
                # Ownership of a workflow document is not a persisted fact yet,
                # so an owned-document delete cannot be proven safe. Unlinking
                # is the only disposition this milestone can honour.
                session.rollback()
                raise ProjectError(
                    "WORKFLOW_OWNERSHIP_UNKNOWN",
                    "Workflow ownership cannot be confirmed",
                    409,
                    {
                        "domainCode": "workflow_ownership_unknown",
                        "retryable": False,
                    },
                )
            done = _purge_automation(session, project_id, row, operation)
            session.add(_operation_row(done))
            session.commit()
            return done

    @staticmethod
    def _guard_project(session, project_id, writable=True):
        guard_project(session, project_id, writable)

    @staticmethod
    def _operation_by_key(session, incoming):
        row = session.scalar(
            select(ProjectOperationRow).where(
                ProjectOperationRow.idempotency_key == incoming.idempotency_key
            )
        )
        if row and (
            row.kind != incoming.kind or row.request_digest != incoming.request_digest
        ):
            raise ProjectError(
                "OPERATION_PAYLOAD_MISMATCH",
                "Idempotency key was used for another request",
                409,
                {"domainCode": "operation_payload_mismatch", "retryable": False},
            )
        return row


def _complete(
    operation: ProjectOperation, record: AutomationRecord
) -> ProjectOperation:
    now = datetime.now(UTC)
    return replace(
        operation,
        status="succeeded",
        status_revision=2,
        result=_json_dates(automation_to_dict(record)),
        updated_at=now,
        completed_at=now,
    )


def _row(value):
    row = ProjectAutomationRow(
        id=value.automation_id,
        project_id=value.project_id,
        workflow_id=value.workflow_id,
        created_at=value.created_at,
    )
    _apply(row, value)
    return row


def _apply(row, value):
    row.name, row.name_key, row.search_text = (
        value.name,
        value.name.casefold(),
        f"{value.name} {value.description}".casefold(),
    )
    row.description, row.management_revision = (
        value.description,
        value.management_revision,
    )
    row.input_plan, row.parameter_schema = value.input_plan, value.parameter_schema
    row.environment_policy, row.run_policy, row.updated_at = (
        value.environment_policy,
        value.run_policy,
        value.updated_at,
    )


def _record(row):
    aware = lambda value: value.replace(tzinfo=UTC) if value.tzinfo is None else value
    return AutomationRecord(
        row.id,
        row.project_id,
        row.workflow_id,
        row.name,
        row.description,
        row.management_revision,
        row.input_plan,
        row.parameter_schema,
        row.environment_policy,
        row.run_policy,
        aware(row.created_at),
        aware(row.updated_at),
    )


def _from_result(value):
    assert value
    return AutomationRecord(
        value["automationId"],
        value["projectId"],
        value["workflowId"],
        value["name"],
        value["description"],
        value["managementRevision"],
        value["inputPlan"],
        value["parameterSchema"],
        value["environmentPolicy"],
        value["runPolicy"],
        datetime.fromisoformat(value["createdAt"]),
        datetime.fromisoformat(value["updatedAt"]),
    )


def _impact_action(action: str) -> str:
    mapped = IMPACT_ACTIONS.get(action)
    if mapped is None:
        raise ProjectError(
            "VALIDATION_ERROR",
            "Unsupported impact action",
            422,
            {"fields": {"action": "Only delete and unlinkWorkflow are available"}},
        )
    return mapped


def _owned_automation(
    session: Session, project_id: str, automation_id: str
) -> ProjectAutomationRow:
    row = session.get(ProjectAutomationRow, automation_id)
    if row is None or row.project_id != project_id:
        raise ProjectError("AUTOMATION_NOT_FOUND", "Automation was not found", 404)
    return row


def _facts(
    session: Session, project_id: str, row: ProjectAutomationRow
) -> dict[str, Any]:
    """What deleting this automation really touches; nothing here is a guess."""
    inputs = row.input_plan.get("inputs") or []
    tables = sorted({item["tableId"] for item in inputs if item.get("tableId")})
    conditions = sum(_count_conditions(item.get("filter")) for item in inputs)
    batches = list(
        session.execute(
            select(ProjectBatchRow.id, ProjectBatchRow.status).where(
                ProjectBatchRow.automation_id == row.id
            )
        )
    )
    prepared = (
        session.scalar(
            select(func.count())
            .select_from(WorkflowPreparedContentRow)
            .where(WorkflowPreparedContentRow.workflow_id == row.workflow_id)
        )
        or 0
    )
    resource = {
        "type": "automation",
        "projectId": project_id,
        "automationId": row.id,
    }
    impacts = [
        _impact(resource, "AUTOMATION_CONFIGURATION", "自动化名称、说明与草稿配置"),
        _impact(resource, "DATA_TABLE_USE", f"数据表使用项 {len(tables)} 项"),
        _impact(resource, "AUTOMATION_PARAMETERS", f"自动化参数 {len(row.parameter_schema)} 个"),
        _impact(resource, "AUTOMATION_FILTERS", f"筛选条件 {conditions} 条"),
        _impact(resource, "RUN_PLANS", f"运行方案 {len(batches)} 个及其任务与事件"),
        _impact(resource, "PREPARED_CONTENTS", f"配置升级恢复副本 {prepared} 个"),
        _impact(
            resource,
            "REFERENCED_RESOURCES_KEPT",
            "数据表与记录、外部来源、其它自动化与项目资源保留",
        ),
        _impact(resource, "WORKFLOW_DOCUMENT_KEPT", "关联的工作流文档保留，只解除关联"),
    ]
    blockers = [
        _blocker(
            "AUTOMATION_BUSY",
            {"type": "batch", "projectId": project_id, "batchId": batch_id},
            status,
            "批次尚未结束，先停止或等它收尾",
        )
        for batch_id, status in batches
        if status not in TERMINAL_BATCH_STATUSES
    ]
    return {
        "impacts": impacts,
        "blockers": blockers,
        "managementRevision": row.management_revision,
    }


def _require_impact(
    session: Session,
    project_id: str,
    automation_id: str,
    impact_revision: Any,
    facts: dict[str, Any],
) -> None:
    """The confirmation must describe the facts that are true right now."""
    if type(impact_revision) is not int or impact_revision < 1:
        raise _stale()
    saved = session.get(DataImpactRow, impact_revision)
    if (
        saved is None
        or saved.project_id != project_id
        or saved.action not in IMPACT_ACTIONS.values()
        or (saved.target or {}).get("automationId") != automation_id
        or _utc(saved.expires_at) <= datetime.now(UTC)
        or saved.facts_digest != _digest(facts)
    ):
        raise _stale(facts["blockers"])


def _purge_automation(
    session: Session,
    project_id: str,
    row: ProjectAutomationRow,
    operation: ProjectOperation,
) -> ProjectOperation:
    """Remove the automation's own run facts, then the automation.

    The workflow document and every table/record it reads stay: owning a
    document is not a fact this database records, so nothing here may act on
    that guess. `defer_foreign_keys` lets children go before their parents
    without exposing a half-deleted graph.
    """
    session.execute(text("PRAGMA defer_foreign_keys=ON"))
    batches = select(ProjectBatchRow.id).where(ProjectBatchRow.automation_id == row.id)
    tasks = select(ProjectTaskRow.id).where(ProjectTaskRow.batch_id.in_(batches))
    runs = select(ProjectTaskRow.run_id).where(ProjectTaskRow.batch_id.in_(batches))
    queries = select(ProjectTaskRecordQueryRow.id).where(
        ProjectTaskRecordQueryRow.task_id.in_(tasks)
    )
    plan: tuple[tuple[Table, Any], ...] = (
        (
            cast(Table, ProjectTaskRecordQueryItemRow.__table__),
            cast(Table, ProjectTaskRecordQueryItemRow.__table__).c.query_id.in_(queries),
        ),
        (
            cast(Table, ProjectTaskRecordQueryRow.__table__),
            ProjectTaskRecordQueryRow.task_id.in_(tasks),
        ),
        (
            cast(Table, ProjectTaskRecordReadRow.__table__),
            ProjectTaskRecordReadRow.task_id.in_(tasks),
        ),
        (
            cast(Table, ProjectTaskRecordCursorRow.__table__),
            ProjectTaskRecordCursorRow.task_id.in_(tasks),
        ),
        (
            cast(Table, ProjectRecordLeaseRow.__table__),
            ProjectRecordLeaseRow.batch_id.in_(batches),
        ),
        (
            cast(Table, ProjectTaskInputSnapshotRow.__table__),
            ProjectTaskInputSnapshotRow.batch_id.in_(batches),
        ),
        (
            cast(Table, WorkflowRunEventRow.__table__),
            WorkflowRunEventRow.run_id.in_(runs),
        ),
        (
            cast(Table, WorkflowRunArtifactRow.__table__),
            WorkflowRunArtifactRow.run_id.in_(runs),
        ),
        (cast(Table, WorkflowRunRow.__table__), WorkflowRunRow.id.in_(runs)),
        (cast(Table, ProjectTaskRow.__table__), ProjectTaskRow.batch_id.in_(batches)),
        (cast(Table, ProjectBatchRow.__table__), ProjectBatchRow.automation_id == row.id),
        (
            cast(Table, WorkflowPreparedContentRow.__table__),
            WorkflowPreparedContentRow.id.in_(
                select(ProjectBatchRow.prepared_content_id).where(
                    ProjectBatchRow.automation_id == row.id
                )
            ),
        ),
    )
    for table, predicate in plan:
        session.execute(delete(table).where(predicate))
    now = datetime.now(UTC)
    done = replace(
        operation,
        status="succeeded",
        status_revision=2,
        result={
            "target": {
                "type": "automation",
                "projectId": project_id,
                "automationId": row.id,
            },
            "deleted": True,
            "workflowId": row.workflow_id,
            "workflowDisposition": "unlink",
        },
        updated_at=now,
        completed_at=now,
    )
    session.execute(delete(ProjectAutomationRow).where(ProjectAutomationRow.id == row.id))
    return done


def _count_conditions(node: Any) -> int:
    """Count real filter leaves; groups and negation only nest them."""
    if not isinstance(node, dict):
        return 0
    if node.get("type") == "compare":
        return 1
    if node.get("type") == "not":
        return _count_conditions(node.get("item"))
    return sum(_count_conditions(child) for child in node.get("items") or [])


def _blocker(
    code: str, resource: dict[str, Any], state: str, message: str
) -> dict[str, Any]:
    return {"code": code, "resource": resource, "state": state, "message": message}


def _impact(resource: dict[str, Any], code: str, message: str) -> dict[str, Any]:
    return {"code": code, "resource": resource, "message": message, "blocking": False}


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _stale(blockers: list[dict[str, Any]] | None = None) -> ProjectError:
    return ProjectError(
        "PRECONDITION_FAILED",
        "重新执行删除影响检查后再提交",
        412,
        {"blockers": blockers or [], "retryable": False},
    )
