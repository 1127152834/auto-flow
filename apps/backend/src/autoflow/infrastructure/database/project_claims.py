from __future__ import annotations

import json
from functools import cmp_to_key
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from autoflow.domain.project_data.identity import (
    RecordKey,
    RecordKeyType,
    encode_record_key,
)
from autoflow.domain.project_data.query import (
    MISSING,
    compare_values,
    matches,
    validate_filter,
    validate_order,
)
from autoflow.domain.project_runs.input_selection import (
    MAX_CANDIDATE_EVALUATIONS,
    Candidate,
    FieldEqualsRelation,
    InputCandidates,
    InputSelection,
    LeaseKey,
    RecordRef,
    RecordSlotRelation,
    SameRecordRelation,
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
        if not all(isinstance(item, dict) for item in raw_inputs):
            return InputSelection("configurationError")
        definitions = {
            item.get("inputId"): item
            for item in raw_inputs
            if isinstance(item.get("inputId"), str)
        }
        if len(definitions) != len(raw_inputs):
            return InputSelection("configurationError")
        sources: list[InputCandidates] = []
        for item in raw_inputs:
            sources.append(self._candidates(project_id, item, definitions))
        return select_required_inputs(sources)

    def hold(
        self,
        selection: InputSelection,
        *,
        input_plan: dict[str, Any],
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
        selected_snapshots = {
            selected.input_id: _snapshot_input(
                selected, lease_rows[selected.lease_key].id, now
            )
            for selected in selection.inputs
        }
        unavailable = {
            item.input_id: item.reason for item in selection.unavailable_inputs
        }
        snapshots: list[dict[str, Any]] = []
        for item in input_plan.get("inputs", []):
            input_id = item.get("inputId")
            if input_id in selected_snapshots:
                snapshots.append(selected_snapshots[input_id])
            elif input_id in unavailable:
                table = self.session.get(DataTableRow, item.get("tableId"))
                snapshots.append(
                    {
                        "inputId": input_id,
                        "alias": item.get("alias", input_id),
                        "tableDisplay": table.name if table is not None else "数据表已失效",
                        "recordRef": None,
                        "values": [],
                        "unavailableReason": unavailable[input_id],
                        "capturedAt": now.isoformat(),
                    }
                )
        return snapshots

    def _candidates(
        self,
        project_id: str,
        item: dict[str, Any],
        definitions: dict[str, dict[str, Any]],
    ) -> InputCandidates:
        input_id = item["inputId"]
        table_id, generation = item.get("tableId"), item.get("datasetGeneration")
        required, mode = item.get("required"), item.get("mode")
        if type(required) is not bool or mode not in {
            "independent",
            "fixedRecord",
            "related",
        }:
            return InputCandidates(input_id, (), "input mode is invalid")
        if not isinstance(table_id, str) or not isinstance(generation, str):
            return InputCandidates(
                input_id, (), "table identity is invalid", required=required, mode=mode
            )
        table = self.session.scalar(
            select(DataTableRow).where(
                DataTableRow.project_id == project_id,
                DataTableRow.id == table_id,
                DataTableRow.published.is_(True),
            )
        )
        if table is None or table.current_generation != generation:
            return InputCandidates(
                input_id,
                (),
                "table generation is no longer current",
                required=required,
                mode=mode,
            )
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
        definition = _selection_definition(
            self.session,
            project_id,
            item,
            definitions,
            field_types,
        )
        if isinstance(definition, str):
            return InputCandidates(
                input_id, (), definition, required=required, mode=mode
            )
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
            return InputCandidates(
                input_id, (), str(error), required=required, mode=mode, **definition
            )
        rows = list(
            self.session.scalars(
                select(DataRecordRow).where(
                    DataRecordRow.project_id == project_id,
                    DataRecordRow.table_id == table_id,
                    DataRecordRow.dataset_generation == generation,
                    DataRecordRow.deleted.is_(False),
                ).limit(MAX_CANDIDATE_EVALUATIONS + 1)
            )
        )
        if len(rows) > MAX_CANDIDATE_EVALUATIONS:
            return InputCandidates(
                input_id,
                (),
                required=required,
                mode=mode,
                scan_budget_exceeded=True,
                **definition,
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
            try:
                record_slots = {
                    slot["slotId"]: (
                        _parse_record_ref(slot["target"])
                        if slot.get("target") is not None
                        else None
                    )
                    for slot in row.record_slots
                    if isinstance(slot, dict) and isinstance(slot.get("slotId"), str)
                }
            except (KeyError, TypeError, ValueError):
                return InputCandidates(
                    input_id,
                    (),
                    "record slot value is invalid",
                    required=required,
                    mode=mode,
                    **definition,
                )
            candidates.append(
                Candidate(
                    ref,
                    lease,
                    value,
                    _lease_key(lease) not in active,
                    row.values_json,
                    record_slots,
                )
            )
        return InputCandidates(
            input_id,
            tuple(candidates),
            required=required,
            mode=mode,
            **definition,
        )


def _selection_definition(
    session: Session,
    project_id: str,
    item: dict[str, Any],
    definitions: dict[str, dict[str, Any]],
    target_field_types: dict[str, str],
) -> dict[str, Any] | str:
    mode = item["mode"]
    if mode == "independent":
        return {}
    if mode == "fixedRecord":
        try:
            fixed = _parse_record_ref(item["fixedRecord"])
        except (KeyError, TypeError, ValueError, ProjectError):
            return "fixed record reference is invalid"
        if (
            fixed.project_id != project_id
            or fixed.table_id != item["tableId"]
            or fixed.dataset_generation != item["datasetGeneration"]
        ):
            return "fixed record reference is outside this input"
        return {"fixed_record": fixed}

    relation = item.get("relation")
    if not isinstance(relation, dict):
        return "related input has no relation"
    source_id = relation.get("sourceInputId")
    if not isinstance(source_id, str):
        return "relation source is invalid"
    source = definitions.get(source_id)
    if source is None or source_id == item["inputId"]:
        return "relation source is invalid"
    kind = relation.get("type")
    if kind == "sameRecord":
        if (
            source.get("tableId"),
            source.get("datasetGeneration"),
        ) != (item["tableId"], item["datasetGeneration"]):
            return "same-record relation uses another table generation"
        return {"relation": SameRecordRelation(source_id)}
    if kind == "recordSlot":
        slot_id = relation.get("slotId")
        source_table = session.scalar(
            select(DataTableRow).where(
                DataTableRow.project_id == project_id,
                DataTableRow.id == source.get("tableId"),
                DataTableRow.current_generation == source.get("datasetGeneration"),
                DataTableRow.published.is_(True),
            )
        )
        if (
            not isinstance(slot_id, str)
            or source_table is None
            or not any(
                isinstance(slot, dict)
                and slot.get("slotId") == slot_id
                and slot.get("targetTableId") == item["tableId"]
                for slot in source_table.slot_definitions
            )
        ):
            return "record slot relation is invalid"
        return {"relation": RecordSlotRelation(source_id, slot_id)}
    if kind == "fieldEquals":
        source_ref, target_ref = relation.get("sourceFieldRef"), relation.get(
            "targetFieldRef"
        )
        if (
            not isinstance(source_ref, dict)
            or not isinstance(target_ref, dict)
            or not _field_ref_matches(source_ref, project_id, source)
            or not _field_ref_matches(target_ref, project_id, item)
        ):
            return "field relation reference is invalid"
        source_field_id = cast(str, source_ref["fieldId"])
        target_field_id = cast(str, target_ref["fieldId"])
        source_field = session.scalar(
            select(DataFieldRow).where(
                DataFieldRow.project_id == project_id,
                DataFieldRow.table_id == source["tableId"],
                DataFieldRow.dataset_generation == source["datasetGeneration"],
                DataFieldRow.id == source_field_id,
            )
        )
        target_type = target_field_types.get(target_field_id)
        if source_field is None or target_type is None or source_field.type != target_type:
            return "field relation types are incompatible"
        return {
            "relation": FieldEqualsRelation(
                source_id, source_field_id, target_field_id
            )
        }
    return "relation type is invalid"


def _field_ref_matches(
    value: Any, project_id: str, definition: dict[str, Any]
) -> bool:
    return isinstance(value, dict) and value == {
        "projectId": project_id,
        "tableId": definition.get("tableId"),
        "datasetGeneration": definition.get("datasetGeneration"),
        "fieldId": value.get("fieldId"),
    } and isinstance(value.get("fieldId"), str)


def _parse_record_ref(value: Any) -> RecordRef:
    if not isinstance(value, dict) or set(value) != {
        "projectId",
        "tableId",
        "datasetGeneration",
        "recordKey",
    }:
        raise ValueError("invalid record reference")
    key = value["recordKey"]
    if (
        not isinstance(key, dict)
        or set(key) != {"type", "value"}
        or key.get("type") not in {"text", "integer", "uuid"}
        or not isinstance(key.get("value"), str)
    ):
        raise ValueError("invalid record key")
    record_key = RecordKey(cast(RecordKeyType, key["type"]), key["value"])
    encode_record_key(record_key)
    if not all(isinstance(value.get(name), str) for name in ("projectId", "tableId", "datasetGeneration")):
        raise ValueError("invalid record scope")
    return RecordRef(
        value["projectId"], value["tableId"], value["datasetGeneration"], record_key
    )


def _snapshot_input(
    selected: SelectedInput, lease_id: str, captured_at: Any | None = None
) -> dict[str, Any]:
    return {
        "inputId": selected.input_id,
        "leaseId": lease_id,
        "unavailableReason": None,
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
