from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any
from uuid import UUID

from autoflow.domain.project_data.identity import (
    MAX_SAFE_INTEGER,
    RecordKey,
    encode_record_key,
)
from autoflow.domain.project_data.rules import validate_field, validate_value
from autoflow.domain.project_data.schema import canonical_bytes
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.projects.models import ProjectError


@dataclass(frozen=True)
class SetRecordStatusCommand:
    operation_id: str
    execution_generation: int
    record_ref: RecordRef
    status_id: str | None
    expected_status_revision: int
    expected_content_revision_when_derived: int | None = None
    allowed_from: tuple[str | None, ...] | None = None

    def __post_init__(self) -> None:
        _uuid(self.operation_id, "operationId")
        _generation(self.execution_generation)
        _record_ref(self.record_ref, "recordRef")
        if self.status_id is not None:
            _uuid(self.status_id, "statusId")
        _positive_integer(self.expected_status_revision, "expectedStatusRevision")
        if self.expected_content_revision_when_derived is not None:
            _positive_integer(
                self.expected_content_revision_when_derived,
                "expectedContentRevisionWhenDerived",
            )
        if self.allowed_from is not None:
            if not isinstance(self.allowed_from, list | tuple) or not self.allowed_from:
                raise _validation("allowedFrom", "must be a non-empty array")
            allowed = tuple(
                None if value is None else _uuid(value, f"allowedFrom.{index}")
                for index, value in enumerate(self.allowed_from)
            )
            if len(allowed) != len(set(allowed)):
                raise _validation("allowedFrom", "must not contain duplicates")
            object.__setattr__(
                self,
                "allowed_from",
                tuple(
                    sorted(allowed, key=lambda value: "" if value is None else value)
                ),
            )

    @property
    def request_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": "setRecordStatus",
            "executionGeneration": self.execution_generation,
            "recordRef": _record_ref_payload(self.record_ref),
            "statusId": self.status_id,
            "expectedStatusRevision": self.expected_status_revision,
        }
        if self.expected_content_revision_when_derived is not None:
            payload["expectedContentRevisionWhenDerived"] = (
                self.expected_content_revision_when_derived
            )
        if self.allowed_from is not None:
            payload["allowedFrom"] = list(self.allowed_from)
        return payload

    @property
    def request_digest(self) -> str:
        return hashlib.sha256(canonical_bytes(self.request_payload)).hexdigest()

    @property
    def idempotency_identity(self) -> tuple[str, str]:
        return self.operation_id, self.request_digest


@dataclass(frozen=True)
class CreateProjectRecordCommand:
    operation_id: str
    execution_generation: int
    project_id: str
    table_id: str
    dataset_generation: str
    values: Mapping[str, Any]

    def __post_init__(self) -> None:
        _uuid(self.operation_id, "operationId")
        _generation(self.execution_generation)
        _uuid(self.project_id, "projectId")
        _uuid(self.table_id, "tableId")
        _uuid(self.dataset_generation, "datasetGeneration")
        object.__setattr__(self, "values", _freeze_json_object(self.values, "values"))

    @property
    def request_payload(self) -> dict[str, Any]:
        return {
            "kind": "createRecord",
            "executionGeneration": self.execution_generation,
            "projectId": self.project_id,
            "tableId": self.table_id,
            "datasetGeneration": self.dataset_generation,
            "values": _thaw_json(self.values),
        }

    @property
    def request_digest(self) -> str:
        return hashlib.sha256(canonical_bytes(self.request_payload)).hexdigest()

    @property
    def idempotency_identity(self) -> tuple[str, str]:
        return self.operation_id, self.request_digest


@dataclass(frozen=True)
class ReadProjectRecordRequest:
    execution_generation: int
    record_ref: RecordRef
    field_ids: tuple[str, ...] | list[str]
    read_purpose: str

    def __post_init__(self) -> None:
        _generation(self.execution_generation)
        _record_ref(self.record_ref, "recordRef")
        object.__setattr__(self, "field_ids", _field_ids(self.field_ids, "fieldIds"))
        object.__setattr__(
            self, "read_purpose", _read_purpose(self.read_purpose, "readPurpose")
        )

    @property
    def request_payload(self) -> dict[str, Any]:
        return {
            "kind": "readProjectRecord",
            "executionGeneration": self.execution_generation,
            "recordRef": _record_ref_payload(self.record_ref),
            "fieldIds": list(self.field_ids),
            "readPurpose": self.read_purpose,
        }

    @property
    def request_digest(self) -> str:
        return _payload_digest(self.request_payload)


