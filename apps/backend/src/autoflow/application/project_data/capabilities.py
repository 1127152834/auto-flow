from __future__ import annotations

from autoflow.domain.project_data.capabilities import (
    AddProjectFieldCommand,
    CreateProjectRecordCommand,
    DeleteProjectRecordCommand,
    EnsureProjectFieldCommand,
    ModifyProjectFieldCommand,
    PreviewProjectFieldChangeRequest,
    QueryProjectRecordsRequest,
    QueryProjectTableSchemaRequest,
    ReadProjectRecordRequest,
    SetRecordStatusCommand,
    TaskCapabilityScope,
    UpdateProjectRecordCommand,
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

    def read_record(
        self, scope: TaskCapabilityScope, request: ReadProjectRecordRequest
    ):
        return self.repository.read_record(scope, request)

    def query_table_schema(self, scope: TaskCapabilityScope, request: QueryProjectTableSchemaRequest):
        return self.repository.query_table_schema(scope, request)

    def query_records(
        self, scope: TaskCapabilityScope, request: QueryProjectRecordsRequest
    ):
        return self.repository.query_records(scope, request)

    def update_record(
        self, scope: TaskCapabilityScope, command: UpdateProjectRecordCommand
    ):
        return self.repository.update_record(scope, command)

    def delete_record(
        self, scope: TaskCapabilityScope, command: DeleteProjectRecordCommand
    ):
        return self.repository.delete_record(scope, command)

    def create_record(
        self, scope: TaskCapabilityScope, command: CreateProjectRecordCommand
    ):
        return self.repository.create_record(scope, command)

    def add_field(self, scope: TaskCapabilityScope, command: AddProjectFieldCommand):
        return self.repository.add_field(scope, command)

    def ensure_field(
        self, scope: TaskCapabilityScope, command: EnsureProjectFieldCommand
    ):
        return self.repository.ensure_field(scope, command)

    def modify_field(
        self, scope: TaskCapabilityScope, command: ModifyProjectFieldCommand
    ):
        return self.repository.modify_field(scope, command)

    def preview_field_change(
        self, scope: TaskCapabilityScope, request: PreviewProjectFieldChangeRequest
    ):
        return self.repository.preview_field_change(scope, request)

    def query_operation(self, scope: TaskCapabilityScope, operation_id: str):
        return self.repository.query_operation(scope, operation_id)
