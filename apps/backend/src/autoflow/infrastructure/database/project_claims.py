from __future__ import annotations

import json
from functools import cmp_to_key
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from autoflow.domain.project_data.identity import RecordKey, RecordKeyType
from autoflow.domain.project_data.query import (
    MISSING,
    compare_values,
    matches,
    validate_filter,
    validate_order,
)
from autoflow.domain.project_runs.input_selection import (
    Candidate,
    InputCandidates,
    InputSelection,
    LeaseKey,
    RecordRef,
    SelectedInput,
    select_required_inputs,
)
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataRecordRow,
    DataStatusRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectRecordLeaseRow,
    ProjectTaskRecordCursorRow,
)


class SqlAlchemyProjectInputGroups:
    """Select and hold one V1 two-input group inside the caller's transaction."""

    def __init__(self, session: Session):
        self.session = session

    def select_required(self, project_id: str, input_plan: dict[str, Any]) -> InputSelection:
        raw_inputs = input_plan.get("inputs") if isinstance(input_plan, dict) else None
        if not isinstance(raw_inputs, list):
            return InputSelection("configurationError")
        sources: list[InputCandidates] = []
        for item in raw_inputs:
            if (
                not isinstance(item, dict)
                or item.get("mode") != "independent"
                or item.get("required") is not True
                or not isinstance(item.get("inputId"), str)
            ):
                sources.append(InputCandidates(str(item.get("inputId", "invalid")), (), "V1 requires independent required inputs"))
                continue
            sources.append(self._candidates(project_id, item))
        return select_required_inputs(sources)

    def hold(
        self,
        selection: InputSelection,
        *,
        project_id: str,
        batch_id: str,
        task_id: str,
        run_id: str,
        now: Any,
    ) -> list[dict[str, Any]]:
        if selection.status != "ready":
            raise ValueError("only a ready input group can be held")
        by_key = {selected.lease_key: selected for selected in selection.inputs}
        lease_rows: dict[LeaseKey, ProjectRecordLeaseRow] = {}
        for lease_key in selection.lease_keys:
            selected = by_key[lease_key]
            record_ref = _record_ref(selected.record_ref)
            lease = ProjectRecordLeaseRow(
                id=str(uuid4()),
                lease_key=_lease_key(lease_key),
                project_id=project_id,
                batch_id=batch_id,
                task_id=task_id,
                run_id=run_id,
                record_ref=record_ref,
                lease_generation=1,
                state="held",
                created_at=now,
                updated_at=now,
                released_at=None,
            )
            self.session.add(lease)
            self.session.flush()
            value = selected.value
            cursor = ProjectTaskRecordCursorRow(
                id=str(uuid4()),
                task_id=task_id,
                lease_id=lease.id,
                record_ref=record_ref,
                content_revision=int(value["contentRevision"]),
                status_revision=int(value["statusRevision"]),
                link_revision=int(value["linkRevision"]),
                source="initialInput",
                updated_at=now,
            )
            self.session.add(cursor)
            lease_rows[lease_key] = lease
        return [
            _snapshot_input(selected, lease_rows[selected.lease_key].id, now)
            for selected in selection.inputs
        ]

    def _candidates(self, project_id: str, item: dict[str, Any]) -> InputCandidates:
        input_id = item["inputId"]
        table_id, generation = item.get("tableId"), item.get("datasetGeneration")
        if not isinstance(table_id, str) or not isinstance(generation, str):
            return InputCandidates(input_id, (), "table identity is invalid")
        table = self.session.scalar(
            select(DataTableRow).where(
                DataTableRow.project_id == project_id,
                DataTableRow.id == table_id,
                DataTableRow.published.is_(True),
            )
        )
        if table is None or table.current_generation != generation:
            return InputCandidates(input_id, (), "table generation is no longer current")
        fields = list(
            self.session.scalars(
                select(DataFieldRow)
                .where(
                    DataFieldRow.project_id == project_id,
                    DataFieldRow.table_id == table_id,
                    DataFieldRow.dataset_generation == generation,
                )
                .order_by(DataFieldRow.position, DataFieldRow.id)
            )
        )
        field_types = {field.id: field.type for field in fields}
        statuses = set(
            self.session.scalars(
                select(DataStatusRow.id).where(
                    DataStatusRow.project_id == project_id,
                    DataStatusRow.table_id == table_id,
                    DataStatusRow.deleted.is_(False),
                )
            )
        )
        try:
            filter_value = validate_filter(item.get("filter"), field_types, statuses)
            order_value = validate_order(item.get("orderBy"), field_types)
        except ProjectError as error:  # validated management data may become stale
            return InputCandidates(input_id, (), str(error))
        rows = list(
            self.session.scalars(
                select(DataRecordRow).where(
                    DataRecordRow.project_id == project_id,
                    DataRecordRow.table_id == table_id,
                    DataRecordRow.dataset_generation == generation,
                    DataRecordRow.deleted.is_(False),
                )
            )
        )
        rows = [row for row in rows if matches(filter_value, row.values_json, row.status_id)]
        rows.sort(key=cmp_to_key(lambda left, right: _compare_rows(left, right, order_value, field_types)))
        active = set(
            self.session.scalars(
                select(ProjectRecordLeaseRow.lease_key).where(
                    ProjectRecordLeaseRow.state.in_(("held", "reconciling"))
                )
            )
        )
        candidates: list[Candidate] = []
        for row in rows:
            ref = RecordRef(
                project_id,
                table_id,
                generation,
                RecordKey(
                    cast(RecordKeyType, row.key_type),
                    cast(str, row.key_value),
                ),
            )
            lease = LeaseKey("local", project_id, table_id, generation, ref.record_key)
            value = {
                "alias": item.get("alias", input_id),
                "tableDisplay": table.name,
                "recordRef": _record_ref(ref),
                "fieldMappings": _mutable(item.get("fieldBindings", [])),
                "values": [
                    {"fieldId": field.id, "fieldName": field.name, "value": row.values_json[field.id]}
                    for field in fields
                    if field.id in row.values_json
                ],
                "statusId": row.status_id,
                "recordSlots": _mutable(row.record_slots),
                "currentEnvironmentId": row.current_environment_id,
                "sourceSummary": {"kind": table.source_kind, "name": table.name},
                "contentRevision": row.content_revision,
                "statusRevision": row.status_revision,
                "linkRevision": row.link_revision,
            }
            candidates.append(Candidate(ref, lease, value, _lease_key(lease) not in active))
        return InputCandidates(input_id, tuple(candidates))