@dataclass(frozen=True)
class QueryProjectTableSchemaRequest:
    execution_generation: int
    project_id: str
    table_id: str
    dataset_generation: str
    field_ids: tuple[str, ...] | list[str]

    def __post_init__(self) -> None:
        _generation(self.execution_generation)
        _table_identity(self.project_id, self.table_id, self.dataset_generation)
        field_ids = _field_ids(self.field_ids, "fieldIds")
        if not field_ids:
            raise _validation("fieldIds", "must explicitly select at least one field")
        object.__setattr__(self, "field_ids", field_ids)


@dataclass(frozen=True)
class QueryProjectRecordsRequest:
    execution_generation: int
    project_id: str
    table_id: str
    dataset_generation: str
    field_ids: tuple[str, ...] | list[str]
    read_purpose: str
    filter: Mapping[str, Any] | None
    order_by: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]]
    cursor: str | None
    limit: int

    def __post_init__(self) -> None:
        _generation(self.execution_generation)
        _uuid(self.project_id, "projectId")
        _uuid(self.table_id, "tableId")
        _uuid(self.dataset_generation, "datasetGeneration")
        object.__setattr__(self, "field_ids", _field_ids(self.field_ids, "fieldIds"))
        object.__setattr__(
            self, "read_purpose", _read_purpose(self.read_purpose, "readPurpose")
        )
        if self.filter is not None:
            object.__setattr__(
                self, "filter", _freeze_json_object(self.filter, "filter")
            )
        if not isinstance(self.order_by, list | tuple):
            raise _validation("orderBy", "must be an array")
        frozen_order = tuple(
            _freeze_json_object(item, f"orderBy.{index}")
            for index, item in enumerate(self.order_by)
        )
        object.__setattr__(self, "order_by", frozen_order)
        if self.cursor is not None and (
            type(self.cursor) is not str
            or not self.cursor
            or len(self.cursor.encode("utf-8")) > 64 * 1024
        ):
            raise _validation("cursor", "must be a non-empty cursor")
        if type(self.limit) is not int or not 1 <= self.limit <= 200:
            raise _validation("limit", "must be an integer from 1 to 200")

    @property
    def request_payload(self) -> dict[str, Any]:
        return {
            "kind": "queryProjectRecords",
            "executionGeneration": self.execution_generation,
            "projectId": self.project_id,
            "tableId": self.table_id,
            "datasetGeneration": self.dataset_generation,
            "fieldIds": list(self.field_ids),
            "readPurpose": self.read_purpose,
            "filter": None if self.filter is None else _thaw_json(self.filter),
            "orderBy": [_thaw_json(item) for item in self.order_by],
            "cursor": self.cursor,
            "limit": self.limit,
        }

    @property
    def request_digest(self) -> str:
        return _payload_digest(self.request_payload)


@dataclass(frozen=True)
class UpdateProjectRecordCommand:
    operation_id: str
    execution_generation: int
    record_ref: RecordRef
    changes: Mapping[str, Any]
    expected_content_revision: int

    def __post_init__(self) -> None:
        _uuid(self.operation_id, "operationId")
        _generation(self.execution_generation)
        _record_ref(self.record_ref, "recordRef")
        changes = _freeze_field_values(self.changes, "changes", allow_empty=False)
        object.__setattr__(self, "changes", changes)
        _positive_integer(self.expected_content_revision, "expectedContentRevision")

    @property
    def request_payload(self) -> dict[str, Any]:
        return {
            "kind": "updateRecord",
            "executionGeneration": self.execution_generation,
            "recordRef": _record_ref_payload(self.record_ref),
            "changes": _thaw_json(self.changes),
            "expectedContentRevision": self.expected_content_revision,
        }

    @property
    def request_digest(self) -> str:
        return _payload_digest(self.request_payload)

    @property
    def idempotency_identity(self) -> tuple[str, str]:
        return self.operation_id, self.request_digest


