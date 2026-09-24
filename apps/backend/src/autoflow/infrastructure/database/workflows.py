from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.workflows.document import (
    SavedWorkflow,
    WorkflowDraft,
    WorkflowSummary,
    WorkflowSummaryPage,
)
from autoflow.domain.workflows.errors import WorkflowDocumentError

from .core_workflows import _canonical_document_shape
from .projects import guard_project
from .workflow_models import WorkflowDocumentRequestRow, WorkflowDocumentRow
from .workflow_project_scope import (
    readable_workflow_project,
    workflow_project_expression,
    workflow_project_id,
)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _saved(row: WorkflowDocumentRow, project_id: str | None = None) -> SavedWorkflow:
    document = copy.deepcopy(row.document)
    layout = copy.deepcopy(row.layout)
    if _canonical_document_shape(document):
        # The project catalog wraps the same persisted graph; Studio consumes
        # the unwrapped document, with its database identity and revision.
        draft = WorkflowDraft.from_payload({
            **document["content"], "id": row.id, "name": row.name, "layout": layout,
        })
        document, layout = draft.document, draft.layout
    return SavedWorkflow(
        id=row.id,
        name=row.name,
        document=document,
        layout=layout,
        revision=row.revision,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
        project_id=project_id,
    )


def _response(value: SavedWorkflow) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "document": value.document,
        "layout": value.layout,
        "revision": value.revision,
        "createdAt": value.created_at.isoformat(),
        "updatedAt": value.updated_at.isoformat(),
        "projectId": value.project_id,
    }


def _from_response(value: dict[str, Any]) -> SavedWorkflow:
    return SavedWorkflow(
        id=value["id"],
        name=value["name"],
        document=copy.deepcopy(value["document"]),
        layout=copy.deepcopy(value["layout"]),
        revision=value["revision"],
        created_at=datetime.fromisoformat(value["createdAt"]),
        updated_at=datetime.fromisoformat(value["updatedAt"]),
        project_id=value.get("projectId"),
    )


