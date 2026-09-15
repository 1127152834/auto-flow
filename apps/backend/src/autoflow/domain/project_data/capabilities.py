from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
from uuid import UUID

from autoflow.domain.project_data.identity import (
    MAX_SAFE_INTEGER,
    RecordKey,
    encode_record_key,
)
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

    def __post_init__(self) -> None:
        _uuid(self.operation_id, "operationId")
        _generation(self.execution_generation)
        _record_ref(self.record_ref, "recordRef")
        if self.status_id is not None:
            _uuid(self.status_id, "statusId")
        _positive_integer(self.expected_status_revision, "expectedStatusRevision")

    @property
    def request_payload(self) -> dict[str, Any]:
        return {
            "kind": "setRecordStatus",
            "executionGeneration": self.execution_generation,
            "recordRef": _record_ref_payload(self.record_ref),
            "statusId": self.status_id,
            "expectedStatusRevision": self.expected_status_revision,
        }

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
class TaskCapabilityScope:
    project_id: str
    task_id: str
    run_id: str
    execution_generation: int
    status_record_refs: frozenset[RecordRef]
    create_record_targets: frozenset[tuple[str, str]]

    def __post_init__(self) -> None:
        _uuid(self.project_id, "projectId")
        _uuid(self.task_id, "taskId")
        _uuid(self.run_id, "runId")
        _generation(self.execution_generation)
        records = frozenset(self.status_record_refs)
        targets = frozenset(self.create_record_targets)
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
        object.__setattr__(self, "status_record_refs", records)
        object.__setattr__(self, "create_record_targets", targets)

    def authorize_set_status(
        self,
        command: SetRecordStatusCommand,
        *,
        current_execution_generation: int,
    ) -> None:
        self._authorize_generation(
            command.execution_generation, current_execution_generation
        )
        if (
            command.record_ref.project_id != self.project_id
            or command.record_ref not in self.status_record_refs
        ):
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
        if command.project_id != self.project_id or (
            command.table_id,
            command.dataset_generation,
        ) not in self.create_record_targets:
            raise _scope_denied("tableRef")

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
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    except (TypeError, ValueError, OverflowError) as error:
        raise _validation(field, "must contain finite JSON values") from error


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise TypeError("JSON object keys must be strings")
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
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