@dataclass(frozen=True)
class DeleteProjectRecordCommand:
    operation_id: str
    execution_generation: int
    record_ref: RecordRef
    expected_content_revision: int
    expected_status_revision: int
    expected_link_revision: int

    def __post_init__(self) -> None:
        _uuid(self.operation_id, "operationId")
        _generation(self.execution_generation)
        _record_ref(self.record_ref, "recordRef")
        _positive_integer(self.expected_content_revision, "expectedContentRevision")
        _positive_integer(self.expected_status_revision, "expectedStatusRevision")
        _positive_integer(self.expected_link_revision, "expectedLinkRevision")

    @property
    def request_payload(self) -> dict[str, Any]:
        return {
            "kind": "deleteRecord",
            "executionGeneration": self.execution_generation,
            "recordRef": _record_ref_payload(self.record_ref),
            "expectedContentRevision": self.expected_content_revision,
            "expectedStatusRevision": self.expected_status_revision,
            "expectedLinkRevision": self.expected_link_revision,
        }

    @property
    def request_digest(self) -> str:
        return _payload_digest(self.request_payload)

    @property
    def idempotency_identity(self) -> tuple[str, str]:
        return self.operation_id, self.request_digest


@dataclass(frozen=True)
class AddProjectFieldCommand:
    operation_id: str
    execution_generation: int
    project_id: str
    table_id: str
    dataset_generation: str
    field_id: str
    definition: Mapping[str, Any]
    has_default: bool
    default: Any
    expected_table_revision: int

    def __post_init__(self) -> None:
        _validate_field_command(self)

    @property
    def request_payload(self) -> dict[str, Any]:
        return _field_request_payload(self, "addField")

    @property
    def request_digest(self) -> str:
        return _payload_digest(self.request_payload)

    @property
    def idempotency_identity(self) -> tuple[str, str]:
        return self.operation_id, self.request_digest


@dataclass(frozen=True)
class EnsureProjectFieldCommand:
    operation_id: str
    execution_generation: int
    project_id: str
    table_id: str
    dataset_generation: str
    field_id: str
    definition: Mapping[str, Any]
    has_default: bool
    default: Any
    expected_table_revision: int

    def __post_init__(self) -> None:
        _validate_field_command(self)

    @property
    def request_payload(self) -> dict[str, Any]:
        return _field_request_payload(self, "ensureField")

    @property
    def request_digest(self) -> str:
        return _payload_digest(self.request_payload)

    @property
    def idempotency_identity(self) -> tuple[str, str]:
        return self.operation_id, self.request_digest


@dataclass(frozen=True)
class PreviewProjectFieldDeletionRequest:
    execution_generation: int
    project_id: str
    table_id: str
    dataset_generation: str
    field_id: str

    def __post_init__(self) -> None:
        _generation(self.execution_generation)
        _table_identity(self.project_id, self.table_id, self.dataset_generation)
        _uuid(self.field_id, "fieldId")


@dataclass(frozen=True)
class DeleteProjectFieldCommand:
    operation_id: str
    execution_generation: int
    project_id: str
    table_id: str
    dataset_generation: str
    field_id: str
    expected_table_revision: int
    impact_revision: int

    def __post_init__(self) -> None:
        _uuid(self.operation_id, "operationId")
        _generation(self.execution_generation)
        _table_identity(self.project_id, self.table_id, self.dataset_generation)
        _uuid(self.field_id, "fieldId")
        _positive_integer(self.expected_table_revision, "expectedTableRevision")
        _positive_integer(self.impact_revision, "impactRevision")

    @property
    def request_digest(self) -> str:
        return _payload_digest({"kind": "deleteField", "executionGeneration": self.execution_generation,
            "projectId": self.project_id, "tableId": self.table_id, "datasetGeneration": self.dataset_generation,
            "fieldId": self.field_id, "expectedTableRevision": self.expected_table_revision, "impactRevision": self.impact_revision})


