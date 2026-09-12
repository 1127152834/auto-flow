from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from autoflow.application.project_data.tables import (
    _canonical_uuid,
    _operation,
    _validation,
)
from autoflow.domain.project_data.catalog import ProjectDataCatalog
from autoflow.domain.project_data.identity import MAX_SAFE_INTEGER
from autoflow.domain.project_data.rules import validate_field, validate_value
from autoflow.domain.projects.models import ProjectError, ProjectOperation


class DataCatalogService:
    def __init__(self, catalog: ProjectDataCatalog):
        self.catalog = catalog

    def fields(self, project_id: str, table_id: str) -> dict[str, Any]:
        _ids(project_id, table_id)
        return self.catalog.fields(project_id, table_id)

    def create_field(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], ProjectOperation, bool]:
        _ids(project_id, table_id)
        operation_key = _canonical_uuid(key, "Idempotency-Key")
        if not isinstance(payload, dict) or set(payload) - {
            "definition",
            "existingRecordDefault",
            "expectedTableRevision",
            "sourceColumnPolicy",
        }:
            raise _validation("form", "Invalid field request")
        if payload.get("sourceColumnPolicy") != "localOnly":
            if payload.get("sourceColumnPolicy") == "mapped":
                raise ProjectError(
                    "SOURCE_MAPPING_UNAVAILABLE",
                    "Mapped source columns are not available",
                    412,
                )
            raise _validation("sourceColumnPolicy", "Must be localOnly or mapped")
        raw_definition = payload.get("definition")
        if not isinstance(raw_definition, dict):
            raise _validation("definition", "Must be an object")
        definition = validate_field(raw_definition)
        expected = _revision(
            payload.get("expectedTableRevision"), "expectedTableRevision"
        )
        has_default = "existingRecordDefault" in payload
        default = payload.get("existingRecordDefault")
        if has_default:
            default = validate_value(definition, default)
        field_id = str(uuid4())
        now = datetime.now(UTC)
        request = {
            "definition": definition,
            "expectedTableRevision": expected,
            "sourceColumnPolicy": "localOnly",
        }
        if has_default:
            request["existingRecordDefault"] = default
        op = _catalog_operation(
            operation_key,
            "mutateField",
            request,
            project_id,
            table_id,
            "field",
            field_id,
            now,
        )
        return self.catalog.create_field(
            project_id,
            table_id,
            field_id,
            definition,
            has_default,
            default,
            expected,
            op,
        )

    def statuses(self, project_id: str, table_id: str) -> dict[str, Any]:
        _ids(project_id, table_id)
        return self.catalog.statuses(project_id, table_id)

    def create_status(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], ProjectOperation, bool]:
        _ids(project_id, table_id)
        operation_key = _canonical_uuid(key, "Idempotency-Key")
        if not isinstance(payload, dict) or set(payload) != {
            "name",
            "color",
            "order",
            "expectedTableRevision",
        }:
            raise _validation("form", "Invalid status request")
        expected = _revision(payload["expectedTableRevision"], "expectedTableRevision")
        value = {
            "name": _name(payload["name"]),
            "color": _color(payload["color"]),
            "order": _order(payload["order"]),
        }
        status_id = str(uuid4())
        now = datetime.now(UTC)
        op = _catalog_operation(
            operation_key,
            "mutateStatus",
            {**value, "expectedTableRevision": expected},
            project_id,
            table_id,
            "status",
            status_id,
            now,
        )
        return self.catalog.create_status(
            project_id, table_id, status_id, value, expected, op
        )

    def update_status(
        self,
        project_id: str,
        table_id: str,
        status_id: str,
        key: str,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], ProjectOperation, bool]:
        _ids(project_id, table_id)
        _canonical_uuid(status_id, "statusId")
        operation_key = _canonical_uuid(key, "Idempotency-Key")
        allowed = {
            "name",
            "color",
            "order",
            "expectedTableRevision",
            "expectedStatusRevision",
        }
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise _validation("form", "Invalid status request")
        et = _revision(payload.get("expectedTableRevision"), "expectedTableRevision")
        es = _revision(payload.get("expectedStatusRevision"), "expectedStatusRevision")
        patch: dict[str, Any] = {}
        if "name" in payload:
            patch["name"] = _name(payload["name"])
        if "color" in payload:
            patch["color"] = _color(payload["color"])
        if "order" in payload:
            patch["order"] = _order(payload["order"])
        if not patch:
            raise _validation("form", "At least one change is required")
        now = datetime.now(UTC)
        op = _catalog_operation(
            operation_key,
            "mutateStatus",
            {
                "statusId": status_id,
                **patch,
                "expectedTableRevision": et,
                "expectedStatusRevision": es,
            },
            project_id,
            table_id,
            "status",
            status_id,
            now,
        )
        return self.catalog.update_status(
            project_id, table_id, status_id, patch, et, es, op
        )


def _ids(project_id: str, table_id: str) -> None:
    _canonical_uuid(project_id, "projectId")
    _canonical_uuid(table_id, "tableId")


def _revision(value: object, field: str) -> int:
    if type(value) is not int or not 1 <= value <= MAX_SAFE_INTEGER:
        raise _validation(field, "Must be a positive JSON-safe integer")
    return value


def _name(value: object) -> str:
    if not isinstance(value, str):
        raise _validation("name", "Must be a string")
    value = value.strip()
    if not 1 <= len(value) <= 120 or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise _validation("name", "Must contain 1 to 120 valid Unicode code points")
    return value


def _color(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", value) is None:
        raise _validation("color", "Must be #RRGGBB")
    return value.lower()


def _order(value: object) -> int:
    if type(value) is not int or not 0 <= value <= MAX_SAFE_INTEGER:
        raise _validation("order", "Must be a nonnegative JSON-safe integer")
    return value


def _catalog_operation(
    key: str,
    kind: str,
    request: dict[str, Any],
    project_id: str,
    table_id: str,
    resource_type: str,
    resource_id: str,
    now: datetime,
) -> ProjectOperation:
    base = _operation(
        key,
        kind,
        {
            "scope": "table",
            "target": {"projectId": project_id, "tableId": table_id},
            "request": request,
        },
        project_id,
        table_id,
        now,
    )
    if resource_type == "field":
        resource = {
            "type": "field",
            "fieldRef": {
                "projectId": project_id,
                "tableId": table_id,
                "datasetGeneration": None,
                "fieldId": resource_id,
            },
        }
    else:
        resource = {
            "type": resource_type,
            "projectId": project_id,
            "tableId": table_id,
            f"{resource_type}Id": resource_id,
        }
    return replace(base, resource=resource)
