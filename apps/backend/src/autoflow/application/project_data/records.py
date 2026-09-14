from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from autoflow.application.project_data.tables import (
    _canonical_uuid,
    _operation,
    _validation,
)
from autoflow.domain.project_data.identity import (
    MAX_SAFE_INTEGER,
    RecordKey,
    decode_record_key,
)
from autoflow.domain.project_data.records import (
    ProjectDataRecords,
    validate_record_scalar,
)
from autoflow.domain.projects.models import ProjectError, ProjectOperation

WriteResult = tuple[dict[str, Any], ProjectOperation, bool]


class DataRecordService:
    def __init__(self, records: ProjectDataRecords):
        self.records = records

    def create(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> WriteResult:
        _ids(project_id, table_id)
        idem = _canonical_uuid(key, "Idempotency-Key")
        _exact(payload, {"datasetGeneration", "values"})
        generation = _canonical_uuid(
            payload.get("datasetGeneration"), "datasetGeneration"
        )
        values = _values(payload.get("values"))
        op = _record_operation(
            idem,
            "createRecord",
            project_id,
            table_id,
            {"datasetGeneration": generation, "values": _value_list(values)},
            None,
        )
        return self.records.create(project_id, table_id, generation, values, op)

    def create_many(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> WriteResult:
        _ids(project_id, table_id)
        idem = _canonical_uuid(key, "Idempotency-Key")
        _exact(payload, {"datasetGeneration", "expectedTableRevision", "rows"})
        generation = _canonical_uuid(payload["datasetGeneration"], "datasetGeneration")
        expected = _revision(payload["expectedTableRevision"], "expectedTableRevision")
        raw_rows = payload["rows"]
        if not isinstance(raw_rows, list) or not 1 <= len(raw_rows) <= 100:
            raise _validation("rows", "Must contain 1 to 100 rows")
        rows: list[tuple[str, dict[str, object]]] = []
        seen: set[str] = set()
        for raw in raw_rows:
            _exact(raw, {"clientRowId", "values"})
            row_id = _canonical_uuid(raw["clientRowId"], "clientRowId")
            if row_id in seen:
                raise _validation("rows", "Duplicate clientRowId")
            seen.add(row_id)
            rows.append((row_id, _values(raw["values"])))
        request = {
            "datasetGeneration": generation,
            "expectedTableRevision": expected,
            "rows": [
                {"clientRowId": rid, "values": _value_list(values)}
                for rid, values in rows
            ],
        }
        if (
            len(
                json.dumps(
                    request, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                ).encode("utf-8")
            )
            > 1024 * 1024
        ):
            raise ProjectError(
                "RECORD_BATCH_TOO_LARGE", "Record batch exceeds 1 MiB", 413
            )
        op = _record_operation(
            idem, "createRecords", project_id, table_id, request, None
        )
        return self.records.create_many(
            project_id, table_id, generation, expected, rows, op
        )

    def get(
        self,
        project_id: str,
        table_id: str,
        dataset_generation: str,
        encoded_record_key: str,
        record_key_type: str,
    ) -> dict[str, Any]:
        _ids(project_id, table_id)
        generation = _canonical_uuid(dataset_generation, "datasetGeneration")
        key = decode_record_key(encoded_record_key, record_key_type)
        value = self.records.get(project_id, table_id, generation, key)
        if value is None:
            raise ProjectError("RECORD_NOT_FOUND", "Record was not found", 404)
        return value

    def update(
        self,
        project_id: str,
        table_id: str,
        encoded_record_key: str,
        key: str,
        payload: dict[str, Any],
    ) -> WriteResult:
        _ids(project_id, table_id)
        idem = _canonical_uuid(key, "Idempotency-Key")
        _exact(
            payload,
            {"datasetGeneration", "recordKeyType", "values", "expectedContentRevision"},
        )
        generation = _canonical_uuid(
            payload.get("datasetGeneration"), "datasetGeneration"
        )
        record_key = decode_record_key(
            encoded_record_key, _key_type(payload.get("recordKeyType"))
        )
        values = _values(payload.get("values"))
        expected = _revision(
            payload.get("expectedContentRevision"), "expectedContentRevision"
        )
        request = {
            "datasetGeneration": generation,
            "recordKeyType": record_key.type,
            "recordKey": record_key.value,
            "values": _value_list(values),
            "expectedContentRevision": expected,
        }
        op = _record_operation(
            idem, "updateRecord", project_id, table_id, request, record_key
        )
        return self.records.update(
            project_id, table_id, generation, record_key, values, expected, op
        )

    def set_status(
        self,
        project_id: str,
        table_id: str,
        encoded_record_key: str,
        key: str,
        payload: dict[str, Any],
    ) -> WriteResult:
        _ids(project_id, table_id)
        idem = _canonical_uuid(key, "Idempotency-Key")
        allowed = {
            "datasetGeneration",
            "recordKeyType",
            "statusId",
            "expectedStatusRevision",
            "expectedFromStatusId",
        }
        _exact(
            payload,
            allowed,
            required={
                "datasetGeneration",
                "recordKeyType",
                "statusId",
                "expectedStatusRevision",
            },
        )
        generation = _canonical_uuid(payload["datasetGeneration"], "datasetGeneration")
        record_key = decode_record_key(
            encoded_record_key, _key_type(payload["recordKeyType"])
        )
        expected = _revision(
            payload["expectedStatusRevision"], "expectedStatusRevision"
        )
        status = _nullable_uuid(payload["statusId"], "statusId")
        has_from = "expectedFromStatusId" in payload
        from_status = (
            _nullable_uuid(payload.get("expectedFromStatusId"), "expectedFromStatusId")
            if has_from
            else None
        )
        request = {
            "datasetGeneration": generation,
            "recordKeyType": record_key.type,
            "recordKey": record_key.value,
            "statusId": status,
            "expectedStatusRevision": expected,
        }
        if has_from:
            request["expectedFromStatusId"] = from_status
        op = _record_operation(
            idem, "setRecordStatus", project_id, table_id, request, record_key
        )
        return self.records.set_status(
            project_id,
            table_id,
            generation,
            record_key,
            status,
            expected,
            has_from,
            from_status,
            op,
        )


def _ids(project_id: str, table_id: str) -> None:
    _canonical_uuid(project_id, "projectId")
    _canonical_uuid(table_id, "tableId")


def _exact(
    payload: object, allowed: set[str], required: set[str] | None = None
) -> None:
    if (
        not isinstance(payload, dict)
        or set(payload) - allowed
        or not (required or allowed).issubset(payload)
    ):
        raise _validation("form", "Invalid record request")


def _values(value: object) -> dict[str, object]:
    if not isinstance(value, list):
        raise _validation("values", "Must be an array")
    result: dict[str, object] = {}
    for item in value:
        if not isinstance(item, dict) or set(item) != {"fieldId", "value"}:
            raise _validation("values", "Invalid cell value")
        field_id = _canonical_uuid(item["fieldId"], "fieldId")
        if field_id in result:
            raise _validation("values", "Duplicate fieldId")
        result[field_id] = validate_record_scalar(item["value"])
    return result


def _value_list(values: dict[str, object]) -> list[dict[str, object]]:
    return [
        {"fieldId": field_id, "value": values[field_id]} for field_id in sorted(values)
    ]


def _revision(value: object, field: str) -> int:
    if type(value) is not int or not 1 <= value <= MAX_SAFE_INTEGER:
        raise _validation(field, "Must be a positive JSON-safe integer")
    return value


def _nullable_uuid(value: object, field: str) -> str | None:
    return None if value is None else _canonical_uuid(value, field)


def _key_type(value: object) -> str:
    if not isinstance(value, str):
        raise _validation("recordKeyType", "Must be text, integer, or uuid")
    return value


def _record_operation(
    key: str,
    kind: str,
    project_id: str,
    table_id: str,
    request: dict[str, Any],
    record_key: RecordKey | None,
) -> ProjectOperation:
    now = datetime.now(UTC)
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
    resource = (
        {"type": "table", "projectId": project_id, "tableId": table_id}
        if record_key is None
        else {
            "type": "record",
            "recordRef": {
                "projectId": project_id,
                "tableId": table_id,
                "datasetGeneration": request["datasetGeneration"],
                "recordKey": {"type": record_key.type, "value": record_key.value},
            },
        }
    )
    return replace(base, resource=resource)