@dataclass(frozen=True)
class ModifyProjectFieldCommand:
    operation_id: str
    execution_generation: int
    project_id: str
    table_id: str
    dataset_generation: str
    field_id: str
    definition: Mapping[str, Any]
    expected_table_revision: int
    expected_field_revision: int
    impact_revision: int

    def __post_init__(self) -> None:
        _uuid(self.operation_id, "operationId")
        _generation(self.execution_generation)
        _table_identity(self.project_id, self.table_id, self.dataset_generation)
        _uuid(self.field_id, "fieldId")
        object.__setattr__(self, "definition", _validated_definition(self.definition))
        _positive_integer(self.expected_table_revision, "expectedTableRevision")
        _positive_integer(self.expected_field_revision, "expectedFieldRevision")
        _positive_integer(self.impact_revision, "impactRevision")

    @property
    def request_payload(self) -> dict[str, Any]:
        return {
            "kind": "modifyField",
            "executionGeneration": self.execution_generation,
            "projectId": self.project_id,
            "tableId": self.table_id,
            "datasetGeneration": self.dataset_generation,
            "fieldId": self.field_id,
            "definition": _thaw_json(self.definition),
            "expectedTableRevision": self.expected_table_revision,
            "expectedFieldRevision": self.expected_field_revision,
            "impactRevision": self.impact_revision,
        }

    @property
    def request_digest(self) -> str:
        return _payload_digest(self.request_payload)

    @property
    def idempotency_identity(self) -> tuple[str, str]:
        return self.operation_id, self.request_digest


@dataclass(frozen=True)
class PreviewProjectFieldChangeRequest:
    execution_generation: int
    project_id: str
    table_id: str
    dataset_generation: str
    field_id: str
    definition: Mapping[str, Any]

    def __post_init__(self) -> None:
        _generation(self.execution_generation)
        _table_identity(self.project_id, self.table_id, self.dataset_generation)
        _uuid(self.field_id, "fieldId")
        object.__setattr__(self, "definition", _validated_definition(self.definition))

    @property
    def request_payload(self) -> dict[str, Any]:
        return {
            "kind": "previewFieldChange",
            "executionGeneration": self.execution_generation,
            "projectId": self.project_id,
            "tableId": self.table_id,
            "datasetGeneration": self.dataset_generation,
            "fieldId": self.field_id,
            "definition": _thaw_json(self.definition),
        }


_CAPABILITY_OPERATIONS = frozenset(
    {
        "readRecord",
        "queryRecords",
        "queryTableSchema",
        "updateRecord",
        "deleteRecord",
        "setRecordStatus",
        "createRecord",
        "addField",
        "ensureField",
        "modifyField",
        "deleteField",
    }
)
_RECORD_WRITE_OPERATIONS = frozenset(
    {"updateRecord", "deleteRecord", "setRecordStatus"}
)


@dataclass(frozen=True)
class RecordReadGrant:
    record_ref: RecordRef
    field_ids: frozenset[str] = field(default_factory=frozenset)
    read_purposes: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        _record_ref(self.record_ref, "recordRef")
        object.__setattr__(
            self, "field_ids", frozenset(_field_ids(self.field_ids, "fieldIds"))
        )
        object.__setattr__(
            self,
            "read_purposes",
            frozenset(
                _read_purpose(value, "readPurposes") for value in self.read_purposes
            ),
        )


@dataclass(frozen=True)
class RecordWriteGrant:
    record_ref: RecordRef
    operations: frozenset[str]
    field_ids: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        _record_ref(self.record_ref, "recordRef")
        object.__setattr__(
            self,
            "operations",
            _operations(self.operations, _RECORD_WRITE_OPERATIONS, "operations"),
        )
        object.__setattr__(
            self, "field_ids", frozenset(_field_ids(self.field_ids, "fieldIds"))
        )


@dataclass(frozen=True)
class TableCapabilityGrant:
    table_id: str
    dataset_generation: str
    operations: frozenset[str]
    field_ids: frozenset[str] = field(default_factory=frozenset)
    read_purposes: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        _uuid(self.table_id, "tableId")
        _uuid(self.dataset_generation, "datasetGeneration")
        object.__setattr__(
            self,
            "operations",
            _operations(self.operations, _CAPABILITY_OPERATIONS, "operations"),
        )
        object.__setattr__(
            self, "field_ids", frozenset(_field_ids(self.field_ids, "fieldIds"))
        )
        object.__setattr__(
            self,
            "read_purposes",
            frozenset(
                _read_purpose(value, "readPurposes") for value in self.read_purposes
            ),
        )


