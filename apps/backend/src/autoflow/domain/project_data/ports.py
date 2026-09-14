from __future__ import annotations

import builtins
from typing import Protocol

from autoflow.domain.project_data.models import DataTable
from autoflow.domain.projects.models import ProjectOperation


class ProjectDataTables(Protocol):
    def create(
        self, table: DataTable, operation: ProjectOperation
    ) -> tuple[dict, ProjectOperation, bool]: ...

    def update(
        self,
        project_id: str,
        table_id: str,
        patch: dict,
        expected_revision: int,
        operation: ProjectOperation,
    ) -> tuple[dict, ProjectOperation, bool]: ...

    def get(self, project_id: str, table_id: str) -> dict | None: ...

    def list(
        self,
        project_id: str,
        q: str | None,
        source_kind: str | None,
        page: int,
        page_size: int,
        sort: str,
    ) -> tuple[builtins.list[dict], int]: ...
