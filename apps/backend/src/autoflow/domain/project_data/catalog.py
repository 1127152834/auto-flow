from __future__ import annotations

from typing import Any, Protocol

from autoflow.domain.projects.models import ProjectOperation


class ProjectDataCatalog(Protocol):
    def preview_field_update(
        self, project_id: str, ref: dict[str, Any], definition: dict[str, Any]
    ) -> dict[str, Any]: ...

    def fields(self, project_id: str, table_id: str) -> dict[str, Any]: ...

    def create_field(
        self,
        project_id: str,
        table_id: str,
        field_id: str,
        definition: dict[str, Any],
        has_default: bool,
        default: object,
        expected_revision: int,
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]: ...

    def update_field(
        self,
        project_id: str,
        table_id: str,
        field_id: str,
        definition: dict[str, Any],
        expected_table_revision: int,
        expected_field_revision: int,
        impact_revision: int,
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]: ...

    def statuses(self, project_id: str, table_id: str) -> dict[str, Any]: ...

    def status_usage(self, project_id: str, table_id: str) -> dict[str, Any]: ...

    def create_status(
        self,
        project_id: str,
        table_id: str,
        status_id: str,
        value: dict[str, Any],
        expected_revision: int,
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]: ...

    def update_status(
        self,
        project_id: str,
        table_id: str,
        status_id: str,
        patch: dict[str, Any],
        expected_table_revision: int,
        expected_status_revision: int,
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]: ...
