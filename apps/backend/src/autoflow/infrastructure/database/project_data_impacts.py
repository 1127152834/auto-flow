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
from autoflow.domain.workflows.runtime import TERMINAL_STATUSES

from .models import ProjectRow
from .project_data_models import (
    DataFieldRow,
    DataImpactRow,
    DataRecordRow,
    DataTableRow,
)
from .project_run_models import ProjectTaskInputSnapshotRow, ProjectTaskRow
from .workflow_runtime_models import WorkflowRunRow


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
    structural_change = any(
        change[key] != current[key] for key in ("key", "type", "required", "validation")
    )
    active_dependencies = (
        active_task_field_dependencies(session, project_id, table, field.id)
        if structural_change
        else []
    )
    blockers.extend(
        _blocker(
            "ACTIVE_TASK_FIELD_DEPENDENCY",
            dependency,
            "An active task depends on this field contract",
        )
        for dependency in active_dependencies
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
                "activeTaskDependencies": active_dependencies,
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


def active_task_field_dependencies(
    session: Session,
    project_id: str,
    table: DataTableRow,
    field_id: str,
    *, deleting_task_id: str | None = None,
) -> list[dict[str, Any]]:
    dependencies: list[dict[str, Any]] = []
    rows = session.execute(
        select(ProjectTaskRow, ProjectTaskInputSnapshotRow, WorkflowRunRow)
        .join(
            ProjectTaskInputSnapshotRow,
            ProjectTaskInputSnapshotRow.task_id == ProjectTaskRow.id,
        )
        .join(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
        .where(
            ProjectTaskRow.project_id == project_id,
            WorkflowRunRow.status.not_in(tuple(TERMINAL_STATUSES)),
        )
        .order_by(ProjectTaskRow.id)
    )
    for task, snapshot, run in rows:
        references: set[str] = set()
        for item in snapshot.inputs if isinstance(snapshot.inputs, list) else []:
            if not _input_targets_table(item, table):
                continue
            if any(
                isinstance(value, dict) and value.get("fieldId") == field_id
                for value in item.get("values", [])
            ):
                references.add("input.values")
            if any(
                _mapping_targets_field(mapping, table, field_id)
                for mapping in item.get("fieldMappings", [])
            ):
                references.add("input.fieldMappings")
        for binding in run.capability_bindings:
            if not _binding_targets_task(binding, project_id, task.id):
                continue
            if any(
                isinstance(grant, dict)
                and grant.get("tableId") == table.id
                and grant.get("datasetGeneration") == table.current_generation
                and field_id in grant.get("fieldIds", [])
                and not (task.id == deleting_task_id and grant.get("operations") == ["deleteField"])
                for grant in binding.get("tableGrants", [])
            ):
                references.add("capability.tableGrants")
        if references:
            order = (
                "input.fieldMappings",
                "input.values",
                "capability.tableGrants",
            )
            dependencies.append(
                {
                    "type": "task",
                    "projectId": project_id,
                    "taskId": task.id,
                    "runId": run.id,
                    "references": [item for item in order if item in references],
                }
            )
    return dependencies



def field_deletion_dependencies(session: Session, project_id: str, table: DataTableRow, field_id: str,
                                *, deleting_task_id: str | None = None) -> list[dict[str, Any]]:
    from .project_automation_models import ProjectAutomationRow
    from .project_sync_models import SheetsBindingRow, SyncOperationRow

    blockers: list[dict[str, Any]] = []
    if table.identity.get("fieldId") == field_id:
        blockers.append({"code": "IDENTITY_FIELD_PROTECTED", "message": "身份字段不能删除"})
    binding = session.get(SheetsBindingRow, table.id)
    if binding and any(item.get("fieldId") == field_id for item in binding.mapping):
        blockers.append({"code": "SOURCE_FIELD_MAPPING", "message": "字段仍有来源列映射，请先处理映射"})
    for automation in session.scalars(select(ProjectAutomationRow).where(ProjectAutomationRow.project_id == project_id)):
        if _references_field(automation.input_plan, field_id, table.current_generation):
            blockers.append({"code": "AUTOMATION_FIELD_DEPENDENCY", "message": "自动化输入或关联条件仍引用此字段"})
            break
    for dependency in active_task_field_dependencies(session, project_id, table, field_id, deleting_task_id=deleting_task_id):
        blockers.append({"code": "ACTIVE_TASK_FIELD_DEPENDENCY", "message": "活动任务的其他节点或输入仍依赖此字段",
                         "taskId": dependency["taskId"], "runId": dependency["runId"], "referenceSources": dependency["references"]})
    for operation in session.scalars(select(SyncOperationRow).where(SyncOperationRow.table_id == table.id, SyncOperationRow.status != "confirmed")):
        if operation.kind in {"column", "systemIdentity"} and operation.status == "failed" and (operation.attempts == 0 or (operation.error or {}).get("unsent") is True):
            continue
        if (operation.error or {}).get("code") == "SYNC_ABANDONED":
            continue
        if _references_field(operation.request, field_id, table.current_generation):
            blockers.append({"code": "PENDING_SYNC_FIELD_DEPENDENCY", "message": "未决同步操作仍引用此字段"})
            break
    return blockers


def _references_field(value: Any, field_id: str, generation: str) -> bool:
    if isinstance(value, dict):
        if value.get("datasetGeneration", generation) != generation:
            return False
        return any(key == field_id or (key in {"fieldId", "sourceFieldId", "targetFieldId"} and item == field_id)
                   or _references_field(item, field_id, generation) for key, item in value.items())
    if isinstance(value, list):
        return any(_references_field(item, field_id, generation) for item in value)
    return False


def _input_targets_table(item: Any, table: DataTableRow) -> bool:
    if not isinstance(item, dict):
        return False
    ref = item.get("recordRef")
    return (
        isinstance(ref, dict)
        and ref.get("tableId") == table.id
        and ref.get("datasetGeneration") == table.current_generation
    )


def _mapping_targets_field(mapping: Any, table: DataTableRow, field_id: str) -> bool:
    if not isinstance(mapping, dict):
        return False
    ref = mapping.get("fieldRef")
    return (
        isinstance(ref, dict)
        and ref.get("tableId") == table.id
        and ref.get("datasetGeneration") == table.current_generation
        and ref.get("fieldId") == field_id
    ) or mapping.get("fieldId") == field_id


def _binding_targets_task(
    binding: Any,
    project_id: str,
    task_id: str,
) -> bool:
    return (
        isinstance(binding, dict)
        and binding.get("capability") == "project.data"
        and binding.get("projectId") == project_id
        and binding.get("taskId") == task_id
        and isinstance(binding.get("tableGrants", []), list)
    )


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