@dataclass(frozen=True)
class TaskCapabilityScope:
    project_id: str
    task_id: str
    run_id: str
    execution_generation: int
    status_record_refs: frozenset[RecordRef]
    create_record_targets: frozenset[tuple[str, str]]
    record_read_grants: frozenset[RecordReadGrant] = field(default_factory=frozenset)
    record_write_grants: frozenset[RecordWriteGrant] = field(default_factory=frozenset)
    table_grants: frozenset[TableCapabilityGrant] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        _uuid(self.project_id, "projectId")
        _uuid(self.task_id, "taskId")
        _uuid(self.run_id, "runId")
        _generation(self.execution_generation)
        records = frozenset(self.status_record_refs)
        targets = frozenset(self.create_record_targets)
        read_grants = frozenset(self.record_read_grants)
        write_grants = frozenset(self.record_write_grants)
        table_grants = frozenset(self.table_grants)
        for index, ref in enumerate(records):
            _record_ref(ref, f"statusRecordRefs.{index}")
            if ref.project_id != self.project_id:
                raise _validation(
                    f"statusRecordRefs.{index}.projectId",
                    "must belong to the capability project",
                )
        for index, target in enumerate(targets):
            if not isinstance(target, tuple) or len(target) != 2:
                raise _validation(
                    f"createRecordTargets.{index}",
                    "must contain tableId and datasetGeneration",
                )
            _uuid(target[0], f"createRecordTargets.{index}.tableId")
            _uuid(target[1], f"createRecordTargets.{index}.datasetGeneration")
        for index, read_grant in enumerate(read_grants):
            if not isinstance(read_grant, RecordReadGrant):
                raise _validation(f"recordReadGrants.{index}", "must be a read grant")
            if read_grant.record_ref.project_id != self.project_id:
                raise _validation(
                    f"recordReadGrants.{index}.recordRef.projectId",
                    "must belong to the capability project",
                )
        for index, write_grant in enumerate(write_grants):
            if not isinstance(write_grant, RecordWriteGrant):
                raise _validation(f"recordWriteGrants.{index}", "must be a write grant")
            if write_grant.record_ref.project_id != self.project_id:
                raise _validation(
                    f"recordWriteGrants.{index}.recordRef.projectId",
                    "must belong to the capability project",
                )
        for index, table_grant in enumerate(table_grants):
            if not isinstance(table_grant, TableCapabilityGrant):
                raise _validation(f"tableGrants.{index}", "must be a table grant")
        object.__setattr__(self, "status_record_refs", records)
        object.__setattr__(self, "create_record_targets", targets)
        object.__setattr__(self, "record_read_grants", read_grants)
        object.__setattr__(self, "record_write_grants", write_grants)
        object.__setattr__(self, "table_grants", table_grants)

    def authorize_read_record(
        self,
        request: ReadProjectRecordRequest,
        *,
        current_execution_generation: int,
    ) -> None:
        self._authorize_generation(
            request.execution_generation, current_execution_generation
        )
        for grant in self.record_read_grants:
            if (
                grant.record_ref == request.record_ref
                and set(request.field_ids) <= grant.field_ids
                and request.read_purpose in grant.read_purposes
            ):
                return
        if request.record_ref.project_id == self.project_id and self._has_table_grant(
            request.record_ref.table_id,
            request.record_ref.dataset_generation,
            "readRecord",
            frozenset(request.field_ids),
            request.read_purpose,
        ):
            return
        raise _scope_denied("recordRef")

    def authorize_query_table_schema(
        self,
        request: QueryProjectTableSchemaRequest,
        *,
        current_execution_generation: int,
    ) -> None:
        self._authorize_generation(request.execution_generation, current_execution_generation)
        if request.project_id != self.project_id or not self._has_table_grant(
            request.table_id, request.dataset_generation, "queryTableSchema", frozenset(request.field_ids)
        ):
            raise _scope_denied("tableRef")

    def authorize_query_records(
        self,
        request: QueryProjectRecordsRequest,
        *,
        current_execution_generation: int,
    ) -> None:
        self._authorize_generation(
            request.execution_generation, current_execution_generation
        )
        field_ids = frozenset(request.field_ids) | _query_referenced_field_ids(request)
        if request.project_id != self.project_id or not self._has_table_grant(
            request.table_id,
            request.dataset_generation,
            "queryRecords",
            field_ids,
            request.read_purpose,
        ):
            raise _scope_denied("tableRef")

    def authorize_update_record(
        self,
        command: UpdateProjectRecordCommand,
        *,
        current_execution_generation: int,
    ) -> str:
        return self._authorize_record_write(
            command.record_ref,
            "updateRecord",
            frozenset(command.changes),
            command.execution_generation,
            current_execution_generation,
        )

    def authorize_delete_record(
        self,
        command: DeleteProjectRecordCommand,
        *,
        current_execution_generation: int,
    ) -> str:
        return self._authorize_record_write(
            command.record_ref,
            "deleteRecord",
            frozenset(),
            command.execution_generation,
            current_execution_generation,
        )

    def authorize_set_status(
        self,
        command: SetRecordStatusCommand,
        *,
        current_execution_generation: int,
    ) -> str:
        self._authorize_generation(
            command.execution_generation, current_execution_generation
        )
        if command.record_ref.project_id == self.project_id:
            if command.record_ref in self.status_record_refs:
                return "existing"
            for grant in self.record_write_grants:
                if (
                    grant.record_ref == command.record_ref
                    and "setRecordStatus" in grant.operations
                ):
                    return "existing"
            if self._has_table_grant(
                command.record_ref.table_id,
                command.record_ref.dataset_generation,
                "setRecordStatus",
                frozenset(),
            ):
                return "dynamic"
        raise _scope_denied("recordRef")

    def authorize_create_record(
        self,
        command: CreateProjectRecordCommand,
        *,
        current_execution_generation: int,
    ) -> None:
        self._authorize_generation(
            command.execution_generation, current_execution_generation
        )
        if command.project_id == self.project_id:
            if (
                command.table_id,
                command.dataset_generation,
            ) in self.create_record_targets:
                return
            if self._has_table_grant(
                command.table_id,
                command.dataset_generation,
                "createRecord",
                frozenset(command.values),
            ):
                return
        raise _scope_denied("tableRef")

    def authorize_add_field(
        self,
        command: AddProjectFieldCommand,
        *,
        current_execution_generation: int,
    ) -> None:
        self._authorize_field_command(command, "addField", current_execution_generation)

    def authorize_ensure_field(
        self,
        command: EnsureProjectFieldCommand,
        *,
        current_execution_generation: int,
    ) -> None:
        self._authorize_field_command(
            command, "ensureField", current_execution_generation
        )

    def authorize_delete_field(self, request: DeleteProjectFieldCommand | PreviewProjectFieldDeletionRequest,
                               *, current_execution_generation: int) -> None:
        self._authorize_generation(request.execution_generation, current_execution_generation)
        if request.project_id != self.project_id or not self._has_table_grant(
            request.table_id, request.dataset_generation, "deleteField", frozenset({request.field_id})
        ):
            raise _scope_denied("fieldRef")

    def authorize_modify_field(
        self,
        command: ModifyProjectFieldCommand,
        *,
        current_execution_generation: int,
    ) -> None:
        self._authorize_field_command(
            command, "modifyField", current_execution_generation
        )

    def authorize_preview_field_change(
        self,
        request: PreviewProjectFieldChangeRequest,
        *,
        current_execution_generation: int,
    ) -> None:
        self._authorize_field_command(
            request, "modifyField", current_execution_generation
        )

    def _authorize_field_command(
        self,
        command: AddProjectFieldCommand
        | EnsureProjectFieldCommand
        | ModifyProjectFieldCommand
        | PreviewProjectFieldChangeRequest,
        operation: str,
        current_execution_generation: int,
    ) -> None:
        self._authorize_generation(
            command.execution_generation, current_execution_generation
        )
        if command.project_id != self.project_id or not self._has_table_grant(
            command.table_id,
            command.dataset_generation,
            operation,
            frozenset(),
        ):
            raise _scope_denied("fieldRef")

    def _authorize_record_write(
        self,
        record_ref: RecordRef,
        operation: str,
        field_ids: frozenset[str],
        command_generation: int,
        current_generation: int,
    ) -> str:
        self._authorize_generation(command_generation, current_generation)
        if record_ref.project_id == self.project_id:
            for grant in self.record_write_grants:
                if (
                    grant.record_ref == record_ref
                    and operation in grant.operations
                    and field_ids <= grant.field_ids
                ):
                    return "existing"
            if self._has_table_grant(
                record_ref.table_id,
                record_ref.dataset_generation,
                operation,
                field_ids,
            ):
                return "dynamic"
        raise _scope_denied("recordRef")

    def _has_table_grant(
        self,
        table_id: str,
        dataset_generation: str,
        operation: str,
        field_ids: frozenset[str],
        read_purpose: str | None = None,
    ) -> bool:
        return any(
            grant.table_id == table_id
            and grant.dataset_generation == dataset_generation
            and operation in grant.operations
            and field_ids <= grant.field_ids
            and (read_purpose is None or read_purpose in grant.read_purposes)
            for grant in self.table_grants
        )

    def _authorize_generation(
        self, command_generation: int, current_generation: int
    ) -> None:
        _generation(current_generation, "currentExecutionGeneration")
        if (
            self.execution_generation != current_generation
            or command_generation != current_generation
        ):
            raise ProjectError(
                "LEASE_REVOKED",
                "Task capability belongs to an obsolete execution generation",
                409,
                {
                    "domainCode": "lease_revoked",
                    "scopeExecutionGeneration": self.execution_generation,
                    "commandExecutionGeneration": command_generation,
                    "currentExecutionGeneration": current_generation,
                    "retryable": False,
                },
            )


