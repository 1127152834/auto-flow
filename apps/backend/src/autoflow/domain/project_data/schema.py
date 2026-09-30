"""Pure validation of complete table-schema drafts and bounded backfills."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from autoflow.domain.project_data.identity import MAX_SAFE_INTEGER
from autoflow.domain.project_data.rules import validate_field, validate_value
from autoflow.domain.projects.models import ProjectError


class SchemaBackfillLimit(ValueError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def backfill_budget(values: list[dict]) -> tuple[int, int]:
    """Count actual changed rows, each containing its entire post-write values JSON."""
    count = len(values)
    size = sum(len(canonical_bytes(value)) for value in values)
    if count > 1000 or size > 4 * 1024 * 1024:
        raise SchemaBackfillLimit("本次字段变更需要更新的数据量超过一次保存上限")
    return count, size


def _invalid(field: str, reason: str) -> ProjectError:
    return ProjectError(
        "INVALID_PROJECT_DATA",
        "Invalid schema candidate",
        422,
        {"field": field, "reason": reason},
    )


def _uuid(value: object, field: str) -> str:
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError) as error:
        raise _invalid(field, "must be a canonical lowercase UUID") from error
    return value


def _revision(value: object, field: str) -> int:
    if type(value) is not int or not 1 <= value <= MAX_SAFE_INTEGER:
        raise _invalid(field, "must be a positive safe integer")
    return value


def validate_candidate(
    candidate: object,
    current_fields: list[dict[str, Any]] | None = None,
    identity_field_id: str | None = None,
) -> dict[str, Any]:
    """Normalize wire dictionaries; optionally check a repository's current snapshot.

    A missing snapshot performs structural validation only. An empty snapshot means
    the table has no existing fields. Generation/table CAS remains the caller's job.
    """
    if not isinstance(candidate, dict) or set(candidate) - {"removedFieldIds"} != {
        "datasetGeneration",
        "expectedTableRevision",
        "fields",
    }:
        raise _invalid(
            "candidate", "must contain datasetGeneration, expectedTableRevision, fields"
        )
    generation = _uuid(candidate["datasetGeneration"], "datasetGeneration")
    revision = _revision(candidate["expectedTableRevision"], "expectedTableRevision")
    if not isinstance(candidate["fields"], list):
        raise _invalid("fields", "must be an array")
    removed = candidate.get("removedFieldIds", [])
    if not isinstance(removed, list) or len(removed) > 1:
        raise _invalid("removedFieldIds", "must explicitly remove at most one field")
    removed = [_uuid(value, "removedFieldIds") for value in removed]
    snapshot = {field["ref"]["fieldId"]: field for field in current_fields or []}
    existing_ids: set[str] = set()
    client_ids: set[str] = set()
    keys: set[str] = set()
    fields = []
    for index, item in enumerate(candidate["fields"]):
        path = f"fields.{index}"
        if not isinstance(item, dict):
            raise _invalid(path, "must be an object")
        kind = item.get("kind")
        required = (
            {"kind", "fieldId", "expectedFieldRevision", "definition"}
            if kind == "existing"
            else {"kind", "clientId", "definition", "sourceColumnPolicy"}
        )
        optional = {"existingRecordDefault"} if kind == "new" else set()
        if (
            kind not in ("existing", "new")
            or not required <= set(item)
            or set(item) - required - optional
        ):
            raise _invalid(path, "invalid field candidate properties")
        definition = validate_field(item["definition"])
        if definition["key"] in keys:
            raise _invalid(f"{path}.definition.key", "field keys must be unique")
        keys.add(definition["key"])
        normalized: dict[str, Any] = {"kind": kind, "definition": definition}
        if kind == "existing":
            field_id = _uuid(item["fieldId"], f"{path}.fieldId")
            expected = _revision(
                item["expectedFieldRevision"], f"{path}.expectedFieldRevision"
            )
            if field_id in existing_ids:
                raise _invalid(path, "existing field must appear exactly once")
            existing_ids.add(field_id)
            if current_fields is not None:
                if field_id not in snapshot:
                    raise _invalid(path, "unknown current field")
                current = snapshot[field_id]
                if current["fieldRevision"] != expected:
                    raise ProjectError(
                        "REVISION_CONFLICT",
                        "Field was modified",
                        409,
                        {
                            "expectedRevision": expected,
                            "currentRevision": current["fieldRevision"],
                            "domainCode": "revision_conflict",
                            "retryable": False,
                        },
                    )
                before = {
                    key: current[key]
                    for key in ("key", "name", "type", "required", "validation")
                }
                if definition["key"] != before["key"]:
                    raise _invalid(path, "existing field key cannot be changed")
                if (
                    current["formula"] or not current["writable"]
                ) and definition != before:
                    raise _invalid(path, "read-only field definition cannot be changed")
                if (
                    field_id == identity_field_id
                    and definition["type"] != before["type"]
                ):
                    raise _invalid(path, "identity field type cannot be changed")
            normalized.update(fieldId=field_id, expectedFieldRevision=expected)
        else:
            client_id = _uuid(item["clientId"], f"{path}.clientId")
            if client_id in client_ids:
                raise _invalid(path, "new clientId must be unique")
            client_ids.add(client_id)
            if item["sourceColumnPolicy"] != "localOnly":
                raise _invalid(f"{path}.sourceColumnPolicy", "must be localOnly")
            normalized.update(clientId=client_id, sourceColumnPolicy="localOnly")
            if "existingRecordDefault" in item:
                normalized["existingRecordDefault"] = validate_value(
                    definition, item["existingRecordDefault"]
                )
        fields.append(normalized)
    if existing_ids & set(removed):
        raise _invalid("fields", "removed fields cannot also be retained")
    if current_fields is not None and existing_ids | set(removed) != set(snapshot):
        raise _invalid("fields", "must contain every current field exactly once")
    result = {
        "datasetGeneration": generation,
        "expectedTableRevision": revision,
        "fields": fields,
    }
    if removed:
        result["removedFieldIds"] = removed
    try:
        canonical_bytes(result)
    except (ValueError, TypeError, UnicodeError) as error:
        raise _invalid(
            "candidate", "must contain finite, valid UTF-8 JSON values"
        ) from error
    return result