def _snapshot_input(
    selected: SelectedInput, lease_id: str, captured_at: Any | None = None
) -> dict[str, Any]:
    return {
        "inputId": selected.input_id,
        "leaseId": lease_id,
        **({"capturedAt": captured_at.isoformat()} if captured_at is not None else {}),
        **_mutable(selected.value),
    }


def active_record_lease(
    session: Session,
    project_id: str,
    table_id: str,
    dataset_generation: str,
    record_key: RecordKey,
) -> ProjectRecordLeaseRow | None:
    value = ProjectRecordLeaseRow.record_ref["recordKey"]["value"]
    key_condition = (
        value.as_integer() == record_key.value
        if record_key.type == "integer"
        else value.as_string() == record_key.value
    )
    return session.scalar(
        select(ProjectRecordLeaseRow).where(
            ProjectRecordLeaseRow.project_id == project_id,
            ProjectRecordLeaseRow.state.in_(("held", "reconciling")),
            ProjectRecordLeaseRow.record_ref["tableId"].as_string() == table_id,
            ProjectRecordLeaseRow.record_ref["datasetGeneration"].as_string()
            == dataset_generation,
            ProjectRecordLeaseRow.record_ref["recordKey"]["type"].as_string()
            == record_key.type,
            key_condition,
        )
    )


def _mutable(value: Any) -> Any:
    if isinstance(value, dict) or hasattr(value, "items"):
        return {key: _mutable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_mutable(item) for item in value]
    if isinstance(value, frozenset | set):
        return [_mutable(item) for item in value]
    return value


def _record_ref(value: RecordRef) -> dict[str, Any]:
    return {
        "projectId": value.project_id,
        "tableId": value.table_id,
        "datasetGeneration": value.dataset_generation,
        "recordKey": {"type": value.record_key.type, "value": value.record_key.value},
    }


def _lease_key(value: LeaseKey) -> str:
    return json.dumps(
        {"source": value.source, **_record_ref(RecordRef(value.project_id, value.table_id, value.dataset_generation, value.record_key))},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _compare_rows(left: DataRecordRow, right: DataRecordRow, order: list[dict[str, str]], field_types: dict[str, str]) -> int:
    for item in order:
        if "fieldId" in item:
            field_id = item["fieldId"]
            a, b = left.values_json.get(field_id, MISSING), right.values_json.get(field_id, MISSING)
            if (a is MISSING or a is None) != (b is MISSING or b is None):
                result = 1 if a is MISSING or a is None else -1
            elif a is MISSING or a is None:
                result = 0
            else:
                result = compare_values(field_types[field_id], a, b) or 0
        else:
            field = item["systemField"]
            if field == "status":
                a, b = left.status_id, right.status_id
            elif field == "createdAt":
                a, b = left.created_at, right.created_at
            elif field == "updatedAt":
                a, b = left.updated_at, right.updated_at
            else:
                a, b = (left.key_type, left.key_value), (right.key_type, right.key_value)
            result = (a > b) - (a < b) if a is not None and b is not None else (0 if a == b else (1 if a is None else -1))
        if result:
            return result if item["direction"] == "asc" else -result
    return ((left.key_type, left.key_value) > (right.key_type, right.key_value)) - ((left.key_type, left.key_value) < (right.key_type, right.key_value))
