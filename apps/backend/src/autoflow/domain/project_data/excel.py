"""Validation and stable request identity for controlled Excel operations."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from autoflow.domain.projects.models import ProjectError


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _window(expected_id: int, expected_hash: str, window_id: int, token: str) -> None:
    if (
        type(window_id) is not int
        or not isinstance(token, str)
        or window_id != expected_id
        or not hmac.compare_digest(_token_hash(token), expected_hash)
    ):
        raise ProjectError(
            "FILE_WINDOW_MISMATCH",
            "File selection belongs to another window",
            403,
        )


def _not_expired(value: datetime) -> None:
    expiry = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    if expiry <= datetime.now(UTC):
        raise ProjectError("EXCEL_INSPECTION_EXPIRED", "Excel inspection expired", 410)


def _uuid(value: Any, field: str) -> str:
    try:
        canonical = str(UUID(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise _invalid(field, "Must be a canonical UUID") from error
    if value != canonical:
        raise _invalid(field, "Must be a canonical UUID")
    return canonical


def _invalid(field: str, message: str) -> ProjectError:
    return ProjectError(
        "VALIDATION_ERROR",
        "Request validation failed",
        422,
        {"fields": {field: message}},
    )


def normalize_import(payload: dict, *, replace: bool) -> dict:
    from .rules import validate_field

    common = {"inspectionId", "fingerprint", "sheetId", "mapping", "identity"}
    extra = (
        {"expectedDatasetGeneration", "expectedTableRevision", "impactRevision"}
        if replace
        else {"name", "description"}
    )
    if set(payload) - common - extra or common - set(payload):
        raise _invalid("import", "Unexpected or missing fields")
    data = dict(payload)
    data["inspectionId"] = _uuid(data["inspectionId"], "inspectionId")
    if not isinstance(data["fingerprint"], str) or len(data["fingerprint"]) != 64:
        raise _invalid("fingerprint", "Invalid fingerprint")
    if not isinstance(data["sheetId"], str) or not data["sheetId"]:
        raise _invalid("sheetId", "A worksheet is required")
    if replace:
        data["expectedDatasetGeneration"] = _uuid(
            data.get("expectedDatasetGeneration"), "expectedDatasetGeneration"
        )
        for key in ("expectedTableRevision", "impactRevision"):
            if type(data.get(key)) is not int or data[key] < 1:
                raise _invalid(key, "Must be a positive integer")
    else:
        for key, maximum, minimum in [("name", 120, 1), ("description", 1000, 0)]:
            value = data.get(key, "")
            if not isinstance(value, str):
                raise _invalid(key, "Must be text")
            value = value.strip()
            if not minimum <= len(value) <= maximum or any(
                0xD800 <= ord(c) <= 0xDFFF for c in value
            ):
                raise _invalid(
                    key, f"Must contain {minimum}–{maximum} Unicode code points"
                )
            data[key] = value
    mapping = data["mapping"]
    if not isinstance(mapping, list) or not 1 <= len(mapping) <= 500:
        raise _invalid("mapping", "Map 1–500 columns")
    normalized, columns, existing = [], set(), set()
    for item in mapping:
        if not isinstance(item, dict) or set(item) != {"columnIndex", "target"}:
            raise _invalid("mapping", "Invalid column mapping")
        column, target = item["columnIndex"], item["target"]
        if type(column) is not int or not 0 <= column < 500 or column in columns:
            raise _invalid("mapping", "Columns must be unique and within the worksheet")
        columns.add(column)
        if (
            isinstance(target, dict)
            and set(target) == {"kind", "definition"}
            and target["kind"] == "new"
        ):
            target = {"kind": "new", "definition": validate_field(target["definition"])}
        elif (
            replace
            and isinstance(target, dict)
            and set(target) == {"kind", "fieldId"}
            and target["kind"] == "existing"
        ):
            field_id = _uuid(target["fieldId"], "fieldId")
            if field_id in existing:
                raise _invalid("mapping", "A field cannot receive more than one column")
            existing.add(field_id)
            target = {"kind": "existing", "fieldId": field_id}
        else:
            raise _invalid(
                "mapping", "Choose an explicit existing field or a new field definition"
            )
        normalized.append({"columnIndex": column, "target": target})
    data["mapping"] = sorted(normalized, key=lambda item: item["columnIndex"])
    identity = data["identity"]
    if (
        identity == {"mode": "system"}
        or isinstance(identity, dict)
        and set(identity) == {"mode", "columnIndex"}
        and identity["mode"] == "column"
        and type(identity["columnIndex"]) is int
        and identity["columnIndex"] in columns
    ):
        pass
    else:
        raise _invalid("identity", "Choose system identity or a mapped column")
    return data
