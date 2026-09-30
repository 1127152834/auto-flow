from __future__ import annotations

from typing import Any, cast

from autoflow.domain.project_data.capabilities import (
    AddProjectFieldCommand,
    CreateProjectRecordCommand,
    DeleteProjectFieldCommand,
    DeleteProjectRecordCommand,
    EnsureProjectFieldCommand,
    ModifyProjectFieldCommand,
    PreviewProjectFieldChangeRequest,
    PreviewProjectFieldDeletionRequest,
    QueryProjectRecordsRequest,
    QueryProjectTableSchemaRequest,
    ReadProjectRecordRequest,
    SetRecordStatusCommand,
    TaskCapabilityScope,
    UpdateProjectRecordCommand,
)


class ProjectDataCapabilityService:
    """The internal workflow-facing boundary for explicit project data writes."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def scope(
        self,
        project_id: str,
        task_id: str,
        run_id: str,
    ) -> TaskCapabilityScope:
        return cast(TaskCapabilityScope, self.repository.scope(project_id, task_id, run_id))

    def set_record_status(
        self, scope: TaskCapabilityScope, command: SetRecordStatusCommand
    ) -> tuple[dict[str, Any], bool]:
        return cast(
            tuple[dict[str, Any], bool],
            self.repository.set_record_status(scope, command),
        )

    def read_record(
        self, scope: TaskCapabilityScope, request: ReadProjectRecordRequest
    ) -> dict[str, Any]:
        return cast(dict[str, Any], self.repository.read_record(scope, request))

    def query_table_schema(
        self,
        scope: TaskCapabilityScope,
        request: QueryProjectTableSchemaRequest,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], self.repository.query_table_schema(scope, request))

    def query_records(
        self, scope: TaskCapabilityScope, request: QueryProjectRecordsRequest
    ) -> dict[str, Any]:
        return cast(dict[str, Any], self.repository.query_records(scope, request))

    def update_record(
        self, scope: TaskCapabilityScope, command: UpdateProjectRecordCommand
    ) -> tuple[dict[str, Any], bool]:
        return cast(
            tuple[dict[str, Any], bool],
            self.repository.update_record(scope, command),
        )

    def delete_record(
        self, scope: TaskCapabilityScope, command: DeleteProjectRecordCommand
    ) -> tuple[dict[str, Any], bool]:
        return cast(
            tuple[dict[str, Any], bool],
            self.repository.delete_record(scope, command),
        )

    def create_record(
        self, scope: TaskCapabilityScope, command: CreateProjectRecordCommand
    ) -> tuple[dict[str, Any], bool]:
        return cast(
            tuple[dict[str, Any], bool],
            self.repository.create_record(scope, command),
        )

    def add_field(
        self, scope: TaskCapabilityScope, command: AddProjectFieldCommand
    ) -> tuple[dict[str, Any], bool]:
        return cast(
            tuple[dict[str, Any], bool], self.repository.add_field(scope, command)
        )

    def ensure_field(
        self, scope: TaskCapabilityScope, command: EnsureProjectFieldCommand
    ) -> tuple[dict[str, Any], bool]:
        return cast(
            tuple[dict[str, Any], bool], self.repository.ensure_field(scope, command)
        )

    def preview_field_deletion(
        self,
        scope: TaskCapabilityScope,
        request: PreviewProjectFieldDeletionRequest,
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any], self.repository.preview_field_deletion(scope, request)
        )

    def delete_field(
        self, scope: TaskCapabilityScope, command: DeleteProjectFieldCommand
    ) -> tuple[dict[str, Any], bool]:
        return cast(
            tuple[dict[str, Any], bool], self.repository.delete_field(scope, command)
        )

    def modify_field(
        self, scope: TaskCapabilityScope, command: ModifyProjectFieldCommand
    ) -> tuple[dict[str, Any], bool]:
        return cast(
            tuple[dict[str, Any], bool], self.repository.modify_field(scope, command)
        )

    def preview_field_change(
        self, scope: TaskCapabilityScope, request: PreviewProjectFieldChangeRequest
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any], self.repository.preview_field_change(scope, request)
        )

    def query_operation(
        self, scope: TaskCapabilityScope, operation_id: str
    ) -> dict[str, Any] | None:
        return cast(
            dict[str, Any] | None,
            self.repository.query_operation(scope, operation_id),
        )
