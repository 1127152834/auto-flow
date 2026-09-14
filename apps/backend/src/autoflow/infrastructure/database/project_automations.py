from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_automations.models import (
    AutomationRecord,
    automation_to_dict,
)
from autoflow.domain.projects.models import ProjectError, ProjectOperation

from .models import ProjectOperationRow, ProjectRow, WorkflowDocumentRow
from .project_automation_models import ProjectAutomationRow
from .projects import _json_dates, _operation, _operation_row


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

    @staticmethod
    def _guard_project(session, project_id, writable=True):
        row = session.get(ProjectRow, project_id)
        if row is None or row.lifecycle_state == "deleted":
            raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)
        if writable and row.lifecycle_state == "closing":
            raise ProjectError("PROJECT_CLOSING", "Project is closing", 423)
        if writable and row.lifecycle_state != "active":
            raise ProjectError("LIFECYCLE_CONFLICT", "Project cannot be edited", 409)

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
