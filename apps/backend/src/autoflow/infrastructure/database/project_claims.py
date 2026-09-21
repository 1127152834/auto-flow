from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import Integer, and_, case, func, or_, select, text
from sqlalchemy import cast as sql_cast
from sqlalchemy.orm import Session

from autoflow.domain.project_data.identity import (
    RecordKey,
    RecordKeyType,
    encode_record_key,
)
from autoflow.domain.project_data.query import (
    MISSING,
    compare_values,
    compatible,
    date_value,
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
    SheetsLeaseKey,
    SourceLeaseKey,
    select_required_inputs,
)
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataGenerationRow,
    DataRecordRow,
    DataStatusRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectRecordLeaseRow,
    ProjectTaskRecordCursorRow,
)
from autoflow.infrastructure.database.project_sync_models import (
    SheetsBindingRow,
    SyncRecordMarkRow,
)


class SqlAlchemyProjectInputGroups:
    """Prepare input candidates and atomically revalidate selected records."""

    def __init__(self, session: Session):
        self.session = session

    def select_required(
        self,
        project_id: str,
        input_plan: dict[str, Any],
        *,
        candidate_offsets: dict[str, int] | None = None,
        candidate_restriction: dict[str, list[RecordRef]] | None = None,
    ) -> InputSelection:
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
        restriction = candidate_restriction or {}
        sources: list[InputCandidates] = []
        for item in raw_inputs:
            sources.append(
                self._candidates(
                    project_id,
                    item,
                    definitions,
                    offset=(candidate_offsets or {}).get(item["inputId"], 0),
                    restriction=restriction.get(item["inputId"]),
                )
            )
        selection = select_required_inputs(sources)
        return self.validate_relation_uniqueness(project_id, input_plan, selection)

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
        lease_rows: dict[SourceLeaseKey, ProjectRecordLeaseRow] = {}
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
                        "tableDisplay": table.name
                        if table is not None
                        else "数据表已失效",
                        "recordRef": None,
                        "values": [],
                        "unavailableReason": unavailable[input_id],
                        "capturedAt": now.isoformat(),
                    }
                )
        return snapshots

    def revalidate_selected(
        self,
        project_id: str,
        input_plan: dict[str, Any],
        prepared: InputSelection,
    ) -> InputSelection:
        """Recheck the exact prepared records without rescanning tables under a write lock."""
        raw_inputs = input_plan.get("inputs") if isinstance(input_plan, dict) else None
        if not isinstance(raw_inputs, list) or not all(
            isinstance(item, dict) for item in raw_inputs
        ):
            return InputSelection("configurationError")
        definitions = {
            item.get("inputId"): item
            for item in raw_inputs
            if isinstance(item.get("inputId"), str)
        }
        if len(definitions) != len(raw_inputs):
            return InputSelection("configurationError")
        selected = {item.input_id: item for item in prepared.inputs}
        sources = [
            self._candidates(
                project_id,
                item,
                definitions,
                exact_record_ref=(
                    selected[item["inputId"]].record_ref
                    if item["inputId"] in selected
                    else None
                ),
                omit_candidates=item["inputId"] not in selected,
            )
            for item in raw_inputs
        ]
        current = select_required_inputs(sources)
        if current.status != "ready":
            return current
        prepared_by_id = {item.input_id: item for item in prepared.inputs}
        changed = tuple(
            item.input_id
            for item in current.inputs
            if item.input_id not in prepared_by_id
            or item.lease_key != prepared_by_id[item.input_id].lease_key
            or any(
                item.value.get(name) != prepared_by_id[item.input_id].value.get(name)
                for name in (
                    "contentRevision",
                    "statusRevision",
                    "linkRevision",
                    "sourceIdentity",
                )
            )
        )
        if changed:
            return InputSelection(
                "temporarilyBusy",
                issue_input_ids=changed,
                issue_details=tuple(
                    (input_id, "record changed while the input group was prepared")
                    for input_id in changed
                ),
            )
        return current

    def validate_relation_uniqueness(
        self,
        project_id: str,
        input_plan: dict[str, Any],
        selection: InputSelection,
    ) -> InputSelection:
        """Check field-equality uniqueness across every physical candidate page."""
        if selection.status != "ready":
            return selection
        definitions: dict[str, dict[str, Any]] = {}
        for raw_item in input_plan.get("inputs", []):
            if isinstance(raw_item, dict) and isinstance(raw_item.get("inputId"), str):
                definitions[raw_item["inputId"]] = raw_item
        selected = {item.input_id: item for item in selection.inputs}
        for input_id, item in definitions.items():
            relation = item.get("relation")
            if not isinstance(relation, dict) or relation.get("type") != "fieldEquals":
                continue
            source_input_id = relation.get("sourceInputId")
            if not isinstance(source_input_id, str):
                continue
            source = selected.get(source_input_id)
            target = selected.get(input_id)
            source_ref = relation.get("sourceFieldRef")
            target_ref = relation.get("targetFieldRef")
            if (
                source is None
                or target is None
                or not isinstance(source_ref, dict)
                or not isinstance(target_ref, dict)
            ):
                continue
            expected = _selected_field_value(source, source_ref.get("fieldId"))
            target_field_id = target_ref.get("fieldId")
            if expected is MISSING or not isinstance(target_field_id, str):
                continue
            fields = list(
                self.session.scalars(
                    select(DataFieldRow).where(
                        DataFieldRow.project_id == project_id,
                        DataFieldRow.table_id == item.get("tableId"),
                        DataFieldRow.dataset_generation
                        == item.get("datasetGeneration"),
                    )
                )
            )
            field_types = {field.id: field.type for field in fields}
            statuses = set(
                self.session.scalars(
                    select(DataStatusRow.id).where(
                        DataStatusRow.project_id == project_id,
                        DataStatusRow.table_id == item.get("tableId"),
                        DataStatusRow.deleted.is_(False),
                    )
                )
            )
            filter_value = validate_filter(item.get("filter"), field_types, statuses)
            raw = cast(
                sqlite3.Connection,
                self.session.connection().connection.driver_connection,
            )

            def relation_match(
                values: str,
                status: str | None,
                selected_filter: dict[str, Any] = filter_value,
                selected_value: Any = expected,
                selected_field_id: str = target_field_id,
            ) -> int:
                decoded = json.loads(values)
                return int(
                    matches(selected_filter, decoded, status)
                    and _scalar_equal(
                        selected_value,
                        decoded.get(selected_field_id, MISSING),
                    )
                )

            try:
                raw.create_function("autoflow_claim_relation_match", 2, relation_match)
                matching = list(
                    self.session.scalars(
                        select(DataRecordRow)
                        .where(
                            DataRecordRow.project_id == project_id,
                            DataRecordRow.table_id == item.get("tableId"),
                            DataRecordRow.dataset_generation
                            == item.get("datasetGeneration"),
                            DataRecordRow.deleted.is_(False),
                            func.autoflow_claim_relation_match(
                                DataRecordRow.values_json,
                                DataRecordRow.status_id,
                            )
                            == 1,
                        )
                        .limit(2)
                    )
                )
            finally:
                raw.create_function("autoflow_claim_relation_match", 2, None)
            if len(matching) > 1:
                shown = ", ".join(f"{row.key_type}:{row.key_value}" for row in matching)
                return InputSelection(
                    "ambiguous",
                    issue_input_ids=(input_id,),
                    issue_details=(
                        (
                            input_id,
                            f"ambiguous value {expected!r}; records {shown}",
                        ),
                    ),
                    effective_required_input_ids=(
                        selection.effective_required_input_ids
                    ),
                )
        return selection

    def _candidates(
        self,
        project_id: str,
        item: dict[str, Any],
        definitions: dict[str, dict[str, Any]],
        *,
        offset: int = 0,
        exact_record_ref: RecordRef | None = None,
        omit_candidates: bool = False,
        restriction: list[RecordRef] | None = None,
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
        status_rows = list(
            self.session.scalars(
                select(DataStatusRow).where(
                    DataStatusRow.project_id == project_id,
                    DataStatusRow.table_id == table_id,
                    DataStatusRow.deleted.is_(False),
                )
            )
        )
        statuses = {row.id for row in status_rows}
        status_order = {row.id: (row.position, row.id) for row in status_rows}
        try:
            filter_value = validate_filter(item.get("filter"), field_types, statuses)
            order_value = validate_order(item.get("orderBy"), field_types)
        except ProjectError as error:  # validated management data may become stale
            return InputCandidates(
                input_id, (), str(error), required=required, mode=mode, **definition
            )
        if type(offset) is not int or offset < 0:
            return InputCandidates(
                input_id,
                (),
                "candidate cursor is invalid",
                required=required,
                mode=mode,
                **definition,
            )
        query = select(DataRecordRow).where(
            DataRecordRow.project_id == project_id,
            DataRecordRow.table_id == table_id,
            DataRecordRow.dataset_generation == generation,
            DataRecordRow.deleted.is_(False),
        )
        if exact_record_ref is not None:
            if (
                exact_record_ref.project_id != project_id
                or exact_record_ref.table_id != table_id
                or exact_record_ref.dataset_generation != generation
            ):
                rows = []
            else:
                rows = list(
                    self.session.scalars(
                        query.where(
                            DataRecordRow.key_type == exact_record_ref.record_key.type,
                            DataRecordRow.key_value
                            == exact_record_ref.record_key.value,
                        )
                    )
                )
        elif omit_candidates:
            rows = []
        elif restriction is not None:
            rows = _restricted_candidate_rows(
                self.session, project_id, table_id, generation, query, restriction
            )
        else:
            rows = _ordered_candidate_rows(
                self.session,
                query,
                order_value,
                field_types,
                status_order,
                offset,
            )
        has_more = (
            exact_record_ref is None
            and not omit_candidates
            and restriction is None
            and len(rows) > MAX_CANDIDATE_EVALUATIONS
        )
        rows = rows[:MAX_CANDIDATE_EVALUATIONS]
        rows = [
            row for row in rows if matches(filter_value, row.values_json, row.status_id)
        ]
        active = set(
            self.session.scalars(
                select(ProjectRecordLeaseRow.lease_key).where(
                    ProjectRecordLeaseRow.state.in_(("held", "reconciling")),
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
            try:
                lease, source_identity = resolve_record_lease(self.session, ref)
            except ProjectError as error:
                return InputCandidates(
                    input_id, (), str(error), required=required, mode=mode, **definition
                )
            value = {
                "alias": item.get("alias", input_id),
                "tableDisplay": table.name,
                "recordRef": _record_ref(ref),
                "fieldMappings": _mutable(item.get("fieldBindings", [])),
                "values": [
                    {
                        "fieldId": field.id,
                        "fieldName": field.name,
                        "value": row.values_json[field.id],
                    }
                    for field in fields
                    if field.id in row.values_json
                ],
                "statusId": row.status_id,
                "recordSlots": _mutable(row.record_slots),
                "currentEnvironmentId": row.current_environment_id,
                "sourceSummary": {"kind": table.source_kind, "name": table.name},
                **({"sourceIdentity": source_identity} if source_identity else {}),
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
                    _lease_key(lease) not in active and (
                        not isinstance(lease, SheetsLeaseKey)
                        or active_record_lease(self.session, project_id, table_id, generation, ref.record_key) is None
                    ),
                    row.values_json,
                    record_slots,
                )
            )
        return InputCandidates(
            input_id,
            tuple(candidates),
            required=required,
            mode=mode,
            scan_budget_exceeded=has_more,
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
        source_ref, target_ref = (
            relation.get("sourceFieldRef"),
            relation.get("targetFieldRef"),
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
        if (
            source_field is None
            or target_type is None
            or source_field.type != target_type
        ):
            return "field relation types are incompatible"
        return {
            "relation": FieldEqualsRelation(source_id, source_field_id, target_field_id)
        }
    return "relation type is invalid"


def _field_ref_matches(value: Any, project_id: str, definition: dict[str, Any]) -> bool:
    return (
        isinstance(value, dict)
        and value
        == {
            "projectId": project_id,
            "tableId": definition.get("tableId"),
            "datasetGeneration": definition.get("datasetGeneration"),
            "fieldId": value.get("fieldId"),
        }
        and isinstance(value.get("fieldId"), str)
    )


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
    if not all(
        isinstance(value.get(name), str)
        for name in ("projectId", "tableId", "datasetGeneration")
    ):
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


def resolve_record_lease(
    session: Session, ref: RecordRef
) -> tuple[SourceLeaseKey, dict[str, Any]]:
    """Keep local permissions/cursors separate from physical source exclusion."""
    table = session.get(DataTableRow, ref.table_id)
    if (
        table is None
        or table.project_id != ref.project_id
        or table.current_generation != ref.dataset_generation
    ):
        raise ProjectError("DATASET_GENERATION_GONE", "Dataset identity changed", 410)
    if table.source_kind != "sheets":
        return LeaseKey(
            "local",
            ref.project_id,
            ref.table_id,
            ref.dataset_generation,
            ref.record_key,
        ), {}
    binding = session.get(SheetsBindingRow, ref.table_id)
    proof = binding.identity_verification if binding is not None else None
    if (
        binding is None
        or not proof
        or not proof.get("valid")
        or proof.get("bindingEpoch") != binding.binding_epoch
        or proof.get("datasetGeneration") != ref.dataset_generation
    ):
        raise ProjectError(
            "SHEETS_IDENTITY_UNVERIFIED",
            "来源身份尚未完整验证，请修复后重新拉取。",
            409,
        )
    peers = session.scalars(
        select(SheetsBindingRow).where(
            SheetsBindingRow.spreadsheet_id == binding.spreadsheet_id,
            SheetsBindingRow.sheet_id == binding.sheet_id,
        )
    ).all()
    for peer in peers:
        if peer.identity_strategy != binding.identity_strategy or (
            peer.identity_verification
            and (
                not peer.identity_verification.get("valid")
                or peer.identity_verification.get("namespace") != proof["namespace"]
                or peer.identity_verification.get("revision") != proof["revision"]
            )
        ):
            raise ProjectError(
                "SHEETS_IDENTITY_UNVERIFIED",
                "同一来源存在未经证明相同的身份列，请修复绑定。",
                409,
            )
    mark = session.get(
        SyncRecordMarkRow, (ref.table_id, ref.record_key.type, ref.record_key.value)
    )
    evidence = (mark.observed or {}).get("identity", {}) if mark else {}
    if (
        mark is None
        or mark.remote_missing
        or evidence.get("revision") != proof["revision"]
        or evidence.get("bindingEpoch") != binding.binding_epoch
        or evidence.get("datasetGeneration") != ref.dataset_generation
    ):
        raise ProjectError(
            "SHEETS_IDENTITY_UNVERIFIED",
            "该记录不在最近完整验证的来源中，请修复后重新拉取。",
            409,
        )
    key = SheetsLeaseKey(
        binding.spreadsheet_id, binding.sheet_id, proof["namespace"], ref.record_key
    )
    return key, {
        "bindingEpoch": binding.binding_epoch,
        "verificationRevision": proof["revision"],
        "leaseKey": _lease_key(key),
    }


def source_record_leases(session: Session, spreadsheet_id: str, sheet_id: int) -> list[ProjectRecordLeaseRow]:
    """Public locks plus conservative legacy locks whose source identity is incomplete."""
    key = ProjectRecordLeaseRow.lease_key
    return list(session.scalars(select(ProjectRecordLeaseRow).outerjoin(
        DataGenerationRow,
        DataGenerationRow.id == ProjectRecordLeaseRow.record_ref["datasetGeneration"].as_string(),
    ).where(
        ProjectRecordLeaseRow.state.in_(("held", "reconciling")),
        or_(
            and_(func.json_extract(key, "$.source") == "sheets",
                 func.json_extract(key, "$.spreadsheetId") == spreadsheet_id,
                 func.json_extract(key, "$.sheetId") == sheet_id),
            and_(func.json_extract(key, "$.source") == "local",
                 DataGenerationRow.source["kind"].as_string() == "sheets",
                 DataGenerationRow.source["spreadsheetId"].as_string() == spreadsheet_id),
        ),
    )))


def active_record_lease(
    session: Session,
    project_id: str,
    table_id: str,
    dataset_generation: str,
    record_key: RecordKey,
) -> ProjectRecordLeaseRow | None:
    binding = session.get(SheetsBindingRow, table_id)
    if binding is not None and binding.project_id == project_id:
        for lease in source_record_leases(session, binding.spreadsheet_id, binding.sheet_id):
            source = json.loads(lease.lease_key)
            if source["source"] == "local" or source.get("recordKey") == {"type": record_key.type, "value": record_key.value}:
                return lease
        return None
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


def _selected_field_value(selected: SelectedInput, field_id: Any) -> Any:
    if not isinstance(field_id, str):
        return MISSING
    values = selected.value.get("values")
    if not isinstance(values, tuple | list):
        return MISSING
    for item in values:
        if (
            isinstance(item, Mapping)
            and item.get("fieldId") == field_id
            and "value" in item
        ):
            return item["value"]
    return MISSING


def _scalar_equal(left: Any, right: Any) -> bool:
    if left is MISSING or right is MISSING or left is None or right is None:
        return False
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, int | float) and isinstance(right, int | float):
        return left == right
    return type(left) is type(right) and left == right


def _record_ref(value: RecordRef) -> dict[str, Any]:
    return {
        "projectId": value.project_id,
        "tableId": value.table_id,
        "datasetGeneration": value.dataset_generation,
        "recordKey": {"type": value.record_key.type, "value": value.record_key.value},
    }


def _lease_key(value: SourceLeaseKey) -> str:
    if isinstance(value, SheetsLeaseKey):
        return json.dumps(
            {
                "source": "sheets",
                "spreadsheetId": value.spreadsheet_id,
                "sheetId": value.sheet_id,
                "identityNamespace": value.identity_namespace,
                "recordKey": {
                    "type": value.record_key.type,
                    "value": value.record_key.value,
                },
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    return json.dumps(
        {
            "source": value.source,
            **_record_ref(
                RecordRef(
                    value.project_id,
                    value.table_id,
                    value.dataset_generation,
                    value.record_key,
                )
            ),
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _restricted_candidate_rows(
    session: Session,
    project_id: str,
    table_id: str,
    generation: str,
    query: Any,
    restriction: list[RecordRef],
) -> list[DataRecordRow]:
    """Pinned candidate set of a follow-up Batch; never widens beyond it."""
    pairs = sorted(
        {
            (ref.record_key.type, ref.record_key.value)
            for ref in restriction
            if ref.project_id == project_id
            and ref.table_id == table_id
            and ref.dataset_generation == generation
        }
    )
    if not pairs:
        return []
    return list(
        session.scalars(
            query.where(
                or_(
                    *(
                        and_(
                            DataRecordRow.key_type == key_type,
                            DataRecordRow.key_value == key_value,
                        )
                        for key_type, key_value in pairs
                    )
                )
            ).order_by(DataRecordRow.created_at, DataRecordRow.key_value)
        )
    )


def _ordered_candidate_rows(
    session: Session,
    query: Any,
    order: list[dict[str, str]],
    field_types: dict[str, str],
    status_order: dict[str, tuple[int, str]],
    offset: int,
) -> list[DataRecordRow]:
    """Apply the same domain ordering before cutting a bounded candidate page."""
    statement = query
    raw = cast(
        sqlite3.Connection,
        session.connection().connection.driver_connection,
    )
    try:
        if order:
            field_targets = [item["fieldId"] for item in order if "fieldId" in item]

            def projection(
                values: str,
                status: str | None,
                created: str,
                updated: str,
                key_type: str,
                key_value: str,
            ) -> str:
                decoded = json.loads(values)
                return json.dumps(
                    [
                        {key: decoded.get(key) for key in field_targets},
                        status,
                        created,
                        updated,
                        key_type,
                        key_value,
                    ],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

            raw.create_function("autoflow_claim_sort", 6, projection)
            raw.create_collation(
                "AUTOFLOW_CLAIM",
                _claim_collation(order, field_types, status_order),
            )
            statement = statement.order_by(
                text(
                    "autoflow_claim_sort(values_json,status_id,created_at,updated_at,"
                    "key_type,key_value) COLLATE AUTOFLOW_CLAIM"
                )
            )
        else:
            rank = case(
                (DataRecordRow.key_type == "text", 0),
                (DataRecordRow.key_type == "integer", 1),
                else_=2,
            )
            statement = statement.order_by(
                rank,
                case(
                    (
                        DataRecordRow.key_type == "integer",
                        sql_cast(DataRecordRow.key_value, Integer),
                    ),
                    else_=None,
                ),
                DataRecordRow.key_value,
            )
        return list(
            session.scalars(
                statement.offset(offset).limit(MAX_CANDIDATE_EVALUATIONS + 1)
            )
        )
    finally:
        raw.create_function("autoflow_claim_sort", 6, None)
        raw.create_collation("AUTOFLOW_CLAIM", None)


def _claim_collation(
    order: list[dict[str, str]],
    field_types: dict[str, str],
    status_order: dict[str, tuple[int, str]],
) -> Callable[[str, str], int]:
    def compare(left_text: str, right_text: str) -> int:
        left, right = json.loads(left_text), json.loads(right_text)
        for item in order:
            if "fieldId" in item:
                field_id = item["fieldId"]
                left_value = left[0].get(field_id, MISSING)
                right_value = right[0].get(field_id, MISSING)
                if (left_value is MISSING or left_value is None) != (
                    right_value is MISSING or right_value is None
                ):
                    return 1 if left_value is MISSING or left_value is None else -1
                left_valid = compatible(field_types[field_id], left_value)
                right_valid = compatible(field_types[field_id], right_value)
                if left_valid != right_valid:
                    return -1 if left_valid else 1
                if field_types[field_id] == "date":
                    left_date = date_value(left_value)
                    right_date = date_value(right_value)
                    if (left_date is None) != (right_date is None):
                        return 1 if left_date is None else -1
                    if (
                        left_date is not None
                        and right_date is not None
                        and left_date[0] != right_date[0]
                    ):
                        return (left_date[0] > right_date[0]) - (
                            left_date[0] < right_date[0]
                        )
                result = _claim_sort_value(
                    field_types[field_id], left_value, right_value
                )
            else:
                target = item["systemField"]
                if target == "status":
                    left_status = status_order.get(left[1], MISSING)
                    right_status = status_order.get(right[1], MISSING)
                    if (left_status is MISSING) != (right_status is MISSING):
                        return 1 if left_status is MISSING else -1
                    result = _nullable_compare(left_status, right_status)
                elif target in {"createdAt", "updatedAt"}:
                    result = _nullable_compare(
                        left[2 if target == "createdAt" else 3],
                        right[2 if target == "createdAt" else 3],
                    )
                else:
                    result = _record_key_compare(left[4], left[5], right[4], right[5])
            if result:
                return result if item["direction"] == "asc" else -result
        return _record_key_compare(left[4], left[5], right[4], right[5])

    return compare


def _claim_sort_value(kind: str, left: Any, right: Any) -> int:
    if left is MISSING or left is None or right is MISSING or right is None:
        return _nullable_compare(left, right)
    if kind == "date":
        left_date, right_date = date_value(left), date_value(right)
        if left_date is None or right_date is None:
            return _nullable_compare(left_date, right_date)
        return (left_date > right_date) - (left_date < right_date)
    result = compare_values(kind, left, right)
    return (
        _nullable_compare(
            None if result is None else left,
            None if result is None else right,
        )
        if result is None
        else result
    )


def _nullable_compare(left: Any, right: Any) -> int:
    left_null = left is MISSING or left is None
    right_null = right is MISSING or right is None
    if left_null or right_null:
        return (1 if left_null else -1) if left_null != right_null else 0
    return (left > right) - (left < right)


def _record_key_compare(lt: str, lv: str, rt: str, rv: str) -> int:
    ranks = {"text": 0, "integer": 1, "uuid": 2}
    if lt != rt:
        return (ranks[lt] > ranks[rt]) - (ranks[lt] < ranks[rt])
    if lt == "integer":
        return (int(lv) > int(rv)) - (int(lv) < int(rv))
    return (lv > rv) - (lv < rv)