class SqlAlchemyWorkflowDocuments:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _receipt(
        session: Session, client_request_id: str, request_digest: str
    ) -> SavedWorkflow | None:
        row = session.get(WorkflowDocumentRequestRow, client_request_id)
        if row is None:
            return None
        if row.request_digest != request_digest:
            raise WorkflowDocumentError(
                "IDEMPOTENCY_CONFLICT", "请求 ID 已用于不同内容", 409
            )
        return _from_response(row.response)

    def create(
        self,
        draft: WorkflowDraft,
        *,
        client_request_id: str,
        request_digest: str,
        now: datetime,
    ) -> SavedWorkflow:
        assert draft.id is not None
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            project_id = draft.document.get("projectId")
            if project_id is not None:
                guard_project(session, project_id)
            previous = self._receipt(session, client_request_id, request_digest)
            if previous is not None:
                session.rollback()
                return previous
            if session.get(WorkflowDocumentRow, draft.id) is not None:
                session.rollback()
                raise WorkflowDocumentError(
                    "WORKFLOW_ID_CONFLICT", "工作流 ID 已存在", 409
                )
            row = WorkflowDocumentRow(
                id=draft.id,
                name=draft.name,
                document=copy.deepcopy(draft.document),
                layout=copy.deepcopy(draft.layout),
                revision=1,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            saved = _saved(row, project_id)
            session.add(
                WorkflowDocumentRequestRow(
                    id=client_request_id,
                    request_digest=request_digest,
                    kind="create",
                    workflow_id=draft.id,
                    response=_response(saved),
                    created_at=now,
                )
            )
            session.commit()
            return saved

    def get(self, workflow_id: str) -> SavedWorkflow | None:
        with self._session_factory() as session:
            row = session.get(WorkflowDocumentRow, workflow_id)
            if row is None:
                return None
            project_id = workflow_project_id(session, workflow_id)
            if project_id is not None:
                guard_project(session, project_id, writable=False)
            return _saved(row, project_id)

    def list_summaries(
        self, cursor: int, limit: int, project_id: str | None = None
    ) -> WorkflowSummaryPage:
        with self._session_factory() as session:
            query = select(WorkflowDocumentRow).where(readable_workflow_project())
            if project_id is not None:
                guard_project(session, project_id, writable=False)
                query = query.where(workflow_project_expression() == project_id)
            rows = session.scalars(query
                .order_by(WorkflowDocumentRow.updated_at.desc(), WorkflowDocumentRow.id)
                .offset(cursor).limit(limit + 1)).all()
            has_more = len(rows) > limit
            items = tuple(
                WorkflowSummary(
                    id=row.id,
                    name=row.name,
                    revision=row.revision,
                    created_at=_aware(row.created_at),
                    updated_at=_aware(row.updated_at),
                )
                for row in rows[:limit]
            )
            return WorkflowSummaryPage(items, cursor + limit if has_more else None)

    def update(
        self,
        workflow_id: str,
        draft: WorkflowDraft,
        *,
        expected_revision: int,
        client_request_id: str,
        request_digest: str,
        now: datetime,
    ) -> SavedWorkflow:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            project_id = workflow_project_id(session, workflow_id)
            if project_id is not None:
                guard_project(session, project_id)
            supplied_project = draft.document.get("projectId")
            if supplied_project is not None and supplied_project != project_id:
                raise WorkflowDocumentError("WORKFLOW_NOT_FOUND", "工作流不存在", 404)
            previous = self._receipt(session, client_request_id, request_digest)
            if previous is not None:
                session.rollback()
                return previous
            row = session.get(WorkflowDocumentRow, workflow_id)
            if row is None:
                session.rollback()
                raise WorkflowDocumentError("WORKFLOW_NOT_FOUND", "工作流不存在", 404)
            if row.revision != expected_revision:
                current_revision = row.revision
                session.rollback()
                raise WorkflowDocumentError(
                    "WORKFLOW_REVISION_CONFLICT",
                    "工作流已由其他窗口修改",
                    409,
                    {
                        "expectedRevision": expected_revision,
                        "currentRevision": current_revision,
                    },
                )
            row.name = draft.name
            row.document = copy.deepcopy(draft.document)
            if project_id is not None:
                row.document = {**row.document, "projectId": project_id}
            row.layout = copy.deepcopy(draft.layout)
            row.revision += 1
            row.updated_at = now
            session.flush()
            saved = _saved(row, project_id)
            session.add(
                WorkflowDocumentRequestRow(
                    id=client_request_id,
                    request_digest=request_digest,
                    kind="update",
                    workflow_id=workflow_id,
                    response=_response(saved),
                    created_at=now,
                )
            )
            session.commit()
            return saved

    def delete(self, workflow_id: str, *, expected_revision: int) -> None:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            project_id = workflow_project_id(session, workflow_id)
            if project_id is not None:
                guard_project(session, project_id)
            row = session.get(WorkflowDocumentRow, workflow_id)
            if row is None:
                session.rollback()
                raise WorkflowDocumentError("WORKFLOW_NOT_FOUND", "工作流不存在", 404)
            if row.revision != expected_revision:
                current_revision = row.revision
                session.rollback()
                raise WorkflowDocumentError(
                    "WORKFLOW_REVISION_CONFLICT",
                    "工作流已由其他窗口修改",
                    409,
                    {
                        "expectedRevision": expected_revision,
                        "currentRevision": current_revision,
                    },
                )
            session.delete(row)
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise WorkflowDocumentError(
                    "WORKFLOW_IN_USE", "工作流仍被项目自动化或运行记录引用，不能直接删除", 409
                ) from error


from .core_workflows import (  # noqa: F401
    SqlAlchemyWorkflowRepository,
    _record,
)
