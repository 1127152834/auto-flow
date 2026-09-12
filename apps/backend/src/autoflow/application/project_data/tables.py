from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from autoflow.domain.project_data.models import DataTable
from autoflow.domain.project_data.ports import ProjectDataTables
from autoflow.domain.projects.models import ProjectError, ProjectOperation


class DataTableService:
    def __init__(self, tables: ProjectDataTables):
        self.tables = tables

    def create(
        self, project_id: str, key: str, payload: dict[str, Any]
    ) -> tuple[dict, ProjectOperation, bool]:
        _canonical_uuid(project_id, "projectId")
        operation_key = _canonical_uuid(key, "Idempotency-Key")
        data = _validate_create(payload)
        now = datetime.now(UTC)
        table = DataTable(
            project_id=project_id,
            table_id=str(uuid4()),
            name=data["name"],
            description=data["description"],
            source_kind=data["sourceKind"],
            dataset_generation=str(uuid4()),
            table_revision=1,
            identity={"mode": "system"},
            slot_definitions=[],
            created_at=now,
            updated_at=now,
        )
        operation = _operation(
            operation_key,
            "createTable",
            {"scope": "project", "target": project_id, "request": data},
            project_id,
            table.table_id,
            now,
        )
        return self.tables.create(table, operation)

    def update(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> tuple[dict, ProjectOperation, bool]:
        _canonical_uuid(project_id, "projectId")
        _canonical_uuid(table_id, "tableId")
        operation_key = _canonical_uuid(key, "Idempotency-Key")
        patch, expected = _validate_update(payload)
        now = datetime.now(UTC)
        operation = _operation(
            operation_key,
            "updateTable",
            {
                "scope": "table",
                "target": {"projectId": project_id, "tableId": table_id},
                "request": {**patch, "expectedTableRevision": expected},
            },
            project_id,
            table_id,
            now,
        )
        return self.tables.update(project_id, table_id, patch, expected, operation)

    def get(self, project_id: str, table_id: str) -> dict:
        _canonical_uuid(project_id, "projectId")
        _canonical_uuid(table_id, "tableId")
        value = self.tables.get(project_id, table_id)
        if value is None:
            raise ProjectError("TABLE_NOT_FOUND", "Table was not found", 404)
        return value

    def list(
        self,
        project_id: str,
        q: str | None = None,
        source_kind: str | None = None,
        page: int = 1,
        page_size: int = 50,
        sort: str = "-updatedAt",
    ) -> tuple[list[dict], int]:
        _canonical_uuid(project_id, "projectId")
        if q is not None and not isinstance(q, str):
            raise _validation("q", "Must be a string")
        if isinstance(q, str) and any(
            unicodedata.category(character) in {"Cc", "Cs"} for character in q
        ):
            raise _validation("q", "Must not contain control or surrogate characters")
        if source_kind is not None and source_kind not in {
            "local",
            "excel",
            "sheets",
            "unconfigured",
        }:
            raise _validation("sourceKind", "Invalid source kind")
        if type(page) is not int or page < 1:
            raise _validation("page", "Must be a positive integer")
        if type(page_size) is not int or not 1 <= page_size <= 200:
            raise _validation("pageSize", "Must be between 1 and 200")
        if sort not in {"name", "-name", "updatedAt", "-updatedAt"}:
            raise _validation("sort", "Invalid sort")
        return self.tables.list(project_id, q, source_kind, page, page_size, sort)


def _validate_create(payload: dict[str, Any]) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise _validation("form", "Must be an object")
    extra = set(payload) - {"name", "description", "sourceKind"}
    if extra:
        raise _validation(next(iter(extra)), "Unexpected field")
    if "name" not in payload:
        raise _validation("name", "Required")
    name = _name(payload["name"])
    description = _description(payload.get("description", ""))
    source_kind = payload.get("sourceKind", "local")
    if source_kind != "local":
        raise _validation("sourceKind", "Must be local")
    return {"name": name, "description": description, "sourceKind": source_kind}


def _validate_update(payload: dict[str, Any]) -> tuple[dict[str, str], int]:
    if not isinstance(payload, dict):
        raise _validation("form", "Must be an object")
    extra = set(payload) - {"name", "description", "expectedTableRevision"}
    if extra:
        raise _validation(next(iter(extra)), "Unexpected field")
    expected = payload.get("expectedTableRevision")
    if type(expected) is not int or expected < 1:
        raise _validation("expectedTableRevision", "Must be a positive integer")
    patch: dict[str, str] = {}
    if "name" in payload:
        patch["name"] = _name(payload["name"])
    if "description" in payload:
        patch["description"] = _description(payload["description"])
    if not patch:
        raise _validation("form", "At least one change is required")
    return patch, expected


def _name(value: object) -> str:
    if not isinstance(value, str):
        raise _validation("name", "Must be a string")
    value = value.strip()
    if not 1 <= len(value) <= 120:
        raise _validation("name", "Must contain 1 to 120 Unicode code points")
    if _has_surrogate(value):
        raise _validation("name", "Must contain valid Unicode scalar values")
    return value


def _description(value: object) -> str:
    if not isinstance(value, str):
        raise _validation("description", "Must be a string")
    value = value.strip()
    if len(value) > 1000:
        raise _validation("description", "Must contain at most 1000 Unicode code points")
    if _has_surrogate(value):
        raise _validation("description", "Must contain valid Unicode scalar values")
    return value


def _has_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _canonical_uuid(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise _validation(field, "Must be a canonical UUID")
    try:
        canonical = str(UUID(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise _validation(field, "Must be a canonical UUID") from error
    if value != canonical:
        raise _validation(field, "Must be a canonical UUID")
    return canonical


def _validation(field: str, message: str) -> ProjectError:
    return ProjectError(
        "VALIDATION_ERROR",
        "Request validation failed",
        422,
        {
            "fields": {field: message},
            "domainCode": "validation_error",
            "retryable": False,
        },
    )


def _operation(
    key: str,
    kind: str,
    canonical: dict[str, Any],
    project_id: str,
    table_id: str,
    now: datetime,
) -> ProjectOperation:
    digest = hashlib.sha256(
        json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    return ProjectOperation(
        str(uuid4()),
        project_id,
        key,
        kind,
        digest,
        "running",
        1,
        {"type": "table", "projectId": project_id, "tableId": table_id},
        None,
        None,
        now,
        now,
        None,
    )
