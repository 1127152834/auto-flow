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
from autoflow.domain.workflows.modules import custom_module_reference
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
        custom_module_exists: Callable[[str], bool] = lambda _module_id: True,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._custom_module_exists = custom_module_exists

    def create(
        self, payload: Mapping[str, Any], *, client_request_id: str
    ) -> SavedWorkflow:
        if not client_request_id:
            raise WorkflowDocumentError("INVALID_REQUEST_ID", "请求 ID 不能为空", 422)
        draft = WorkflowDraft.from_payload(payload)
        self._validate_custom_modules(draft)
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
        self, *, cursor: int = 0, limit: int = 50, project_id: str | None = None
    ) -> WorkflowSummaryPage:
        if cursor < 0 or limit < 1 or limit > 200:
            raise WorkflowDocumentError("INVALID_PAGE", "分页参数无效", 422)
        return self._repository.list_summaries(cursor, limit, project_id)

    def update(
        self,
        workflow_id: str,
        payload: Mapping[str, Any],
        *,
        expected_revision: int,
        client_request_id: str,
    ) -> SavedWorkflow:
        draft = WorkflowDraft.from_payload(payload).with_id(workflow_id)
        self._validate_custom_modules(draft)
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

    def referencing_custom_module_ids(self, module_id: str) -> tuple[str, ...]:
        """Return saved workflows that currently reference a custom module."""
        workflow_ids: list[str] = []
        cursor = 0
        while True:
            page = self._repository.list_summaries(cursor, 200)
            for summary in page.items:
                saved = self._repository.get(summary.id)
                if saved is None:
                    continue
                nodes = saved.document.get("nodes", [])
                if isinstance(nodes, list) and any(
                    isinstance(node, Mapping)
                    and custom_module_reference(node) == module_id
                    for node in nodes
                ):
                    workflow_ids.append(saved.id)
            if page.next_cursor is None:
                break
            cursor = page.next_cursor
        return tuple(workflow_ids)

    def _validate_custom_modules(self, draft: WorkflowDraft) -> None:
        nodes = draft.document.get("nodes", [])
        if not isinstance(nodes, list):
            return
        for index, node in enumerate(nodes):
            if not isinstance(node, Mapping):
                continue
            data = node.get("data")
            module_type = (
                data.get("moduleType")
                if isinstance(data, Mapping)
                else node.get("type")
            )
            if module_type != "custom_module":
                continue
            module_id = custom_module_reference(node)
            if not module_id:
                raise WorkflowDocumentError(
                    "CUSTOM_MODULE_REFERENCE_REQUIRED",
                    "自定义模块节点未选择模块",
                    422,
                    {"path": f"nodes.{index}.data.customModuleId"},
                )
            if not self._custom_module_exists(module_id):
                raise WorkflowDocumentError(
                    "CUSTOM_MODULE_DEPENDENCY_MISSING",
                    f"自定义模块依赖不存在: {module_id}",
                    422,
                    {
                        "path": f"nodes.{index}.data.customModuleId",
                        "moduleId": module_id,
                    },
                )
