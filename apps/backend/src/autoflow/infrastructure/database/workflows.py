from datetime import UTC

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.workflows.models import WorkflowError, WorkflowRecord

from .models import WorkflowDocumentRow


class SqlAlchemyWorkflowRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def list(self) -> list[WorkflowRecord]:
        with self._session_factory() as session:
            return [
                _record(row)
                for row in session.scalars(
                    select(WorkflowDocumentRow).order_by(
                        WorkflowDocumentRow.updated_at.desc(), WorkflowDocumentRow.id
                    )
                )
            ]

    def get(self, workflow_id: str) -> WorkflowRecord | None:
        with self._session_factory() as session:
            row = session.get(WorkflowDocumentRow, workflow_id)
            return _record(row) if row else None

    def create(self, record: WorkflowRecord) -> WorkflowRecord:
        with self._session_factory.begin() as session:
            session.execute(
                insert(WorkflowDocumentRow)
                .values(
                    id=record.document["id"],
                    name=record.document["name"],
                    document=record.document,
                    layout=record.layout,
                    revision=1,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                )
                .on_conflict_do_nothing(index_elements=[WorkflowDocumentRow.id])
            )
            row = session.get(WorkflowDocumentRow, record.document["id"])
            assert row is not None
            saved = _record(row)
            if not saved.matches(record.document, record.layout):
                raise _conflict()
            return saved

    def save(self, record: WorkflowRecord, expected_revision: int) -> WorkflowRecord:
        with self._session_factory.begin() as session:
            result = session.execute(
                update(WorkflowDocumentRow)
                .where(
                    WorkflowDocumentRow.id == record.document["id"],
                    WorkflowDocumentRow.revision == expected_revision,
                )
                .values(
                    name=record.document["name"],
                    document=record.document,
                    layout=record.layout,
                    revision=expected_revision + 1,
                    updated_at=record.updated_at,
                )
            )
            row = session.get(WorkflowDocumentRow, record.document["id"])
            if row is None:
                raise WorkflowError("WORKFLOW_NOT_FOUND", "工作流不存在", 404)
            saved = _record(row)
            if getattr(result, "rowcount", 0) != 1 and not (
                saved.revision == expected_revision + 1
                and saved.matches(record.document, record.layout)
            ):
                raise _conflict()
            return saved


def _conflict() -> WorkflowError:
    return WorkflowError(
        "WORKFLOW_REVISION_CONFLICT",
        "工作流已被修改；请保留当前草稿并重新加载后重试",
        409,
    )


def _record(row: WorkflowDocumentRow) -> WorkflowRecord:
    return WorkflowRecord(
        row.document,
        row.layout,
        row.revision,
        row.created_at.replace(tzinfo=UTC),
        row.updated_at.replace(tzinfo=UTC),
    )
