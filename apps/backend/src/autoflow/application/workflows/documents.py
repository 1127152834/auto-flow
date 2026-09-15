from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from autoflow.domain.workflows.document import (
    SavedWorkflow,
    WorkflowDraft,
    WorkflowSummaryPage,
)
from autoflow.domain.workflows.errors import WorkflowDocumentError
from autoflow.domain.workflows.ports import WorkflowDocumentRepository


def _digest(draft: WorkflowDraft, operation: str, expected_revision: int | None) -> str:
    value = {
        "operation": operation,
        "expectedRevision": expected_revision,
        "payload": draft.to_payload(),
    }
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class WorkflowDocumentService:
    def __init__(
        self,
        repository: WorkflowDocumentRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._clock = clock

    def create(
        self, payload: Mapping[str, Any], *, client_request_id: str
    ) -> SavedWorkflow:
        if not client_request_id:
            raise WorkflowDocumentError("INVALID_REQUEST_ID", "请求 ID 不能为空", 422)
        draft = WorkflowDraft.from_payload(payload)
        workflow_id = draft.id or str(
            uuid5(NAMESPACE_URL, f"autoflow-workflow:{client_request_id}")
        )
        draft = draft.with_id(workflow_id)
        return self._repository.create(
            draft,
            client_request_id=client_request_id,
            request_digest=_digest(draft, "create", None),
            now=self._clock(),
        )

    def get(self, workflow_id: str) -> SavedWorkflow:
        document = self._repository.get(workflow_id)
        if document is None:
            raise WorkflowDocumentError("WORKFLOW_NOT_FOUND", "工作流不存在", 404)
        return document

    def list_summaries(
        self, *, cursor: int = 0, limit: int = 50
    ) -> WorkflowSummaryPage:
        if cursor < 0 or limit < 1 or limit > 200:
            raise WorkflowDocumentError("INVALID_PAGE", "分页参数无效", 422)
        return self._repository.list_summaries(cursor, limit)

    def update(
        self,
        workflow_id: str,
        payload: Mapping[str, Any],
        *,
        expected_revision: int,
        client_request_id: str,
    ) -> SavedWorkflow:
        draft = WorkflowDraft.from_payload(payload).with_id(workflow_id)
        return self._repository.update(
            workflow_id,
            draft,
            expected_revision=expected_revision,
            client_request_id=client_request_id,
            request_digest=_digest(draft, "update", expected_revision),
            now=self._clock(),
        )

    def delete(self, workflow_id: str, *, expected_revision: int) -> None:
        self._repository.delete(workflow_id, expected_revision=expected_revision)
