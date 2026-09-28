from __future__ import annotations

from dataclasses import MISSING, fields
from typing import TYPE_CHECKING, Any
from uuid import UUID

from autoflow.domain.project_data.capabilities import (
    AddProjectFieldCommand,
    CreateProjectRecordCommand,
    DeleteProjectRecordCommand,
    EnsureProjectFieldCommand,
    ModifyProjectFieldCommand,
    PreviewProjectFieldChangeRequest,
    QueryProjectRecordsRequest,
    ReadProjectRecordRequest,
    SetRecordStatusCommand,
    TaskCapabilityScope,
    UpdateProjectRecordCommand,
)
from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.projects.models import ProjectError

if TYPE_CHECKING:
    from autoflow.application.project_runs.end import ProjectRunEnd

_WORKER_COMMANDS = {
    "read": (ReadProjectRecordRequest, "read_record"),
    "query": (QueryProjectRecordsRequest, "query_records"),
    "update": (UpdateProjectRecordCommand, "update_record"),
    "status": (SetRecordStatusCommand, "set_record_status"),
    "create": (CreateProjectRecordCommand, "create_record"),
    "delete": (DeleteProjectRecordCommand, "delete_record"),
    "addField": (AddProjectFieldCommand, "add_field"),
    "ensureField": (EnsureProjectFieldCommand, "ensure_field"),
    "modifyField": (ModifyProjectFieldCommand, "modify_field"),
    "previewField": (PreviewProjectFieldChangeRequest, "preview_field_change"),
}


class ProjectDataCapabilityService:
    """The internal workflow-facing boundary for explicit project data writes."""

    def __init__(self, repository, *, project_end: ProjectRunEnd | None = None) -> None:
        self.repository = repository
        self.project_end = project_end

    def worker_call(self, run_id: str, generation: int, request: dict[str, Any]) -> dict[str, Any]:
        """Decode only fixed commands; identity comes from the owning host pipe."""
        if request.get("capability") == "project.end" and self.project_end is not None:
            return self.project_end.worker_call(run_id, generation, request)
        try:
            if set(request) != {
                "nodeId",
                "nodeVisitId",
                "attempt",
                "commandId",
                "capability",
                "arguments",
            }:
                raise ValueError("Unexpected worker identity or request field")
            if any(
                not isinstance(request[key], str) or not 1 <= len(request[key]) <= 120
                for key in ("nodeId", "nodeVisitId")
            ):
                raise ValueError("Invalid node visit")
            if type(request["attempt"]) is not int or request["attempt"] < 1:
                raise ValueError("Invalid attempt")
            command_id = request["commandId"]
            if not isinstance(command_id, str) or str(UUID(command_id)) != command_id:
                raise ValueError("Invalid command identity")
            capability = request["capability"]
            if not isinstance(capability, str) or not capability.startswith(
                "project.data."
            ):
                raise ValueError("Unknown capability")
            action = capability.removeprefix("project.data.")
            if action not in {*_WORKER_COMMANDS, "inputs", "operation"}:
                raise ValueError("Unknown capability")
            arguments = request["arguments"]
            if not isinstance(arguments, dict):
                raise TypeError("Invalid capability arguments")
            scope, inputs = self.repository.worker_context(run_id, generation, request)
            if action == "inputs":
                if arguments:
                    raise ValueError("Input snapshots take no selectors")
                return {"inputs": inputs}
            if action == "operation":
                if set(arguments) != {"operationId"} or not isinstance(
                    arguments["operationId"], str
                ):
                    raise ValueError("Expected original operation identity")
                result = self.query_operation(scope, arguments["operationId"])
                return {
                    "operation": _write_receipt(result) if result is not None else None
                }
            command_type, method = _WORKER_COMMANDS[action]
            values: dict[str, Any] = {}
            allowed = set()
            for field in fields(command_type):
                if field.name in {"operation_id", "execution_generation", "project_id"}:
                    values[field.name] = {
                        "operation_id": command_id,
                        "execution_generation": generation,
                        "project_id": scope.project_id,
                    }[field.name]
                    continue
                first, *rest = field.name.split("_")
                key = first + "".join(part.title() for part in rest)
                allowed.add(key)
                if key in arguments:
                    values[field.name] = arguments[key]
                elif field.default is MISSING:
                    raise ValueError(f"Missing {key}")
            if set(arguments) - allowed:
                raise ValueError("Unexpected capability argument")
            if "record_ref" in values:
                ref = values["record_ref"]
                if not isinstance(ref, dict) or set(ref) != {
                    "projectId",
                    "tableId",
                    "datasetGeneration",
                    "recordKey",
                }:
                    raise ValueError("Invalid record reference")
                key = ref["recordKey"]
                if not isinstance(key, dict) or set(key) != {"type", "value"}:
                    raise ValueError("Invalid record key")
                values["record_ref"] = RecordRef(
                    ref["projectId"],
                    ref["tableId"],
                    ref["datasetGeneration"],
                    RecordKey(key["type"], key["value"]),
                )
            result = getattr(self, method)(scope, command_type(**values))
            if isinstance(result, tuple):
                value, replayed = result
                return {"result": _write_receipt(value), "replayed": replayed}
            return {"result": result}
        except (ValueError, TypeError, KeyError) as error:
            raise ProjectError(
                "VALIDATION_ERROR", "Invalid project data capability request", 422
            ) from error

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


def _write_receipt(result: dict[str, Any]) -> dict[str, Any]:
    # Write authority does not grant reads of the other fields in a row.
    # Keep the complete snapshot in the durable operation/audit only.
    return {key: value for key, value in result.items() if key != "values"}
