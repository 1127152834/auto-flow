from __future__ import annotations

import builtins
from typing import Any, Protocol

from autoflow.domain.projects.models import ProjectOperation

from .models import AutomationRecord


class ProjectAutomations(Protocol):
    def create(
        self, record: AutomationRecord, operation: ProjectOperation
    ) -> tuple[AutomationRecord, ProjectOperation, bool]: ...
    def update(
        self,
        project_id: str,
        automation_id: str,
        values: dict[str, Any],
        expected_revision: int,
        operation: ProjectOperation,
    ) -> tuple[AutomationRecord, ProjectOperation]: ...
    def get(self, project_id: str, automation_id: str) -> AutomationRecord | None: ...
    def impact(
        self, project_id: str, automation_id: str, action: str
    ) -> dict[str, Any]: ...
    def delete(
        self,
        project_id: str,
        automation_id: str,
        operation: ProjectOperation,
        *,
        impact_revision: int,
        expected_revision: int,
        disposition: str,
    ) -> ProjectOperation: ...
    def list(
        self, project_id: str, q: str | None, page: int, page_size: int, sort: str
    ) -> tuple[builtins.list[AutomationRecord], int]: ...


class AutomationWorkflowQuery(Protocol):
    def inspect_workflow(self, workflow_id: str) -> dict[str, Any] | None: ...


class AutomationResourceQuery(Protocol):
    def inspect_resources(
        self, automation: AutomationRecord
    ) -> list[dict[str, Any]]: ...


class AutomationCapabilityQuery(Protocol):
    def inspect_capabilities(self, workflow_id: str) -> list[dict[str, Any]]: ...
