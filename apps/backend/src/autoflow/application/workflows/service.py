from datetime import UTC, datetime
from typing import Any

from autoflow.domain.workflows.models import (
    WorkflowError,
    WorkflowRecord,
    WorkflowRepository,
)
from autoflow.domain.workflows.validation import validate_structure


class WorkflowService:
    def __init__(self, repository: WorkflowRepository):
        self.repository = repository

    def list(self) -> list[WorkflowRecord]:
        return self.repository.list()

    def get(self, workflow_id: str) -> WorkflowRecord:
        record = self.repository.get(workflow_id)
        if record is None:
            raise WorkflowError("WORKFLOW_NOT_FOUND", "工作流不存在", 404)
        return record

    def create(
        self, document: dict[str, Any], layout: dict[str, Any]
    ) -> WorkflowRecord:
        validate_structure(document, layout)
        now = datetime.now(UTC)
        return self.repository.create(WorkflowRecord(document, layout, 1, now, now))

    def save(
        self,
        workflow_id: str,
        document: dict[str, Any],
        layout: dict[str, Any],
        expected_revision: int,
    ) -> WorkflowRecord:
        if workflow_id != document["id"]:
            raise WorkflowError("WORKFLOW_ID_MISMATCH", "路径与文档标识不一致", 422)
        validate_structure(document, layout)
        now = datetime.now(UTC)
        return self.repository.save(
            WorkflowRecord(document, layout, expected_revision + 1, now, now),
            expected_revision,
        )
