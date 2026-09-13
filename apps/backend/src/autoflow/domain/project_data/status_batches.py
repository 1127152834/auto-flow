from __future__ import annotations

from typing import Any, Protocol

from autoflow.domain.projects.models import ProjectOperation


class RecordStatusBatchRepository(Protocol):
    def preview(
        self, project_id: str, table_id: str, request: dict[str, Any]
    ) -> dict[str, Any]: ...
    def accept(
        self,
        project_id: str,
        table_id: str,
        request: dict[str, Any],
        operation: ProjectOperation,
    ) -> tuple[ProjectOperation, bool]: ...
    def process_block(self, operation_id: str) -> bool: ...
    def fail(self, operation_id: str, error: Exception) -> None: ...
    def cancel(
        self,
        project_id: str,
        table_id: str,
        operation_id: str,
        expected_revision: int,
        command: ProjectOperation,
    ) -> tuple[ProjectOperation, bool]: ...
    def pending_operation_ids(self) -> list[str]: ...
