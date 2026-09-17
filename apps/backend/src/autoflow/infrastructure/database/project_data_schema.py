"""Consistent schema previews and bounded, atomic consumption of their evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from tempfile import SpooledTemporaryFile
from time import monotonic
from typing import IO, Any
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.rules import validate_value
from autoflow.domain.project_data.schema import (
    backfill_budget,
    canonical_bytes,
    validate_candidate,
)
from autoflow.domain.projects.models import ProjectError, ProjectOperation

from .project_data import (
    SqlAlchemyProjectData,
    _completed,
    _operation,
    _operation_result,
    _operation_row,
)
from .project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
    _change,
    _field,
    _record_resource,
)
from .project_data_impacts import active_task_field_dependencies
from .project_data_models import (
    DataFieldRow,
    DataImpactRow,
    DataRecordRow,
    DataTableRow,
)


class SqlAlchemyProjectDataSchema:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def preview(self, project_id: str, table_id: str, candidate: dict) -> dict:
        candidate = validate_candidate(candidate)
        with SpooledTemporaryFile(
            mode="w+t", max_size=2 * 1024 * 1024, encoding="utf-8"
        ) as spool:
            with self._session_factory() as session:
                session.execute(text("BEGIN"))
                table, fields = _snapshot(session, project_id, table_id, candidate)
                _validate_snapshot(candidate, fields, table)
                expected = _revisions(table, fields)
                before = {row.id: _definition(row) for row in fields}
                count = 0
                for row in session.scalars(
                    select(DataRecordRow)
                    .where(
                        DataRecordRow.project_id == project_id,
                        DataRecordRow.table_id == table_id,
                        DataRecordRow.dataset_generation == table.current_generation,
                        DataRecordRow.deleted.is_(False),
                    )
                    .order_by(DataRecordRow.key_type, DataRecordRow.key_value)
                    .execution_options(yield_per=200)
                ):
                    spool.write(
                        json.dumps(
                            {
                                "keyType": row.key_type,
                                "keyValue": row.key_value,
                                "contentRevision": row.content_revision,
                                "values": row.values_json,
                            }
                        )
                        + "\n"
                    )
                    count += 1
                session.rollback()
            spool.seek(0)
            report, prepared = _validate_rows(candidate, before, spool, count)
            with self._session_factory() as session:
                session.execute(text("BEGIN IMMEDIATE"))
                table, fields = _snapshot(session, project_id, table_id, candidate)
                if _revisions(table, fields) != expected:
                    raise _stale()
                report["blockers"].extend(
                    _active_task_field_blockers(
                        session, project_id, table, fields, candidate
                    )
                )
                now = datetime.now(UTC)
            expires = now + timedelta(minutes=10)
            saved = DataImpactRow(
                project_id=project_id,
                action="saveTableSchema",
                target=_target(project_id, table_id, candidate),
                change_digest=_digest(candidate),
                expected_revisions=expected,
                facts_digest=_digest(expected),
                report={},
                expires_at=expires,
            )
            session.add(saved)
            session.flush()
            report.update(
                impactRevision=saved.id,
                calculatedAt=now.isoformat(),
                expiresAt=expires.isoformat(),
            )
            saved.report = {"public": report, "prepared": prepared}
            session.commit()
            return report

    def commit(
        self,
        project_id: str,
        table_id: str,
        candidate: dict,
        impact_revision: int,
        operation: ProjectOperation,
    ) -> tuple[dict, ProjectOperation, bool]:
        candidate = validate_candidate(candidate)
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            SqlAlchemyProjectData._guard_project_read(session, project_id)
            existing = SqlAlchemyProjectDataCatalog._existing(session, operation)
            if existing is not None:
                session.rollback()
                return _operation_result(existing), _operation(existing), True
            table, fields = _snapshot(session, project_id, table_id, candidate)
            saved = session.get(DataImpactRow, impact_revision)
            if (
                saved is None
                or saved.project_id != project_id
                or saved.action != "saveTableSchema"
                or saved.target != _target(project_id, table_id, candidate)
                or saved.change_digest != _digest(candidate)
                or saved.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC)
                or saved.expected_revisions != _revisions(table, fields)
            ):
                raise _stale()
            saved_blockers = saved.report["public"]["blockers"]
            if saved_blockers:
                raise _stale(saved_blockers)
            _validate_snapshot(candidate, fields, table)
            active_task_blockers = _active_task_field_blockers(
                session, project_id, table, fields, candidate
            )
            if active_task_blockers:
                raise _stale(active_task_blockers)
            prepared = saved.report["prepared"]
            backfill_budget([entry["values"] for entry in prepared["records"]])
            current = {field.id: field for field in fields}
            changes: list[tuple[dict | None, dict, dict]] = []
            now = datetime.now(UTC)
            position = max((field.position for field in fields), default=-1) + 1
            for item in candidate["fields"]:
                definition = item["definition"]
                if item["kind"] == "existing":
                    field = current[item["fieldId"]]
                    if _definition(field) == definition:
                        continue
                    before = _field(field)
                    for key, value in definition.items():
                        setattr(field, key, value)
                    field.field_revision += 1
                else:
                    before = None
                    field = DataFieldRow(
                        id=prepared["createdFieldIds"][item["clientId"]],
                        project_id=project_id,
                        table_id=table_id,
                        dataset_generation=table.current_generation,
                        **definition,
                        writable=True,
                        formula=False,
                        field_revision=1,
                        position=position,
                    )
                    position += 1
                    current[field.id] = field
                    session.add(field)
                after = _field(field)
                changes.append(
                    (before, after, {"type": "field", "fieldRef": after["ref"]})
                )
            for entry in prepared["records"]:
                row = session.get(
                    DataRecordRow,
                    (table.current_generation, entry["keyType"], entry["keyValue"]),
                )
                if (
                    row is None
                    or row.project_id != project_id
                    or row.table_id != table_id
                    or row.deleted
                    or row.content_revision != entry["contentRevision"]
                ):
                    raise _stale()
                before = {
                    "values": row.values_json,
                    "contentRevision": row.content_revision,
                }
                row.values_json = entry["values"]
                row.content_revision += 1
                row.updated_at = now
                changes.append(
                    (
                        before,
                        {
                            "values": row.values_json,
                            "contentRevision": row.content_revision,
                        },
                        _record_resource(project_id, table_id, row),
                    )
                )
            if changes:
                table.table_revision += 1
                table.updated_at = now
            result = {
                "action": "saveSchema",
                "datasetGeneration": table.current_generation,
                "tableRevision": table.table_revision,
                "fields": [
                    _field(field)
                    for field in sorted(
                        current.values(), key=lambda field: field.position
                    )
                ],
                "createdFieldIds": prepared["createdFieldIds"],
                "backfilledRecords": len(prepared["records"]),
            }
            done = _completed(operation, result)
            session.add(_operation_row(done))
            session.flush()
            for sequence, (before, after, resource) in enumerate(changes, 1):
                session.add(_change(done, sequence, before, after, resource))
            session.commit()
            return result, done, False


def _snapshot(session: Session, project_id: str, table_id: str, candidate: dict):
    table = SqlAlchemyProjectDataCatalog._table(session, project_id, table_id, True)
    if table.current_generation != candidate["datasetGeneration"]:
        raise ProjectError("DATASET_GENERATION_GONE", "Dataset was replaced", 410)
    SqlAlchemyProjectDataCatalog._cas(
        table.table_revision, candidate["expectedTableRevision"]
    )
    fields = session.scalars(
        select(DataFieldRow)
        .where(
            DataFieldRow.project_id == project_id,
            DataFieldRow.table_id == table_id,
            DataFieldRow.dataset_generation == table.current_generation,
        )
        .order_by(DataFieldRow.position)
    ).all()
    return table, fields


def _identity(table: DataTableRow) -> str | None:
    return (
        table.identity.get("fieldId") if table.identity.get("mode") == "field" else None
    )


def _validate_snapshot(candidate: dict, fields, table: DataTableRow) -> None:
    # Defaults were validated before opening a transaction. Never execute their
    # user regex again while holding a read snapshot or the commit write lock.
    without_defaults = {
        **candidate,
        "fields": [
            {
                key: value
                for key, value in item.items()
                if key != "existingRecordDefault"
            }
            for item in candidate["fields"]
        ],
    }
    validate_candidate(
        without_defaults, [_field(row) for row in fields], _identity(table)
    )


def _definition(field: DataFieldRow) -> dict:
    return {
        key: getattr(field, key)
        for key in ("key", "name", "type", "required", "validation")
    }


def _revisions(table: DataTableRow, fields) -> dict:
    return {
        "tableRevision": table.table_revision,
        "datasetGeneration": table.current_generation,
        "schemaGuardRevision": table.schema_guard_revision,
        "fieldRevisions": {field.id: field.field_revision for field in fields},
    }


def _target(project_id: str, table_id: str, candidate: dict) -> dict:
    return {
        "type": "table",
        "projectId": project_id,
        "tableId": table_id,
        "datasetGeneration": candidate["datasetGeneration"],
    }


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _stale(blockers: list[dict] | None = None) -> ProjectError:
    details: dict[str, object] = {
        "domainCode": "impact_stale",
        "retryable": False,
    }
    if blockers is not None:
        details["blockers"] = blockers
    return ProjectError(
        "IMPACT_STALE",
        "Schema preview is no longer valid",
        409,
        details,
    )


def _issue(code: str, item: dict | None, message: str, count: int | None) -> dict:
    return {
        "code": code,
        "fieldId": item.get("fieldId") if item else None,
        "clientId": item.get("clientId") if item else None,
        "message": message,
        "affectedRecords": count,
    }


def _active_task_field_blockers(
    session: Session,
    project_id: str,
    table: DataTableRow,
    fields: list[DataFieldRow],
    candidate: dict,
) -> list[dict]:
    current = {field.id: field for field in fields}
    blockers = []
    for item in candidate["fields"]:
        if item["kind"] != "existing":
            continue
        field = current[item["fieldId"]]
        if not any(
            item["definition"][key] != getattr(field, key)
            for key in ("key", "type", "required", "validation")
        ):
            continue
        for dependency in active_task_field_dependencies(
            session, project_id, table, field.id
        ):
            references = ", ".join(dependency["references"])
            blocker = _issue(
                "ACTIVE_TASK_FIELD_DEPENDENCY",
                item,
                f"An active task depends on this field via {references}",
                None,
            )
            blocker.update(
                taskId=dependency["taskId"],
                runId=dependency["runId"],
                referenceSources=dependency["references"],
            )
            blockers.append(blocker)
    return blockers


def _validate_rows(
    candidate: dict, before: dict, spool: IO[str], count: int
) -> tuple[dict, dict]:
    new = [item for item in candidate["fields"] if item["kind"] == "new"]
    created = {item["clientId"]: str(uuid4()) for item in new}
    defaults = {
        created[item["clientId"]]: item["existingRecordDefault"]
        for item in new
        if "existingRecordDefault" in item
    }
    blockers: list[dict] = []
    warnings: list[dict] = []
    for item in new:
        if (
            count
            and item["definition"]["required"]
            and "existingRecordDefault" not in item
        ):
            blockers.append(
                _issue(
                    "EXISTING_RECORD_DEFAULT_REQUIRED",
                    item,
                    "A valid default is required for existing records",
                    count,
                )
            )
    existing = [item for item in candidate["fields"] if item["kind"] == "existing"]
    changed = {
        item["fieldId"]
        for item in existing
        if any(
            item["definition"][key] != before[item["fieldId"]][key]
            for key in ("type", "required", "validation")
        )
    }
    to_validate = [item for item in existing if item["fieldId"] in changed]
    invalid = {item["fieldId"]: 0 for item in to_validate}
    records: list[dict[str, Any]] = []
    byte_count = 0
    write_count = 0
    deadline = monotonic() + 120
    invalid_json = False

    def check_deadline() -> None:
        if monotonic() >= deadline:
            raise ProjectError(
                "FIELD_VALIDATION_TIMEOUT",
                "Schema validation exceeded its time budget",
                422,
            )

    for line in spool:
        check_deadline()
        row = json.loads(line)
        for item in to_validate:
            check_deadline()
            try:
                validate_value(item["definition"], row["values"].get(item["fieldId"]))
            except ProjectError as error:
                if error.code == "PATTERN_VALIDATION_TIMEOUT":
                    raise
                invalid[item["fieldId"]] += 1
            finally:
                check_deadline()
        if defaults:
            values = {**row["values"], **defaults}
            write_count += 1
            try:
                byte_count += len(canonical_bytes(values))
            except (ValueError, UnicodeError):
                invalid_json = True
            if (
                write_count <= 1000
                and byte_count <= 4 * 1024 * 1024
                and not invalid_json
            ):
                records.append({**row, "values": values})
            else:
                records.clear()
        check_deadline()
    for item in to_validate:
        number = invalid[item["fieldId"]]
        if number:
            blockers.append(
                _issue(
                    "FIELD_VALUES_INCOMPATIBLE",
                    item,
                    "Existing values do not satisfy the field rules",
                    number,
                )
            )
    if write_count > 1000 or byte_count > 4 * 1024 * 1024:
        blockers.append(
            _issue(
                "SCHEMA_BACKFILL_LIMIT",
                None,
                "本次字段变更需要更新的数据量超过一次保存上限",
                write_count,
            )
        )
    if invalid_json:
        blockers.append(
            _issue(
                "SCHEMA_BACKFILL_INVALID_JSON",
                None,
                "Existing values cannot be preserved as strict UTF-8 JSON",
                write_count,
            )
        )
    return (
        {
            "affectedRecords": count if changed or defaults else 0,
            "backfillBytes": byte_count,
            "blockers": blockers,
            "warnings": warnings,
            "referenceAvailability": {
                "automations": "notImplemented",
                "sync": "notImplemented",
            },
        },
        {"createdFieldIds": created, "records": records},
    )
