"""Persisted field-change confirmations, rechecked inside the writer's transaction."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from tempfile import SpooledTemporaryFile
from time import monotonic
from typing import IO, Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.rules import validate_field, validate_value
from autoflow.domain.projects.models import ProjectError

from .models import ProjectRow
from .project_data_models import (
    DataFieldRow,
    DataImpactRow,
    DataRecordRow,
    DataTableRow,
)


class SqlAlchemyProjectDataImpacts:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def preview_field_update(
        self, project_id: str, ref: dict, definition: dict
    ) -> dict:
        change = validate_field(definition)
        target = _target(project_id, ref)
        # Only identity/value projections are spooled, never the entire table in RAM.
        with SpooledTemporaryFile(
            mode="w+t", max_size=2 * 1024 * 1024, encoding="utf-8"
        ) as rows:
            with self._session_factory() as session:
                session.execute(text("BEGIN"))
                report, facts_digest, count = _field_facts(
                    session, project_id, target, change, validation_rows=rows
                )
                session.rollback()
            # Potentially expensive user rules execute without any database lock.
            rows.seek(0)
            _validate_rows(change, rows, report, count)
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            now = datetime.now(UTC)
            saved = DataImpactRow(
                project_id=project_id,
                action="updateField",
                target=target,
                change_digest=_digest(change),
                expected_revisions=report["expectedRevisions"],
                facts_digest=facts_digest,
                report={},
                expires_at=now + timedelta(minutes=10),
            )
            session.add(saved)
            session.flush()
            report.update(impactRevision=saved.id, calculatedAt=now.isoformat())
            saved.report = report
            session.commit()
            return report

    def require_field_update(
        self,
        session: Session,
        project_id: str,
        ref: dict,
        definition: dict,
        impact_revision: int,
    ) -> dict:
        """Never begin/commit here: the caller owns the write unit of work."""
        change = validate_field(definition)
        target = _target(project_id, ref)
        if type(impact_revision) is not int or impact_revision < 1:
            raise _stale()
        saved = session.get(DataImpactRow, impact_revision)
        if (
            saved is None
            or saved.project_id != project_id
            or saved.action != "updateField"
            or saved.target != target
            or saved.change_digest != _digest(change)
            or _utc(saved.expires_at) <= datetime.now(UTC)
        ):
            raise _stale()
        current, facts_digest, _ = _field_facts(session, project_id, target, change)
        if (
            saved.expected_revisions != current["expectedRevisions"]
            or saved.facts_digest != facts_digest
            or saved.report["blockers"]
            or current["blockers"]
        ):
            raise _stale(current["blockers"])
        return saved.report


def _target(project_id: str, ref: dict) -> dict:
    keys = {"projectId", "tableId", "datasetGeneration", "fieldId"}
    if not isinstance(ref, dict) or set(ref) != keys:
        raise ProjectError("INVALID_PROJECT_DATA", "Invalid field reference", 422)
    for value in (project_id, *ref.values()):
        try:
            if not isinstance(value, str) or str(UUID(value)) != value:
                raise ValueError
        except (ValueError, TypeError, AttributeError) as error:
            raise ProjectError(
                "INVALID_PROJECT_DATA", "Invalid field identity", 422
            ) from error
    if ref["projectId"] != project_id:
        raise ProjectError("FIELD_NOT_FOUND", "Field was not found", 404)
    return {"type": "field", "fieldRef": ref.copy()}


def _field_facts(
    session: Session,
    project_id: str,
    target: dict,
    change: dict,
    *,
    validation_rows: IO[str] | None = None,
) -> tuple[dict, str, int]:
    ref = target["fieldRef"]
    project = session.get(ProjectRow, project_id)
    if project is None or project.lifecycle_state == "deleted":
        raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)
    table = session.scalar(
        select(DataTableRow).where(
            DataTableRow.published.is_(True),
            DataTableRow.id == ref["tableId"],
            DataTableRow.project_id == project_id,
        )
    )
    if table is None:
        raise ProjectError("TABLE_NOT_FOUND", "Table was not found", 404)
    if table.current_generation != ref["datasetGeneration"]:
        raise ProjectError("DATASET_GENERATION_GONE", "Dataset was replaced", 410)
    field = session.scalar(
        select(DataFieldRow).where(
            DataFieldRow.project_id == project_id,
            DataFieldRow.table_id == table.id,
            DataFieldRow.dataset_generation == table.current_generation,
            DataFieldRow.id == ref["fieldId"],
        )
    )
    if field is None:
        raise ProjectError("FIELD_NOT_FOUND", "Field was not found", 404)
    current = {
        "key": field.key,
        "name": field.name,
        "type": field.type,
        "required": field.required,
        "validation": field.validation,
    }
    blockers = []
    if change != current and (field.formula or not field.writable):
        blockers.append(_blocker("FIELD_READ_ONLY", target, "This field is read-only"))
    if (
        table.identity == {"mode": "field", "fieldId": field.id}
        and change["type"] != field.type
    ):
        blockers.append(
            _blocker(
                "IDENTITY_FIELD_PROTECTED",
                target,
                "Identity field type cannot be changed",
            )
        )
    revisions = {
        "tableRevision": table.table_revision,
        "fieldRevision": field.field_revision,
    }
    hasher = hashlib.sha256()
    hasher.update(
        _json(
            {
                "target": target,
                "revisions": revisions,
                "definition": current,
                "identity": table.identity,
                "sourceKind": table.source_kind,
                "formula": field.formula,
                "writable": field.writable,
            }
        )
    )
    rows = session.scalars(
        select(DataRecordRow)
        .where(
            DataRecordRow.project_id == project_id,
            DataRecordRow.table_id == table.id,
            DataRecordRow.dataset_generation == table.current_generation,
            DataRecordRow.deleted.is_(False),
        )
        .order_by(DataRecordRow.key_type, DataRecordRow.key_value)
        .execution_options(yield_per=500)
    )
    count = 0
    for row in rows:
        count += 1
        value = row.values_json.get(field.id)
        hasher.update(
            b"\n" + _json([row.key_type, row.key_value, row.content_revision, value])
        )
        if validation_rows is not None:
            record_ref = {
                "projectId": project_id,
                "tableId": table.id,
                "datasetGeneration": table.current_generation,
                "recordKey": {"type": row.key_type, "value": row.key_value},
            }
            validation_rows.write(
                _json({"ref": record_ref, "value": value}).decode() + "\n"
            )
    report: dict[str, Any] = {
        "target": target,
        "changeDigest": _digest(change),
        "expectedRevisions": revisions,
        "impacts": [],
        "blockers": blockers,
    }
    return report, hasher.hexdigest(), count


def _validate_rows(change: dict, rows: IO[str], report: dict, count: int) -> None:
    incompatible = 0
    deadline = monotonic() + 120
    for line in rows:
        if monotonic() >= deadline:
            raise ProjectError(
                "FIELD_VALIDATION_TIMEOUT",
                "Field validation exceeded its time budget",
                422,
            )
        entry = json.loads(line)
        try:
            validate_value(change, entry["value"])
        except ProjectError as error:
            if error.code == "PATTERN_VALIDATION_TIMEOUT":
                raise
            incompatible += 1
            if incompatible <= 20:
                report["blockers"].append(
                    _blocker(
                        "FIELD_VALUES_INCOMPATIBLE",
                        {"type": "record", "recordRef": entry["ref"]},
                        "Record value does not satisfy the new field rules",
                    )
                )
    if incompatible > 20:
        report["blockers"].append(
            _blocker(
                "FIELD_VALUES_INCOMPATIBLE_SUMMARY",
                report["target"],
                f"{incompatible} records do not satisfy the new field rules; first 20 shown",
            )
        )
    report["impacts"] = [
        {
            "code": "FIELD_RECORD_VALIDATION",
            "resource": report["target"],
            "message": f"Validated {count} records; {incompatible} incompatible",
            "blocking": bool(incompatible),
        }
    ]


def _blocker(code: str, resource: dict, message: str) -> dict:
    return {"code": code, "resource": resource, "state": "blocked", "message": message}


def _json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _stale(blockers: list | None = None) -> ProjectError:
    return ProjectError(
        "PRECONDITION_FAILED",
        "Recalculate the field change impact before saving",
        412,
        {"blockers": blockers or [], "retryable": False},
    )
