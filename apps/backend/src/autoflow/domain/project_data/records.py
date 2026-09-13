from __future__ import annotations

from typing import Any, Protocol

from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_data.rules import validate_value
from autoflow.domain.projects.models import ProjectOperation


class ProjectDataRecords(Protocol):
    def create(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        values: dict[str, object],
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]: ...
    def create_many(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        expected: int,
        rows: list[tuple[str, dict[str, object]]],
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]: ...
    def get(
        self, project_id: str, table_id: str, generation: str, key: RecordKey
    ) -> dict[str, Any] | None: ...
    def update(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        key: RecordKey,
        values: dict[str, object],
        expected: int,
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]: ...
    def set_status(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        key: RecordKey,
        status_id: str | None,
        expected: int,
        has_from: bool,
        from_status: str | None,
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]: ...


def validate_record_scalar(value: object) -> object:
    """Validate a wire scalar without coercing or trimming it."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return validate_value(_wire_definition("string"), value)
    if isinstance(value, (int, float)):
        return validate_value(_wire_definition("number"), value)
    if isinstance(value, dict):
        return validate_value(_wire_definition("date"), value)
    return validate_value(_wire_definition("boolean"), value)


def _wire_definition(field_type: str) -> dict[str, Any]:
    return {
        "key": "value",
        "name": "Value",
        "type": field_type,
        "required": False,
        "validation": {},
    }