def _payload_digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _query_referenced_field_ids(
    request: QueryProjectRecordsRequest,
) -> frozenset[str]:
    result: set[str] = set()

    def visit(node: object) -> None:
        if not isinstance(node, Mapping):
            return
        kind = node.get("type")
        field_id = node.get("fieldId")
        if kind == "compare" and isinstance(field_id, str):
            result.add(field_id)
        if kind in {"all", "any"}:
            items = node.get("items")
            if isinstance(items, tuple):
                for item in items:
                    visit(item)
        elif kind == "not":
            visit(node.get("item"))

    visit(request.filter)
    for item in request.order_by:
        field_id = item.get("fieldId")
        if isinstance(field_id, str):
            result.add(field_id)
    return frozenset(result)


def _table_identity(project_id: object, table_id: object, generation: object) -> None:
    _uuid(project_id, "projectId")
    _uuid(table_id, "tableId")
    _uuid(generation, "datasetGeneration")


def _field_ids(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple | set | frozenset):
        raise _validation(field_name, "must be an array of field IDs")
    result = tuple(
        _uuid(item, f"{field_name}.{index}") for index, item in enumerate(value)
    )
    if len(result) != len(set(result)):
        raise _validation(field_name, "must not contain duplicate field IDs")
    return result


def _read_purpose(value: object, field_name: str) -> str:
    if (
        type(value) is not str
        or not value
        or value.strip() != value
        or len(value) > 120
        or any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    ):
        raise _validation(field_name, "must be 1 to 120 valid Unicode code points")
    return value


