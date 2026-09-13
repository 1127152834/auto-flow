from __future__ import annotations

from typing import Any, Protocol

from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.projects.models import ProjectOperation

WriteResult = tuple[dict[str, Any], ProjectOperation, bool]


class ProjectDataDeletions(Protocol):
    def preview_status(
        self, project_id: str, table_id: str, status_id: str
    ) -> dict[str, Any]: ...

    def preview_record(
        self, project_id: str, table_id: str, generation: str, key: RecordKey
    ) -> dict[str, Any]: ...

    def delete_status(
        self,
        project_id: str,
        table_id: str,
        status_id: str,
        expected_status: int,
        expected_table: int,
        impact: int,
        operation: ProjectOperation,
    ) -> WriteResult: ...

    def delete_record(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        key: RecordKey,
        expected_content: int,
        expected_status: int,
        expected_link: int,
        impact: int,
        operation: ProjectOperation,
    ) -> WriteResult: ...
