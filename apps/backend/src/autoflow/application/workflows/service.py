from __future__ import annotations

import builtins
import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from autoflow.domain.workflows.models import (
    LegacyWorkflowRecord,
    WorkflowError,
    WorkflowRecord,
    WorkflowRepository,
    WorkflowSaveOperation,
    canonical_json,
)
from autoflow.domain.workflows.references import require_canonical_uuid
from autoflow.domain.workflows.validation import project_document


class WorkflowService:
    def __init__(
        self,
        repository: WorkflowRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

    def list(self) -> list[WorkflowRecord]:
        return self._repository.list()

    def list_legacy(self) -> builtins.list[LegacyWorkflowRecord]:
        return self._repository.list_legacy()

    def export_legacy(self, workflow_id: object) -> LegacyWorkflowRecord:
        if not isinstance(workflow_id, str) or workflow_id == "":
            raise WorkflowError(
                "VALIDATION_ERROR",
                "请求参数无效",
                422,
                details={
                    "fields": {"workflowId": "必须是非空旧工作流标识"},
                    "domainCode": "validation_error",
                    "retryable": False,
                },
            )
        record = self._repository.get_legacy(workflow_id)
        if record is None:
            raise WorkflowError("WORKFLOW_LEGACY_DOCUMENT_NOT_FOUND", "旧工作流不存在", 404)
        return record

    def get(self, workflow_id: str) -> WorkflowRecord:
        workflow_id = require_canonical_uuid(workflow_id, "workflowId")
        record = self._repository.get(workflow_id)
        if record is None:
            raise WorkflowError("WORKFLOW_NOT_FOUND", "工作流不存在", 404)
        return record

    def create(
        self, document: object, save_operation_id: str
    ) -> WorkflowRecord:
        projected = _project_request_document(document)
        return self._save(
            projected["id"], projected, 0, save_operation_id
        ).record

    def save(
        self,
        workflow_id: str,
        document: object,
        expected_revision: int,
        save_operation_id: str,
    ) -> WorkflowRecord:
        workflow_id = require_canonical_uuid(workflow_id, "workflowId")
        projected = _project_request_document(document)
        if projected["id"] != workflow_id:
            raise WorkflowError(
                "WORKFLOW_ID_MISMATCH",
                "路径与文档标识不一致",
                422,
                details={
                    "domainCode": "workflow_id_mismatch",
                    "retryable": False,
                },
            )
        return self._save(
            workflow_id,
            projected,
            expected_revision,
            save_operation_id,
        ).record

    def query_save(self, save_operation_id: str) -> WorkflowSaveOperation:
        save_operation_id = require_canonical_uuid(
            save_operation_id, "saveOperationId"
        )
        operation = self._repository.get_save_operation(save_operation_id)
        if operation is None:
            raise WorkflowError(
                "WORKFLOW_SAVE_OPERATION_NOT_FOUND",
                "工作流保存操作不存在",
                404,
            )
        return operation

    def _save(
        self,
        workflow_id: str,
        document: dict[str, Any],
        expected_revision: int,
        save_operation_id: str,
    ) -> WorkflowSaveOperation:
        workflow_id = require_canonical_uuid(workflow_id, "workflowId")
        save_operation_id = require_canonical_uuid(
            save_operation_id, "saveOperationId"
        )
        if type(expected_revision) is not int or expected_revision < 0:
            raise WorkflowError(
                "VALIDATION_ERROR",
                "请求参数无效",
                422,
                details={
                    "fields": {"expectedRevision": "必须是非负整数"},
                    "domainCode": "validation_error",
                    "retryable": False,
                },
            )
        digest = hashlib.sha256(
            canonical_json(
                {
                    "kind": "saveWorkflow",
                    "workflowId": workflow_id,
                    "expectedRevision": expected_revision,
                    "document": document,
                }
            ).encode()
        ).hexdigest()
        return self._repository.save(
            document,
            expected_revision,
            save_operation_id,
            digest,
            self._clock(),
        )


def _project_request_document(document: object) -> dict[str, Any]:
    if not isinstance(document, dict):
        return project_document(document)
    require_canonical_uuid(document.get("id"), "document.id")
    return project_document(document)
