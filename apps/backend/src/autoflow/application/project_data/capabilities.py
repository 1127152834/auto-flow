from __future__ import annotations

from autoflow.domain.project_data.capabilities import (
    CreateProjectRecordCommand,
    SetRecordStatusCommand,
    TaskCapabilityScope,
)


class ProjectDataCapabilityService:
    """The internal workflow-facing boundary for explicit project data writes."""

    def __init__(self, repository):
        self.repository = repository

    def scope(
        self,
        project_id: str,
        task_id: str,
        run_id: str,
    ) -> TaskCapabilityScope:
        return self.repository.scope(project_id, task_id, run_id)

    def set_record_status(
        self, scope: TaskCapabilityScope, command: SetRecordStatusCommand
    ):
        return self.repository.set_record_status(scope, command)

    def create_record(
        self, scope: TaskCapabilityScope, command: CreateProjectRecordCommand
    ):
        return self.repository.create_record(scope, command)

    def query_operation(self, scope: TaskCapabilityScope, operation_id: str):
        return self.repository.query_operation(scope, operation_id)
