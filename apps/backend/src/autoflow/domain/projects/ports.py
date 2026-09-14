from __future__ import annotations

import builtins
from datetime import datetime
from typing import Any, Protocol

from .models import ProjectOperation, ProjectRecord


class Projects(Protocol):
    def create(
        self, record: ProjectRecord, operation: ProjectOperation
    ) -> tuple[ProjectRecord, ProjectOperation]: ...
    def update(
        self,
        project_id: str,
        patch: dict[str, Any],
        expected_revision: int,
        operation: ProjectOperation,
    ) -> tuple[ProjectRecord, ProjectOperation]: ...
    def get(self, project_id: str) -> ProjectRecord | None: ...
    def list(
        self,
        q: str | None = None,
        lifecycle_state: str | None = None,
        page: int = 1,
        page_size: int = 50,
        sort: str = "-lastOpenedAt",
    ) -> tuple[builtins.list[ProjectRecord], int]: ...
    def open(self, project_id: str, now: datetime) -> ProjectRecord: ...
    def get_operation(
        self,
        operation_id: str | None = None,
        key: str | None = None,
        project_id: str | None = None,
        workspace: bool = False,
    ) -> ProjectOperation | None: ...
    def list_operations(
        self,
        project_id: str,
        page: int = 1,
        page_size: int = 50,
        kind: str | None = None,
        status: str | None = None,
        resource_type: str | None = None,
    ) -> tuple[builtins.list[ProjectOperation], int]: ...