def _operations(
    value: object, allowed: frozenset[str], field_name: str
) -> frozenset[str]:
    if not isinstance(value, set | frozenset):
        raise _validation(field_name, "must be a set of capability operations")
    result = frozenset(value)
    if (
        not result
        or any(type(item) is not str for item in result)
        or not result <= allowed
    ):
        raise _validation(field_name, "contains an unsupported capability operation")
    return result


def _freeze_field_values(
    value: object, field_name: str, *, allow_empty: bool
) -> Mapping[str, Any]:
    frozen = _freeze_json_object(value, field_name)
    if not allow_empty and not frozen:
        raise _validation(field_name, "must contain at least one field change")
    for index, field_id in enumerate(frozen):
        _uuid(field_id, f"{field_name}.{index}.fieldId")
    return frozen


def _validated_definition(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _validation("definition", "must be a field definition")
    try:
        definition = validate_field(dict(value))
    except ProjectError as error:
        raise _validation("definition", error.message) from error
    return _freeze_json_object(definition, "definition")


def _validate_field_command(
    command: AddProjectFieldCommand | EnsureProjectFieldCommand,
) -> None:
    _uuid(command.operation_id, "operationId")
    _generation(command.execution_generation)
    _table_identity(command.project_id, command.table_id, command.dataset_generation)
    _uuid(command.field_id, "fieldId")
    definition = _validated_definition(command.definition)
    object.__setattr__(command, "definition", definition)
    if type(command.has_default) is not bool:
        raise _validation("hasDefault", "must be boolean")
    if command.has_default:
        try:
            default = validate_value(_thaw_json(definition), command.default)
        except ProjectError as error:
            raise _validation("default", error.message) from error
        object.__setattr__(command, "default", _freeze_json(default))
    elif command.default is not None:
        raise _validation("default", "must be null when hasDefault is false")
    _positive_integer(command.expected_table_revision, "expectedTableRevision")


def _field_request_payload(
    command: AddProjectFieldCommand | EnsureProjectFieldCommand, kind: str
) -> dict[str, Any]:
    return {
        "kind": kind,
        "executionGeneration": command.execution_generation,
        "projectId": command.project_id,
        "tableId": command.table_id,
        "datasetGeneration": command.dataset_generation,
        "fieldId": command.field_id,
        "definition": _thaw_json(command.definition),
        "hasDefault": command.has_default,
        "default": _thaw_json(command.default),
        "expectedTableRevision": command.expected_table_revision,
    }


def _record_ref(value: object, field: str) -> RecordRef:
    if not isinstance(value, RecordRef):
        raise _validation(field, "must be a typed record reference")
    _uuid(value.project_id, f"{field}.projectId")
    _uuid(value.table_id, f"{field}.tableId")
    _uuid(value.dataset_generation, f"{field}.datasetGeneration")
    if not isinstance(value.record_key, RecordKey):
        raise _validation(f"{field}.recordKey", "must be a typed record key")
    try:
        encode_record_key(value.record_key)
    except ProjectError as error:
        raise _validation(f"{field}.recordKey", error.message) from error
    return value


def _record_ref_payload(value: RecordRef) -> dict[str, Any]:
    return {
        "projectId": value.project_id,
        "tableId": value.table_id,
        "datasetGeneration": value.dataset_generation,
        "recordKey": {"type": value.record_key.type, "value": value.record_key.value},
    }


def _uuid(value: object, field: str) -> str:
    try:
        if type(value) is not str or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError) as error:
        raise _validation(field, "must be a canonical lowercase UUID") from error
    return value


def _generation(value: object, field: str = "executionGeneration") -> int:
    return _positive_integer(value, field)


def _positive_integer(value: object, field: str) -> int:
    if type(value) is not int or not 1 <= value <= MAX_SAFE_INTEGER:
        raise _validation(field, "must be a positive safe integer")
    return value


def _freeze_json_object(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        raise _validation(field, "must be an object with string keys")
    try:
        canonical_bytes(value)
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    except (TypeError, ValueError, OverflowError) as error:
        raise _validation(field, "must contain finite JSON values") from error


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise TypeError("JSON object keys must be strings")
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, list | tuple):
        return tuple(_freeze_json(item) for item in value)
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise TypeError("value is not finite JSON")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _validation(field: str, reason: str) -> ProjectError:
    return ProjectError(
        "VALIDATION_ERROR",
        "Project data capability request is invalid",
        422,
        {
            "fields": {field: reason},
            "domainCode": "validation_error",
            "retryable": False,
        },
    )


def _scope_denied(field: str) -> ProjectError:
    return ProjectError(
        "CAPABILITY_SCOPE_DENIED",
        "Project data capability does not allow this target",
        403,
        {"field": field, "domainCode": "capability_scope_denied", "retryable": False},
    )
