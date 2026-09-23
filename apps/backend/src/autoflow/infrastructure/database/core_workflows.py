from __future__ import annotations

import builtins
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.workflows.models import (
    LegacyWorkflowRecord,
    WorkflowError,
    WorkflowRecord,
    WorkflowSaveOperation,
)
from autoflow.domain.workflows.validation import (
    FORMAT_KIND,
    FORMAT_VERSION,
    SOURCE_COMMIT,
    SOURCE_PRODUCT,
)

from .projects import guard_project
from .workflow_core_models import WorkflowDocumentOperationRow
from .workflow_models import WorkflowDocumentRow
from .workflow_project_scope import (
    readable_workflow_project,
    workflow_project_expression,
    workflow_project_id,
)


class SqlAlchemyWorkflowRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list(self) -> list[WorkflowRecord]:
        with self._session_factory() as session:
            rows = session.execute(
                select(WorkflowDocumentRow, workflow_project_expression()).where(readable_workflow_project()).order_by(
                    WorkflowDocumentRow.updated_at.desc(), WorkflowDocumentRow.id
                )
            ).all()
            return [_record(row, project_id) for row, project_id in rows if _current_document(row.document)]

    def list_legacy(self) -> builtins.list[LegacyWorkflowRecord]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(WorkflowDocumentRow).order_by(
                    WorkflowDocumentRow.updated_at.desc(), WorkflowDocumentRow.id
                )
            ).all()
            return [
                _legacy_record(row)
                for row in rows
                if not _current_document(row.document)
            ]

    def get(self, workflow_id: str) -> WorkflowRecord | None:
        with self._session_factory() as session:
            row = session.get(WorkflowDocumentRow, workflow_id)
            if row is None:
                return None
            project_id = workflow_project_id(session, workflow_id)
            if project_id is not None:
                guard_project(session, project_id, writable=False)
            return _record(row, project_id)

    def get_legacy(self, workflow_id: str) -> LegacyWorkflowRecord | None:
        with self._session_factory() as session:
            row = session.get(WorkflowDocumentRow, workflow_id)
            if row is None or _current_document(row.document):
                return None
            return _legacy_record(row)

    def save(
        self,
        document: dict[str, Any],
        expected_revision: int,
        save_operation_id: str,
        request_digest: str,
        now: datetime,
    ) -> WorkflowSaveOperation:
        workflow_id = str(document["id"])
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            project_id = workflow_project_id(session, workflow_id)
            if project_id is not None:
                guard_project(session, project_id)
                document = deepcopy(document)
                document["content"]["projectId"] = project_id
            existing = session.get(
                WorkflowDocumentOperationRow, save_operation_id
            )
            if existing is not None:
                operation = _operation(existing)
                if operation.request_digest != request_digest:
                    session.rollback()
                    raise _operation_mismatch()
                session.rollback()
                return operation

            row = session.get(WorkflowDocumentRow, workflow_id)
            if row is None:
                if expected_revision != 0:
                    session.rollback()
                    raise WorkflowError(
                        "WORKFLOW_NOT_FOUND", "工作流不存在", 404
                    )
                row = WorkflowDocumentRow(
                    id=workflow_id,
                    name=str(document["content"]["name"]),
                    document=document,
                    layout={},
                    revision=1,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                session.flush()
                record = _record(row)
            else:
                current = _record(row)
                if current.revision != expected_revision:
                    session.rollback()
                    raise _revision_conflict(expected_revision, current)
                if current.matches(document):
                    record = current
                else:
                    row.name = str(document["content"]["name"])
                    row.document = document
                    row.layout = {}
                    row.revision = expected_revision + 1
                    row.updated_at = now
                    session.flush()
                    record = _record(row)

            operation = WorkflowSaveOperation(
                save_operation_id,
                workflow_id,
                request_digest,
                record,
            )
            session.add(_operation_row(operation, now))
            session.commit()
            return operation

    def get_save_operation(
        self, save_operation_id: str
    ) -> WorkflowSaveOperation | None:
        with self._session_factory() as session:
            row = session.get(WorkflowDocumentOperationRow, save_operation_id)
            return _operation(row) if row is not None else None


def _record(row: WorkflowDocumentRow, project_id: str | None = None) -> WorkflowRecord:
    document = _canonical_document(row)
    if document is None:
        raise WorkflowError(
            "WORKFLOW_LEGACY_DOCUMENT_UNSUPPORTED",
            "旧版工作流不能按当前 Studio 格式打开",
            409,
            details={
                "workflowId": row.id,
                "domainCode": "workflow_legacy_document_unsupported",
                "retryable": False,
            },
        )
    return WorkflowRecord(
        document,
        row.revision,
        _aware(row.created_at),
        _aware(row.updated_at),
        project_id or document["content"].get("projectId"),
    )


def _current_document(document: object) -> bool:
    return _canonical_document_shape(document) or _studio_document_shape(document)


def _canonical_document_shape(document: object) -> bool:
    return (
        isinstance(document, dict)
        and document.get("source")
        == {"product": SOURCE_PRODUCT, "commit": SOURCE_COMMIT}
        and document.get("format")
        == {"kind": FORMAT_KIND, "version": FORMAT_VERSION}
        and isinstance(document.get("content"), dict)
    )


def _studio_document_shape(document: object) -> bool:
    return (
        isinstance(document, dict)
        and ("schemaVersion" not in document or document["schemaVersion"] == 3)
        and isinstance(document.get("nodes"), list)
        and isinstance(document.get("edges"), list)
        and isinstance(document.get("variables"), list)
        and all(
            isinstance(node, dict)
            and isinstance(node.get("data"), dict)
            and isinstance(node["data"].get("moduleType"), str)
            for node in document["nodes"]
        )
    )


def _canonical_document(row: WorkflowDocumentRow) -> dict[str, Any] | None:
    """Normalize the direct Studio document at the catalog/runtime boundary.

    Studio and the legacy catalog share the same table but intentionally have
    different transport shapes. Keep the database value untouched and expose
    one canonical WebRPA record to existing project/runtime consumers.
    """
    raw = row.document
    if _canonical_document_shape(raw):
        return deepcopy(raw)
    if not _studio_document_shape(raw):
        return None
    assert isinstance(raw, dict)
    content = deepcopy(raw)
    content.pop("name", None)
    content["id"] = row.id
    content["name"] = row.name
    layout_nodes = row.layout.get("nodes", {}) if isinstance(row.layout, dict) else {}
    if isinstance(layout_nodes, dict):
        for node in content.get("nodes", []):
            if not isinstance(node, dict):
                continue
            layout = layout_nodes.get(node.get("id"))
            if isinstance(layout, dict):
                for key, value in layout.items():
                    node.setdefault(key, deepcopy(value))
    return {
        "id": row.id,
        "source": {"product": SOURCE_PRODUCT, "commit": SOURCE_COMMIT},
        "format": {"kind": FORMAT_KIND, "version": FORMAT_VERSION},
        "content": content,
    }


def _legacy_record(row: WorkflowDocumentRow) -> LegacyWorkflowRecord:
    return LegacyWorkflowRecord(
        row.id,
        row.name,
        deepcopy(row.document),
        deepcopy(row.layout),
        row.revision,
        _aware(row.created_at),
        _aware(row.updated_at),
    )


def _operation_row(
    operation: WorkflowSaveOperation, now: datetime
) -> WorkflowDocumentOperationRow:
    record = operation.record
    return WorkflowDocumentOperationRow(
        save_operation_id=operation.save_operation_id,
        workflow_id=operation.workflow_id,
        request_digest=operation.request_digest,
        result={
            "document": record.document,
            "revision": record.revision,
            "createdAt": record.created_at.isoformat(),
            "updatedAt": record.updated_at.isoformat(),
            "projectId": record.project_id,
        },
        created_at=now,
    )


def _operation(row: WorkflowDocumentOperationRow) -> WorkflowSaveOperation:
    result = row.result
    record = WorkflowRecord(
        result["document"],
        int(result["revision"]),
        datetime.fromisoformat(result["createdAt"]),
        datetime.fromisoformat(result["updatedAt"]),
        result.get("projectId") or result["document"]["content"].get("projectId"),
    )
    return WorkflowSaveOperation(
        row.save_operation_id,
        row.workflow_id,
        row.request_digest,
        record,
    )


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _revision_conflict(
    expected_revision: int, current: WorkflowRecord
) -> WorkflowError:
    return WorkflowError(
        "WORKFLOW_REVISION_CONFLICT",
        "工作流已被修改；请保留当前草稿并重新加载后重试",
        409,
        details={
            "expectedRevision": expected_revision,
            "currentRevision": current.revision,
            "domainCode": "workflow_revision_conflict",
            "retryable": False,
        },
    )


def _operation_mismatch() -> WorkflowError:
    return WorkflowError(
        "OPERATION_PAYLOAD_MISMATCH",
        "幂等键已用于另一请求",
        409,
        details={
            "domainCode": "operation_payload_mismatch",
            "retryable": False,
        },
    )
