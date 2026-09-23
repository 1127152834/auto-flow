"""Resolve existing project automation ownership and unbound Studio drafts."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from .models import ProjectRow
from .project_automation_models import ProjectAutomationRow
from .workflow_models import WorkflowDocumentRow


def workflow_project_expression() -> ColumnElement[str]:
    # Existing automation bindings are authoritative; newly created project
    # drafts carry the same project identifier until an automation is attached.
    binding = (
        select(ProjectAutomationRow.project_id)
        .where(ProjectAutomationRow.workflow_id == WorkflowDocumentRow.id)
        .correlate(WorkflowDocumentRow)
        .scalar_subquery()
    )
    return func.coalesce(
        binding,
        WorkflowDocumentRow.document["projectId"].as_string(),
        WorkflowDocumentRow.document["content"]["projectId"].as_string(),
    )


def workflow_project_id(session: Session, workflow_id: str) -> str | None:
    return session.scalar(
        select(workflow_project_expression()).where(WorkflowDocumentRow.id == workflow_id)
    )


def readable_workflow_project() -> ColumnElement[bool]:
    owner = workflow_project_expression()
    existing_project = select(ProjectRow.id).where(
        ProjectRow.id == owner, ProjectRow.lifecycle_state != "deleted",
    ).correlate(WorkflowDocumentRow).exists()
    return or_(owner.is_(None), existing_project)
