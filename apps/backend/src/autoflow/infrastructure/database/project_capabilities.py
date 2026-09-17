from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from functools import cmp_to_key
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.capabilities import (
    AddProjectFieldCommand,
    CreateProjectRecordCommand,
    DeleteProjectRecordCommand,
    EnsureProjectFieldCommand,
    ModifyProjectFieldCommand,
    PreviewProjectFieldChangeRequest,
    QueryProjectRecordsRequest,
    ReadProjectRecordRequest,
    RecordReadGrant,
    RecordWriteGrant,
    SetRecordStatusCommand,
    TableCapabilityGrant,
    TaskCapabilityScope,
    UpdateProjectRecordCommand,
)
from autoflow.domain.project_data.identity import (
    RecordKey,
    record_key,
    system_record_key,
)
from autoflow.domain.project_data.query import (
    MISSING,
    compare_values,
    matches,
    validate_filter,
    validate_order,
)
from autoflow.domain.project_data.schema import (
    SchemaBackfillLimit,
    backfill_budget,
    canonical_bytes,
)
from autoflow.domain.project_runs.input_selection import (
    MAX_CANDIDATE_EVALUATIONS,
    LeaseKey,
    RecordRef,
)
from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_claims import _lease_key
from autoflow.infrastructure.database.project_data import (
    _operation_result,
    _operation_row,
)
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_catalog import (
    _field as _catalog_field,
)
from autoflow.infrastructure.database.project_data_deletions import (
    SqlAlchemyProjectDataDeletions,
)
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataFieldRow,
    DataRecordRow,
    DataStatusRow,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectRecordLeaseRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRecordCursorRow,
    ProjectTaskRecordQueryItemRow,
    ProjectTaskRecordQueryRow,
    ProjectTaskRecordReadRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow

MAX_QUERY_SNAPSHOT_RECORDS = MAX_CANDIDATE_EVALUATIONS
MAX_QUERY_SNAPSHOT_BYTES = 4 * 1024 * 1024


class SqlAlchemyProjectDataCapabilities:
    """Execute one explicit data mutation per short, fenced transaction."""

    def __init__(self, factory: sessionmaker[Session]):
        self._factory = factory

    def scope(
        self,
        project_id: str,
        task_id: str,
        run_id: str,
    ) -> TaskCapabilityScope:
        with self._factory() as session:
            task, run, snapshot = self._facts(session, project_id, task_id, run_id)
            del task
            binding = next(
                (
                    item
                    for item in run.capability_bindings
                    if item.get("capability") == "project.data"
                    and item.get("projectId") == project_id
                    and item.get("taskId") == task_id
                    and item.get("executionGeneration") == run.execution_generation
                ),
                None,
            )
            if binding is None:
                raise ProjectError(
                    "CAPABILITY_SCOPE_DENIED",
                    "Project data capability was not granted to this run",
                    403,
                )
            raw_status_inputs = binding.get("statusInputIds")
            if not isinstance(raw_status_inputs, list) or any(
                not isinstance(item, str) for item in raw_status_inputs
            ):
                raise ProjectError(
                    "CAPABILITY_FACTS_INCOMPLETE",
                    "Project data status targets are invalid",
                    409,
                )
            allowed_status_inputs = set(raw_status_inputs)
            refs = frozenset(
                _ref(item["recordRef"])
                for item in snapshot.inputs
                if item.get("inputId") in allowed_status_inputs
            )
            if len(refs) != len(allowed_status_inputs):
                raise ProjectError(
                    "CAPABILITY_FACTS_INCOMPLETE",
                    "Project data status targets are missing from the input snapshot",
                    409,
                )
            raw_targets = binding.get("createRecordTargets")
            if not isinstance(raw_targets, list):
                raise ProjectError(
                    "CAPABILITY_FACTS_INCOMPLETE",
                    "Project data capability targets are missing",
                    409,
                )
            validated_targets: set[tuple[str, str]] = set()
            for item in raw_targets:
                table_id = item.get("tableId") if isinstance(item, dict) else None
                generation = (
                    item.get("datasetGeneration") if isinstance(item, dict) else None
                )
                if not isinstance(table_id, str) or not isinstance(generation, str):
                    raise ProjectError(
                        "CAPABILITY_FACTS_INCOMPLETE",
                        "Project data capability targets are invalid",
                        409,
                    )
                validated_targets.add((table_id, generation))
            create_record_targets = frozenset(validated_targets)
            for table_id, generation in create_record_targets:
                SqlAlchemyProjectDataRecords._table(
                    session, project_id, table_id, generation, False
                )
            read_grants: set[RecordReadGrant] = set()
            write_grants: set[RecordWriteGrant] = set()
            for item in snapshot.inputs:
                payload = item.get("recordRef")
                if not isinstance(payload, dict):
                    continue
                ref = _ref(payload)
                field_ids = frozenset(
                    value["fieldId"]
                    for value in item.get("values", [])
                    if isinstance(value, dict) and isinstance(value.get("fieldId"), str)
                )
                read_grants.add(
                    RecordReadGrant(ref, field_ids, frozenset({"workflow", "input"}))
                )
                operations: set[str] = set()
                input_id = item.get("inputId")
                if input_id in allowed_status_inputs:
                    operations.add("setRecordStatus")
                if operations:
                    write_grants.add(
                        RecordWriteGrant(ref, frozenset(operations), field_ids)
                    )
            raw_table_grants = binding.get("tableGrants", [])
            if not isinstance(raw_table_grants, list):
                raise ProjectError(
                    "CAPABILITY_FACTS_INCOMPLETE",
                    "Project data table grants are invalid",
                    409,
                )
            table_grants: set[TableCapabilityGrant] = set()
            try:
                for item in raw_table_grants:
                    if not isinstance(item, dict):
                        raise TypeError
                    table_grants.add(
                        TableCapabilityGrant(
                            item["tableId"],
                            item["datasetGeneration"],
                            frozenset(item["operations"]),
                            frozenset(item.get("fieldIds", [])),
                            frozenset(item.get("readPurposes", [])),
                        )
                    )
            except (KeyError, TypeError, ValueError, ProjectError) as error:
                raise ProjectError(
                    "CAPABILITY_FACTS_INCOMPLETE",
                    "Project data table grants are invalid",
                    409,
                ) from error
            return TaskCapabilityScope(
                project_id,
                task_id,
                run_id,
                run.execution_generation,
                refs,
                create_record_targets,
                frozenset(read_grants),
                frozenset(write_grants),
                frozenset(table_grants),
            )

    def read_record(
        self, scope: TaskCapabilityScope, request: ReadProjectRecordRequest
    ) -> dict:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            _task, run, _snapshot = self._facts(
                session, scope.project_id, scope.task_id, scope.run_id
            )
            scope.authorize_read_record(
                request, current_execution_generation=run.execution_generation
            )
            records = SqlAlchemyProjectDataRecords(self._factory)
            table = records._table(
                session,
                scope.project_id,
                request.record_ref.table_id,
                request.record_ref.dataset_generation,
                False,
            )
            fields = records._fields(session, table)
            row = records._required_record(
                session,
                scope.project_id,
                request.record_ref.table_id,
                request.record_ref.dataset_generation,
                request.record_ref.record_key,
            )
            field_ids = tuple(request.field_ids)
            value = _projected_snapshot(records._snapshot(row, fields), field_ids)
            self._record_read(session, scope, request.read_purpose, field_ids, value)
            self._commit(session)
            return value

    def query_records(
        self, scope: TaskCapabilityScope, request: QueryProjectRecordsRequest
    ) -> dict:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            _task, run, _snapshot = self._facts(
                session, scope.project_id, scope.task_id, scope.run_id
            )
            scope.authorize_query_records(
                request, current_execution_generation=run.execution_generation
            )
            records = SqlAlchemyProjectDataRecords(self._factory)
            table = records._table(
                session,
                scope.project_id,
                request.table_id,
                request.dataset_generation,
                False,
            )
            fields = records._fields(session, table)
            payload = request.request_payload
            shape_digest = _query_shape_digest(scope, payload)
            decoded = _decode_cursor(request.cursor, shape_digest)
            if decoded is None:
                field_types = {field.id: field.type for field in fields}
                statuses = set(
                    session.scalars(
                        select(DataStatusRow.id).where(
                            DataStatusRow.project_id == scope.project_id,
                            DataStatusRow.table_id == request.table_id,
                            DataStatusRow.deleted.is_(False),
                        )
                    )
                )
                filter_value = validate_filter(
                    payload["filter"] or {"type": "all", "items": []},
                    field_types,
                    statuses,
                )
                order_value = validate_order(payload["orderBy"], field_types)
                scanned_count = (
                    session.scalar(
                        select(func.count())
                        .select_from(DataRecordRow)
                        .where(
                            DataRecordRow.project_id == scope.project_id,
                            DataRecordRow.table_id == request.table_id,
                            DataRecordRow.dataset_generation
                            == request.dataset_generation,
                            DataRecordRow.deleted.is_(False),
                        )
                    )
                    or 0
                )
                if scanned_count > MAX_QUERY_SNAPSHOT_RECORDS:
                    raise _query_snapshot_budget_error("recordCount", scanned_count, 0)
                rows = list(
                    session.scalars(
                        select(DataRecordRow).where(
                            DataRecordRow.project_id == scope.project_id,
                            DataRecordRow.table_id == request.table_id,
                            DataRecordRow.dataset_generation
                            == request.dataset_generation,
                            DataRecordRow.deleted.is_(False),
                        )
                    )
                )
                rows = [
                    row
                    for row in rows
                    if matches(filter_value, row.values_json, row.status_id)
                ]
                rows.sort(
                    key=cmp_to_key(
                        lambda left, right: _compare_records(
                            left, right, order_value, field_types
                        )
                    )
                )
                query_id, offset = str(uuid4()), 0
                field_ids = tuple(request.field_ids)
                snapshots: list[dict] = []
                snapshot_bytes = 0
                for row in rows:
                    snapshot = _projected_snapshot(
                        records._snapshot(row, fields), field_ids
                    )
                    snapshot_bytes += len(canonical_bytes(snapshot))
                    if snapshot_bytes > MAX_QUERY_SNAPSHOT_BYTES:
                        raise _query_snapshot_budget_error(
                            "snapshotBytes", scanned_count, snapshot_bytes
                        )
                    snapshots.append(snapshot)
                session.add(
                    ProjectTaskRecordQueryRow(
                        id=query_id,
                        project_id=scope.project_id,
                        task_id=scope.task_id,
                        run_id=scope.run_id,
                        execution_generation=scope.execution_generation,
                        table_id=request.table_id,
                        dataset_generation=request.dataset_generation,
                        request_digest=shape_digest,
                        request_payload=payload | {"cursor": None},
                        result_count=len(snapshots),
                        created_at=datetime.now(UTC),
                    )
                )
                session.flush()
                session.add_all(
                    ProjectTaskRecordQueryItemRow(
                        query_id=query_id,
                        ordinal=ordinal,
                        snapshot=snapshot,
                    )
                    for ordinal, snapshot in enumerate(snapshots)
                )
                total = len(snapshots)
            else:
                query_id, offset = decoded
                query = session.get(ProjectTaskRecordQueryRow, query_id)
                if query is None or not _query_snapshot_matches(
                    query, scope, request, shape_digest
                ):
                    raise _invalid_query_cursor()
                if offset > query.result_count:
                    raise _invalid_query_cursor()
                snapshots = list(
                    session.scalars(
                        select(ProjectTaskRecordQueryItemRow.snapshot)
                        .where(
                            ProjectTaskRecordQueryItemRow.query_id == query_id,
                            ProjectTaskRecordQueryItemRow.ordinal >= offset,
                        )
                        .order_by(ProjectTaskRecordQueryItemRow.ordinal)
                        .limit(request.limit)
                    )
                )
                total = query.result_count
            items = (
                snapshots[offset : offset + request.limit]
                if decoded is None
                else snapshots
            )
            field_ids = tuple(request.field_ids)
            for item in items:
                self._record_read(
                    session,
                    scope,
                    request.read_purpose,
                    field_ids,
                    item,
                )
            next_offset = offset + len(items)
            result = {
                "items": items,
                "nextCursor": (
                    _encode_cursor(query_id, next_offset, shape_digest)
                    if next_offset < total
                    else None
                ),
                "hasMore": next_offset < total,
            }
            self._commit(session)
            return result

    def set_record_status(
        self, scope: TaskCapabilityScope, command: SetRecordStatusCommand
    ) -> tuple[dict, bool]:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            task, run, _snapshot = self._facts(
                session, scope.project_id, scope.task_id, scope.run_id
            )
            existing = self._existing(
                session,
                scope,
                "setRecordStatus",
                command.operation_id,
                command.request_digest,
            )
            if existing is not None:
                session.rollback()
                return _operation_result(existing), True
            lease_mode = scope.authorize_set_status(
                command, current_execution_generation=run.execution_generation
            )
            row = SqlAlchemyProjectDataRecords._required_record(
                SqlAlchemyProjectDataRecords(self._factory),
                session,
                command.record_ref.project_id,
                command.record_ref.table_id,
                command.record_ref.dataset_generation,
                command.record_ref.record_key,
            )
            lease, cursor = self._write_cursor(
                session,
                scope,
                task,
                command.record_ref,
                row,
                lease_mode,
                expected_content=command.expected_content_revision_when_derived,
                expected_status=command.expected_status_revision,
            )
            if (
                row.status_revision != command.expected_status_revision
                or cursor.status_revision != command.expected_status_revision
            ):
                raise _revision_conflict(
                    command.expected_status_revision, row.status_revision
                )
            if command.expected_content_revision_when_derived is not None and (
                row.content_revision != command.expected_content_revision_when_derived
                or cursor.content_revision
                != command.expected_content_revision_when_derived
            ):
                raise _content_revision_conflict(
                    command.expected_content_revision_when_derived,
                    row.content_revision,
                )
            if (
                command.allowed_from is not None
                and row.status_id not in command.allowed_from
            ):
                raise ProjectError(
                    "STATUS_PRECONDITION_FAILED",
                    "Record status changed",
                    409,
                    {
                        "allowedFrom": list(command.allowed_from),
                        "currentStatusId": row.status_id,
                        "retryable": False,
                    },
                )
            if (
                command.status_id is not None
                and session.scalar(
                    select(DataStatusRow.id).where(
                        DataStatusRow.project_id == scope.project_id,
                        DataStatusRow.table_id == command.record_ref.table_id,
                        DataStatusRow.id == command.status_id,
                        DataStatusRow.deleted.is_(False),
                    )
                )
                is None
            ):
                raise ProjectError("STATUS_NOT_FOUND", "Status was not found", 404)
            fields = SqlAlchemyProjectDataRecords._fields(
                session,
                SqlAlchemyProjectDataRecords._table(
                    session,
                    scope.project_id,
                    command.record_ref.table_id,
                    command.record_ref.dataset_generation,
                    True,
                ),
            )
            before = SqlAlchemyProjectDataRecords._snapshot(row, fields)
            changed = command.status_id is None or command.status_id != row.status_id
            if changed:
                row.status_id = command.status_id
                row.status_revision += 1
                row.updated_at = datetime.now(UTC)
                cursor.status_revision = row.status_revision
                cursor.updated_at = row.updated_at
                lease.updated_at = row.updated_at
            after = SqlAlchemyProjectDataRecords._snapshot(row, fields)
            operation = _completed_operation(
                scope,
                command.operation_id,
                "setRecordStatus",
                command.request_digest,
                after,
            )
            session.add(_operation_row(operation))
            session.flush()
            if changed:
                session.add(_change(operation, before, after))
            self._commit(session)
            return after, False

    def update_record(
        self, scope: TaskCapabilityScope, command: UpdateProjectRecordCommand
    ) -> tuple[dict, bool]:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            task, run, _snapshot = self._facts(
                session, scope.project_id, scope.task_id, scope.run_id
            )
            existing = self._existing(
                session,
                scope,
                "updateRecord",
                command.operation_id,
                command.request_digest,
            )
            if existing is not None:
                session.rollback()
                return _operation_result(existing), True
            lease_mode = scope.authorize_update_record(
                command, current_execution_generation=run.execution_generation
            )
            records = SqlAlchemyProjectDataRecords(self._factory)
            table = records._table(
                session,
                scope.project_id,
                command.record_ref.table_id,
                command.record_ref.dataset_generation,
                True,
            )
            fields = records._fields(session, table)
            row = records._required_record(
                session,
                scope.project_id,
                command.record_ref.table_id,
                command.record_ref.dataset_generation,
                command.record_ref.record_key,
            )
            lease, cursor = self._write_cursor(
                session,
                scope,
                task,
                command.record_ref,
                row,
                lease_mode,
                expected_content=command.expected_content_revision,
            )
            if (
                row.content_revision != command.expected_content_revision
                or cursor.content_revision != command.expected_content_revision
            ):
                raise _content_revision_conflict(
                    command.expected_content_revision, row.content_revision
                )
            identity_id = (
                table.identity.get("fieldId")
                if table.identity.get("mode") == "field"
                else None
            )
            if identity_id in command.changes:
                raise ProjectError(
                    "IDENTITY_FIELD_IMMUTABLE",
                    "Identity field cannot be changed",
                    422,
                )
            canonical = records._validate(fields, dict(command.changes), False)
            before = records._snapshot(row, fields)
            merged = {**row.values_json, **canonical}
            if merged != row.values_json:
                row.values_json = merged
                row.content_revision += 1
                row.updated_at = datetime.now(UTC)
                cursor.content_revision = row.content_revision
                cursor.updated_at = row.updated_at
                lease.updated_at = row.updated_at
            after = records._snapshot(row, fields)
            operation = _completed_operation(
                scope,
                command.operation_id,
                "updateRecord",
                command.request_digest,
                after,
            )
            session.add(_operation_row(operation))
            session.flush()
            if before != after:
                session.add(_change(operation, before, after))
            self._commit(session)
            return after, False

    def delete_record(
        self, scope: TaskCapabilityScope, command: DeleteProjectRecordCommand
    ) -> tuple[dict, bool]:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            task, run, _snapshot = self._facts(
                session, scope.project_id, scope.task_id, scope.run_id
            )
            existing = self._existing(
                session,
                scope,
                "deleteRecord",
                command.operation_id,
                command.request_digest,
            )
            if existing is not None:
                session.rollback()
                return _operation_result(existing), True
            lease_mode = scope.authorize_delete_record(
                command, current_execution_generation=run.execution_generation
            )
            records = SqlAlchemyProjectDataRecords(self._factory)
            table = records._table(
                session,
                scope.project_id,
                command.record_ref.table_id,
                command.record_ref.dataset_generation,
                True,
            )
            fields = records._fields(session, table)
            row = records._required_record(
                session,
                scope.project_id,
                command.record_ref.table_id,
                command.record_ref.dataset_generation,
                command.record_ref.record_key,
            )
            report, _facts = SqlAlchemyProjectDataDeletions(
                self._factory
            )._record_facts(
                session,
                scope.project_id,
                command.record_ref.table_id,
                command.record_ref.dataset_generation,
                command.record_ref.record_key,
                True,
            )
            if report["blockers"]:
                blocker = report["blockers"][0]
                raise ProjectError(
                    blocker["code"],
                    blocker["message"],
                    409,
                    {"blockers": report["blockers"], "retryable": False},
                )
            lease, cursor = self._write_cursor(
                session,
                scope,
                task,
                command.record_ref,
                row,
                lease_mode,
                expected_content=command.expected_content_revision,
                expected_status=command.expected_status_revision,
                expected_link=command.expected_link_revision,
            )
            current = (
                row.content_revision,
                row.status_revision,
                row.link_revision,
            )
            expected = (
                command.expected_content_revision,
                command.expected_status_revision,
                command.expected_link_revision,
            )
            cursor_versions = (
                cursor.content_revision,
                cursor.status_revision,
                cursor.link_revision,
            )
            if current != expected or cursor_versions != expected:
                raise ProjectError(
                    "REVISION_CONFLICT",
                    "Record was modified",
                    409,
                    {"expectedRevisions": expected, "currentRevisions": current},
                )
            before = records._snapshot(row, fields)
            row.deleted = True
            row.updated_at = datetime.now(UTC)
            after = records._snapshot(row, fields)
            operation = _completed_operation(
                scope,
                command.operation_id,
                "deleteRecord",
                command.request_digest,
                {
                    "target": {"type": "record", "recordRef": before["ref"]},
                    "deleted": True,
                },
            )
            session.add(_operation_row(operation))
            session.flush()
            session.add(_change(operation, before, after))
            lease.updated_at = cursor.updated_at = row.updated_at
            self._commit(session)
            return operation.result or {}, False

    def create_record(
        self, scope: TaskCapabilityScope, command: CreateProjectRecordCommand
    ) -> tuple[dict, bool]:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            task, run, _snapshot = self._facts(
                session, scope.project_id, scope.task_id, scope.run_id
            )
            existing = self._existing(
                session,
                scope,
                "createRecord",
                command.operation_id,
                command.request_digest,
            )
            if existing is not None:
                session.rollback()
                return _operation_result(existing), True
            scope.authorize_create_record(
                command, current_execution_generation=run.execution_generation
            )
            records = SqlAlchemyProjectDataRecords(self._factory)
            table = records._table(
                session,
                command.project_id,
                command.table_id,
                command.dataset_generation,
                True,
            )
            fields = records._fields(session, table)
            canonical = records._validate(fields, dict(command.values), True)
            identity = table.identity
            if identity.get("mode") == "system":
                key = system_record_key()
            else:
                identity_field_id = identity.get("fieldId")
                if not isinstance(identity_field_id, str):
                    raise ProjectError(
                        "INVALID_PROJECT_DATA", "Invalid table identity", 422
                    )
                key = record_key(canonical.get(identity_field_id))
            now = datetime.now(UTC)
            row = DataRecordRow(
                project_id=command.project_id,
                table_id=command.table_id,
                dataset_generation=command.dataset_generation,
                key_type=key.type,
                key_value=key.value,
                values_json=canonical,
                record_slots=[],
                status_id=None,
                current_environment_id=None,
                content_revision=1,
                status_revision=1,
                link_revision=1,
                deleted=False,
                created_at=now,
                updated_at=now,
            )
            after = records._snapshot(row, fields)
            operation = _completed_operation(
                scope,
                command.operation_id,
                "createRecord",
                command.request_digest,
                after,
            )
            try:
                session.add(row)
                session.add(_operation_row(operation))
                session.flush()
                self._new_lease_cursor(
                    session,
                    scope,
                    task,
                    command.table_id,
                    command.dataset_generation,
                    key,
                    row,
                    "createdRecord",
                )
                session.add(_change(operation, None, after))
                self._commit(session)
            except IntegrityError as error:
                session.rollback()
                raise ProjectError(
                    "RECORD_ALREADY_EXISTS", "Record already exists", 409
                ) from error
            return after, False

    def add_field(
        self, scope: TaskCapabilityScope, command: AddProjectFieldCommand
    ) -> tuple[dict, bool]:
        return self._add_or_ensure_field(scope, command, ensure=False)

    def ensure_field(
        self, scope: TaskCapabilityScope, command: EnsureProjectFieldCommand
    ) -> tuple[dict, bool]:
        return self._add_or_ensure_field(scope, command, ensure=True)

    def _add_or_ensure_field(
        self,
        scope: TaskCapabilityScope,
        command: AddProjectFieldCommand | EnsureProjectFieldCommand,
        *,
        ensure: bool,
    ) -> tuple[dict, bool]:
        kind = "ensureField" if ensure else "addField"
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            _task, run, _snapshot = self._facts(
                session, scope.project_id, scope.task_id, scope.run_id
            )
            existing_operation = self._existing(
                session,
                scope,
                kind,
                command.operation_id,
                command.request_digest,
            )
            if existing_operation is not None:
                session.rollback()
                return _operation_result(existing_operation), True
            if isinstance(command, EnsureProjectFieldCommand):
                scope.authorize_ensure_field(
                    command, current_execution_generation=run.execution_generation
                )
            else:
                scope.authorize_add_field(
                    command, current_execution_generation=run.execution_generation
                )
            catalog = SqlAlchemyProjectDataCatalog(self._factory)
            table = catalog._table(session, command.project_id, command.table_id, True)
            if table.current_generation != command.dataset_generation:
                raise ProjectError(
                    "DATASET_GENERATION_GONE", "Dataset was replaced", 410
                )
            catalog._cas(table.table_revision, command.expected_table_revision)
            definition = command.request_payload["definition"]
            matching = session.scalar(
                select(DataFieldRow).where(
                    DataFieldRow.project_id == command.project_id,
                    DataFieldRow.table_id == command.table_id,
                    DataFieldRow.dataset_generation == command.dataset_generation,
                    DataFieldRow.key == definition["key"],
                )
            )
            if matching is not None:
                if not ensure:
                    raise ProjectError(
                        "FIELD_KEY_CONFLICT", "Field key is already in use", 409
                    )
                comparable = {
                    "key": matching.key,
                    "name": matching.name,
                    "type": matching.type,
                    "required": matching.required,
                    "validation": matching.validation,
                }
                if comparable != definition:
                    raise ProjectError(
                        "FIELD_DEFINITION_CONFLICT",
                        "Existing field has a different definition",
                        409,
                        {"fieldRef": _catalog_field(matching)["ref"]},
                    )
                snapshot = _catalog_field(matching)
                result = {
                    "action": "ensure",
                    "created": False,
                    "field": snapshot,
                    "tableRevision": table.table_revision,
                }
                operation = _completed_operation(
                    scope,
                    command.operation_id,
                    kind,
                    command.request_digest,
                    result,
                )
                session.add(_operation_row(operation))
                self._commit(session)
                return result, False
            records = list(
                session.scalars(
                    select(DataRecordRow).where(
                        DataRecordRow.project_id == command.project_id,
                        DataRecordRow.table_id == command.table_id,
                        DataRecordRow.dataset_generation == command.dataset_generation,
                        DataRecordRow.deleted.is_(False),
                    )
                )
            )
            if definition["required"] and records and not command.has_default:
                raise ProjectError(
                    "EXISTING_RECORD_DEFAULT_REQUIRED",
                    "A valid default is required for existing records",
                    422,
                )
            if command.has_default and records:
                active_lease = session.scalar(
                    select(ProjectRecordLeaseRow.id).where(
                        ProjectRecordLeaseRow.project_id == command.project_id,
                        ProjectRecordLeaseRow.record_ref["tableId"].as_string()
                        == command.table_id,
                        ProjectRecordLeaseRow.record_ref[
                            "datasetGeneration"
                        ].as_string()
                        == command.dataset_generation,
                        ProjectRecordLeaseRow.state.in_(("held", "reconciling")),
                    )
                )
                if active_lease is not None:
                    raise ProjectError(
                        "FIELD_IN_USE",
                        "Existing records are currently used by an active task",
                        423,
                        {"retryable": True},
                    )
            prepared_backfills = (
                [
                    (
                        record,
                        {
                            **record.values_json,
                            command.field_id: command.request_payload["default"],
                        },
                    )
                    for record in records
                ]
                if command.has_default
                else []
            )
            try:
                backfill_budget([values for _record, values in prepared_backfills])
            except SchemaBackfillLimit as error:
                raise ProjectError(
                    "SCHEMA_BACKFILL_LIMIT",
                    str(error),
                    422,
                    {
                        "maxRecords": 1000,
                        "maxBytes": 4 * 1024 * 1024,
                        "retryable": False,
                    },
                ) from error
            position = (
                session.scalar(
                    select(func.count())
                    .select_from(DataFieldRow)
                    .where(
                        DataFieldRow.dataset_generation == command.dataset_generation
                    )
                )
                or 0
            )
            now = datetime.now(UTC)
            row = DataFieldRow(
                id=command.field_id,
                project_id=command.project_id,
                table_id=command.table_id,
                dataset_generation=command.dataset_generation,
                key=definition["key"],
                name=definition["name"],
                type=definition["type"],
                required=definition["required"],
                writable=True,
                formula=False,
                validation=definition["validation"],
                field_revision=1,
                position=position,
            )
            session.add(row)
            table.table_revision += 1
            table.updated_at = now
            snapshot = _catalog_field(row)
            result = {
                "action": "ensure" if ensure else "create",
                "created": True,
                "field": snapshot,
                "tableRevision": table.table_revision,
            }
            operation = _completed_operation(
                scope,
                command.operation_id,
                kind,
                command.request_digest,
                result,
            )
            session.add(_operation_row(operation))
            session.flush()
            session.add(_field_change(operation, None, snapshot, sequence=1))
            if command.has_default:
                for sequence, (record, values) in enumerate(prepared_backfills, 2):
                    before = {
                        "values": record.values_json,
                        "contentRevision": record.content_revision,
                    }
                    record.values_json = values
                    record.content_revision += 1
                    record.updated_at = now
                    session.add(
                        _record_value_change(
                            operation, record, before, sequence=sequence
                        )
                    )
            try:
                self._commit(session)
            except IntegrityError as error:
                raise ProjectError(
                    "FIELD_KEY_CONFLICT", "Field key is already in use", 409
                ) from error
            return result, False

    def modify_field(
        self, scope: TaskCapabilityScope, command: ModifyProjectFieldCommand
    ) -> tuple[dict, bool]:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            _task, run, _snapshot = self._facts(
                session, scope.project_id, scope.task_id, scope.run_id
            )
            existing = self._existing(
                session,
                scope,
                "modifyField",
                command.operation_id,
                command.request_digest,
            )
            if existing is not None:
                session.rollback()
                return _operation_result(existing), True
            scope.authorize_modify_field(
                command, current_execution_generation=run.execution_generation
            )
            if not self._field_declared_or_created(
                session,
                scope,
                command.table_id,
                command.dataset_generation,
                command.field_id,
            ):
                raise ProjectError(
                    "CAPABILITY_SCOPE_DENIED",
                    "Field is outside the task capability",
                    403,
                )
            catalog = SqlAlchemyProjectDataCatalog(self._factory)
            table = catalog._table(session, command.project_id, command.table_id, True)
            if table.current_generation != command.dataset_generation:
                raise ProjectError(
                    "DATASET_GENERATION_GONE", "Dataset was replaced", 410
                )
            row = session.scalar(
                select(DataFieldRow).where(
                    DataFieldRow.project_id == command.project_id,
                    DataFieldRow.table_id == command.table_id,
                    DataFieldRow.dataset_generation == command.dataset_generation,
                    DataFieldRow.id == command.field_id,
                )
            )
            if row is None:
                raise ProjectError("FIELD_NOT_FOUND", "Field was not found", 404)
            catalog._cas(table.table_revision, command.expected_table_revision)
            catalog._cas(row.field_revision, command.expected_field_revision, "Field")
            ref = {
                "projectId": command.project_id,
                "tableId": command.table_id,
                "datasetGeneration": command.dataset_generation,
                "fieldId": command.field_id,
            }
            catalog._impacts.require_field_update(
                session,
                command.project_id,
                ref,
                command.request_payload["definition"],
                command.impact_revision,
            )
            before = _catalog_field(row)
            definition = command.request_payload["definition"]
            changed = any(
                before[key] != definition[key]
                for key in ("key", "name", "type", "required", "validation")
            )
            if changed:
                row.key = definition["key"]
                row.name = definition["name"]
                row.type = definition["type"]
                row.required = definition["required"]
                row.validation = definition["validation"]
                row.field_revision += 1
                table.table_revision += 1
                table.updated_at = datetime.now(UTC)
            after = _catalog_field(row)
            result = {
                "action": "update",
                "field": after,
                "tableRevision": table.table_revision,
            }
            operation = _completed_operation(
                scope,
                command.operation_id,
                "modifyField",
                command.request_digest,
                result,
            )
            session.add(_operation_row(operation))
            session.flush()
            if changed:
                session.add(_field_change(operation, before, after, sequence=1))
            try:
                self._commit(session)
            except IntegrityError as error:
                raise ProjectError(
                    "FIELD_KEY_CONFLICT", "Field key is already in use", 409
                ) from error
            return result, False

    def preview_field_change(
        self,
        scope: TaskCapabilityScope,
        request: PreviewProjectFieldChangeRequest,
    ) -> dict:
        with self._factory() as session:
            _task, run, _snapshot = self._facts(
                session, scope.project_id, scope.task_id, scope.run_id
            )
            scope.authorize_preview_field_change(
                request, current_execution_generation=run.execution_generation
            )
            if not self._field_declared_or_created(
                session,
                scope,
                request.table_id,
                request.dataset_generation,
                request.field_id,
            ):
                raise ProjectError(
                    "CAPABILITY_SCOPE_DENIED",
                    "Field is outside the task capability",
                    403,
                )
        return SqlAlchemyProjectDataCatalog(self._factory).preview_field_update(
            request.project_id,
            {
                "projectId": request.project_id,
                "tableId": request.table_id,
                "datasetGeneration": request.dataset_generation,
                "fieldId": request.field_id,
            },
            request.request_payload["definition"],
        )

    @staticmethod
    def _field_declared_or_created(
        session: Session,
        scope: TaskCapabilityScope,
        table_id: str,
        dataset_generation: str,
        field_id: str,
    ) -> bool:
        if any(
            grant.table_id == table_id
            and grant.dataset_generation == dataset_generation
            and "modifyField" in grant.operations
            and field_id in grant.field_ids
            for grant in scope.table_grants
        ):
            return True
        rows = session.scalars(
            select(ProjectOperationRow).where(
                ProjectOperationRow.project_id == scope.project_id,
                ProjectOperationRow.kind.in_(("addField", "ensureField")),
                ProjectOperationRow.resource["taskId"].as_string() == scope.task_id,
                ProjectOperationRow.resource["runId"].as_string() == scope.run_id,
                ProjectOperationRow.resource["executionGeneration"].as_integer()
                == scope.execution_generation,
                ProjectOperationRow.status == "succeeded",
            )
        ).all()
        return any(
            isinstance(row.result, dict)
            and isinstance(row.result.get("field"), dict)
            and row.result["field"].get("ref")
            == {
                "projectId": scope.project_id,
                "tableId": table_id,
                "datasetGeneration": dataset_generation,
                "fieldId": field_id,
            }
            for row in rows
        )

    def query_operation(
        self, scope: TaskCapabilityScope, operation_id: str
    ) -> dict | None:
        with self._factory() as session:
            row = session.get(ProjectOperationRow, operation_id)
            if row is None:
                return None
            self._authorize_operation(row, scope, row.kind)
            return _operation_result(row)

    @staticmethod
    def _record_read(
        session: Session,
        scope: TaskCapabilityScope,
        purpose: str,
        field_ids: tuple[str, ...],
        snapshot: dict,
    ) -> None:
        ref = snapshot["ref"]
        key = ref["recordKey"]
        session.add(
            ProjectTaskRecordReadRow(
                id=str(uuid4()),
                project_id=scope.project_id,
                task_id=scope.task_id,
                run_id=scope.run_id,
                execution_generation=scope.execution_generation,
                table_id=ref["tableId"],
                dataset_generation=ref["datasetGeneration"],
                key_type=key["type"],
                key_value=key["value"],
                field_ids=list(field_ids),
                read_purpose=purpose,
                content_revision=snapshot["contentRevision"],
                status_revision=snapshot["statusRevision"],
                link_revision=snapshot["linkRevision"],
                snapshot=snapshot,
                created_at=datetime.now(UTC),
            )
        )

    @staticmethod
    def _existing(
        session: Session,
        scope: TaskCapabilityScope,
        kind: str,
        operation_id: str,
        digest: str,
    ):
        row = session.scalar(
            select(ProjectOperationRow).where(
                ProjectOperationRow.idempotency_key == operation_id
            )
        )
        if row is not None and (row.request_digest != digest or row.kind != kind):
            raise ProjectError(
                "OPERATION_PAYLOAD_MISMATCH",
                "Operation identity was used for another request",
                409,
            )
        if row is not None:
            SqlAlchemyProjectDataCapabilities._authorize_operation(row, scope, kind)
        return row

    @staticmethod
    def _authorize_operation(
        row: ProjectOperationRow, scope: TaskCapabilityScope, kind: str
    ) -> None:
        resource = row.resource if isinstance(row.resource, dict) else {}
        if (
            row.project_id != scope.project_id
            or row.kind != kind
            or resource.get("taskId") != scope.task_id
            or resource.get("runId") != scope.run_id
            or resource.get("executionGeneration") != scope.execution_generation
        ):
            raise ProjectError(
                "CAPABILITY_SCOPE_DENIED",
                "Operation does not belong to this task capability",
                403,
            )

    @staticmethod
    def _facts(session: Session, project_id: str, task_id: str, run_id: str):
        task = session.get(ProjectTaskRow, task_id)
        run = session.get(WorkflowRunRow, run_id)
        snapshot = session.scalar(
            select(ProjectTaskInputSnapshotRow).where(
                ProjectTaskInputSnapshotRow.task_id == task_id
            )
        )
        if (
            task is None
            or task.project_id != project_id
            or task.run_id != run_id
            or run is None
            or snapshot is None
        ):
            raise ProjectError(
                "CAPABILITY_SCOPE_DENIED", "Task capability facts do not match", 403
            )
        if run.status != "running":
            raise ProjectError(
                "LEASE_REVOKED",
                "Project data capability is no longer active",
                409,
                {"runStatus": run.status, "retryable": False},
            )
        return task, run, snapshot

    @staticmethod
    def _leased_cursor(session: Session, scope: TaskCapabilityScope, ref: RecordRef):
        ref_payload = _ref_payload(ref)
        lease = session.scalar(
            select(ProjectRecordLeaseRow).where(
                ProjectRecordLeaseRow.project_id == scope.project_id,
                ProjectRecordLeaseRow.task_id == scope.task_id,
                ProjectRecordLeaseRow.run_id == scope.run_id,
                ProjectRecordLeaseRow.state.in_(("held", "reconciling")),
                ProjectRecordLeaseRow.record_ref == ref_payload,
            )
        )
        if lease is None:
            raise ProjectError(
                "CAPABILITY_SCOPE_DENIED", "Record is not leased by this task", 403
            )
        cursor = session.scalar(
            select(ProjectTaskRecordCursorRow).where(
                ProjectTaskRecordCursorRow.task_id == scope.task_id,
                ProjectTaskRecordCursorRow.lease_id == lease.id,
            )
        )
        if cursor is None:
            raise ProjectError(
                "CAPABILITY_FACTS_INCOMPLETE", "Task write cursor is missing", 409
            )
        return lease, cursor

    @classmethod
    def _write_cursor(
        cls,
        session: Session,
        scope: TaskCapabilityScope,
        task: ProjectTaskRow,
        ref: RecordRef,
        row: DataRecordRow,
        lease_mode: str,
        *,
        expected_content: int | None = None,
        expected_status: int | None = None,
        expected_link: int | None = None,
    ):
        if lease_mode == "existing":
            return cls._leased_cursor(session, scope, ref)
        active = session.scalar(
            select(ProjectRecordLeaseRow).where(
                ProjectRecordLeaseRow.lease_key
                == _lease_key(
                    LeaseKey(
                        "local",
                        scope.project_id,
                        ref.table_id,
                        ref.dataset_generation,
                        ref.record_key,
                    )
                ),
                ProjectRecordLeaseRow.state.in_(("held", "reconciling")),
            )
        )
        if active is not None:
            if active.task_id == scope.task_id and active.run_id == scope.run_id:
                cursor = session.scalar(
                    select(ProjectTaskRecordCursorRow).where(
                        ProjectTaskRecordCursorRow.task_id == scope.task_id,
                        ProjectTaskRecordCursorRow.lease_id == active.id,
                    )
                )
                if cursor is None:
                    raise ProjectError(
                        "CAPABILITY_FACTS_INCOMPLETE",
                        "Task write cursor is missing",
                        409,
                    )
                return active, cursor
            raise ProjectError(
                "LEASE_BUSY",
                "Record is currently used by another task",
                409,
                {"retryable": True},
            )
        evidence = session.scalar(
            select(ProjectTaskRecordReadRow)
            .where(
                ProjectTaskRecordReadRow.project_id == scope.project_id,
                ProjectTaskRecordReadRow.task_id == scope.task_id,
                ProjectTaskRecordReadRow.run_id == scope.run_id,
                ProjectTaskRecordReadRow.execution_generation
                == scope.execution_generation,
                ProjectTaskRecordReadRow.table_id == ref.table_id,
                ProjectTaskRecordReadRow.dataset_generation == ref.dataset_generation,
                ProjectTaskRecordReadRow.key_type == ref.record_key.type,
                ProjectTaskRecordReadRow.key_value == ref.record_key.value,
            )
            .order_by(ProjectTaskRecordReadRow.created_at.desc())
        )
        if evidence is None:
            raise ProjectError(
                "CAPABILITY_SCOPE_DENIED",
                "Record was not returned by a task-scoped read",
                403,
            )
        expected_pairs = (
            ("content", expected_content, evidence.content_revision),
            ("status", expected_status, evidence.status_revision),
            ("link", expected_link, evidence.link_revision),
        )
        for kind, expected, observed in expected_pairs:
            if expected is not None and expected != observed:
                raise ProjectError(
                    "REVISION_CONFLICT",
                    f"Record {kind} revision does not match the task read",
                    409,
                    {"expectedRevision": expected, "readRevision": observed},
                )
        return cls._new_lease_cursor(
            session,
            scope,
            task,
            ref.table_id,
            ref.dataset_generation,
            ref.record_key,
            row,
            "queryResult",
        )

    @staticmethod
    def _new_lease_cursor(
        session: Session,
        scope: TaskCapabilityScope,
        task: ProjectTaskRow,
        table_id: str,
        generation: str,
        key: RecordKey,
        row: DataRecordRow,
        source: str,
    ):
        now = datetime.now(UTC)
        ref = RecordRef(scope.project_id, table_id, generation, key)
        payload = _ref_payload(ref)
        lease = ProjectRecordLeaseRow(
            id=str(uuid4()),
            lease_key=_lease_key(
                LeaseKey("local", scope.project_id, table_id, generation, key)
            ),
            project_id=scope.project_id,
            batch_id=task.batch_id,
            task_id=scope.task_id,
            run_id=scope.run_id,
            record_ref=payload,
            lease_generation=1,
            state="held",
            created_at=now,
            updated_at=now,
            released_at=None,
        )
        session.add(lease)
        session.flush()
        cursor = ProjectTaskRecordCursorRow(
            id=str(uuid4()),
            task_id=scope.task_id,
            lease_id=lease.id,
            record_ref=payload,
            content_revision=row.content_revision,
            status_revision=row.status_revision,
            link_revision=row.link_revision,
            source=source,
            updated_at=now,
        )
        session.add(cursor)
        return lease, cursor

    @staticmethod
    def _commit(session: Session) -> None:
        try:
            session.commit()
        except Exception:
            session.invalidate()
            raise


def _completed_operation(
    scope: TaskCapabilityScope, operation_id: str, kind: str, digest: str, result: dict
) -> ProjectOperation:
    now = datetime.now(UTC)
    resource = {
        "projectId": scope.project_id,
        "taskId": scope.task_id,
        "runId": scope.run_id,
        "executionGeneration": scope.execution_generation,
    }
    record_ref = result.get("ref")
    target = result.get("target")
    if not isinstance(record_ref, dict) and isinstance(target, dict):
        record_ref = target.get("recordRef")
    field = result.get("field")
    field_ref = field.get("ref") if isinstance(field, dict) else None
    if isinstance(record_ref, dict):
        resource.update(type="record", recordRef=record_ref)
    elif isinstance(field_ref, dict):
        resource.update(type="field", fieldRef=field_ref)
    else:
        resource.update(type="task")
    return ProjectOperation(
        operation_id,
        scope.project_id,
        operation_id,
        kind,
        digest,
        "succeeded",
        1,
        resource,
        result,
        None,
        now,
        now,
        now,
    )


def _change(
    operation: ProjectOperation, before: dict | None, after: dict
) -> DataChangeRow:
    return DataChangeRow(
        id=str(uuid4()),
        project_id=operation.project_id,
        operation_id=operation.operation_id,
        sequence=1,
        resource={"type": "record", "recordRef": after["ref"]},
        origin="workflow",
        before=before,
        after=after,
        created_at=operation.completed_at,
    )


def _field_change(
    operation: ProjectOperation,
    before: dict | None,
    after: dict,
    *,
    sequence: int,
) -> DataChangeRow:
    return DataChangeRow(
        id=str(uuid4()),
        project_id=operation.project_id,
        operation_id=operation.operation_id,
        sequence=sequence,
        resource={"type": "field", "fieldRef": after["ref"]},
        origin="workflow",
        before=before,
        after=after,
        created_at=operation.completed_at,
    )


def _record_value_change(
    operation: ProjectOperation,
    row: DataRecordRow,
    before: dict,
    *,
    sequence: int,
) -> DataChangeRow:
    ref = {
        "projectId": row.project_id,
        "tableId": row.table_id,
        "datasetGeneration": row.dataset_generation,
        "recordKey": {"type": row.key_type, "value": row.key_value},
    }
    return DataChangeRow(
        id=str(uuid4()),
        project_id=operation.project_id,
        operation_id=operation.operation_id,
        sequence=sequence,
        resource={"type": "record", "recordRef": ref},
        origin="workflow",
        before=before,
        after={
            "values": row.values_json,
            "contentRevision": row.content_revision,
        },
        created_at=operation.completed_at,
    )


def _ref(payload: dict) -> RecordRef:
    key = payload["recordKey"]
    return RecordRef(
        payload["projectId"],
        payload["tableId"],
        payload["datasetGeneration"],
        RecordKey(key["type"], key["value"]),
    )


def _ref_payload(ref: RecordRef) -> dict:
    return {
        "projectId": ref.project_id,
        "tableId": ref.table_id,
        "datasetGeneration": ref.dataset_generation,
        "recordKey": {"type": ref.record_key.type, "value": ref.record_key.value},
    }


def _revision_conflict(expected: int, current: int) -> ProjectError:
    return ProjectError(
        "REVISION_CONFLICT",
        "Record status was modified",
        409,
        {"expectedRevision": expected, "currentRevision": current, "retryable": False},
    )


def _content_revision_conflict(expected: int, current: int) -> ProjectError:
    return ProjectError(
        "REVISION_CONFLICT",
        "Record content was modified",
        409,
        {
            "expectedRevision": expected,
            "currentRevision": current,
            "retryable": False,
        },
    )


def _projected_snapshot(snapshot: dict, field_ids: tuple[str, ...]) -> dict:
    allowed = set(field_ids)
    return {
        **snapshot,
        "values": [
            value for value in snapshot["values"] if value["fieldId"] in allowed
        ],
    }


def _query_shape_digest(scope: TaskCapabilityScope, payload: dict) -> str:
    shape = {
        "projectId": scope.project_id,
        "taskId": scope.task_id,
        "runId": scope.run_id,
        "executionGeneration": scope.execution_generation,
        "request": payload | {"cursor": None},
    }
    return hashlib.sha256(
        json.dumps(
            shape,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _query_snapshot_matches(
    query: ProjectTaskRecordQueryRow,
    scope: TaskCapabilityScope,
    request: QueryProjectRecordsRequest,
    digest: str,
) -> bool:
    return (
        query.project_id == scope.project_id
        and query.task_id == scope.task_id
        and query.run_id == scope.run_id
        and query.execution_generation == scope.execution_generation
        and query.table_id == request.table_id
        and query.dataset_generation == request.dataset_generation
        and query.request_digest == digest
    )


def _encode_cursor(query_id: str, offset: int, digest: str) -> str:
    raw = json.dumps(
        {"queryId": query_id, "offset": offset, "digest": digest},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str | None, digest: str) -> tuple[str, int] | None:
    if cursor is None:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        value = json.loads(raw)
        query_id = value["queryId"]
        offset = value["offset"]
        if (
            not isinstance(value, dict)
            or value.get("digest") != digest
            or not isinstance(query_id, str)
            or len(query_id) != 36
            or type(offset) is not int
            or offset < 0
        ):
            raise ValueError
        return query_id, offset
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise _invalid_query_cursor() from error


def _invalid_query_cursor() -> ProjectError:
    return ProjectError(
        "QUERY_CURSOR_INVALID", "Query cursor does not match this request", 422
    )


def _query_snapshot_budget_error(
    reason: str, scanned_record_count: int, snapshot_bytes: int
) -> ProjectError:
    return ProjectError(
        "QUERY_SNAPSHOT_BUDGET_EXCEEDED",
        "Query result exceeds the stable snapshot budget",
        409,
        {
            "reason": reason,
            "scannedRecordCount": scanned_record_count,
            "maxRecords": MAX_QUERY_SNAPSHOT_RECORDS,
            "snapshotBytes": snapshot_bytes,
            "maxSnapshotBytes": MAX_QUERY_SNAPSHOT_BYTES,
            "retryable": False,
        },
    )


def _compare_records(
    left: DataRecordRow,
    right: DataRecordRow,
    order: list[dict[str, str]],
    field_types: dict[str, str],
) -> int:
    for item in order:
        if "fieldId" in item:
            field_id = item["fieldId"]
            a = left.values_json.get(field_id, MISSING)
            b = right.values_json.get(field_id, MISSING)
            if (a is MISSING or a is None) != (b is MISSING or b is None):
                result = 1 if a is MISSING or a is None else -1
            elif a is MISSING or a is None:
                result = 0
            else:
                result = compare_values(field_types[field_id], a, b) or 0
        else:
            system = item["systemField"]
            if system == "status":
                a, b = left.status_id, right.status_id
            elif system == "createdAt":
                a, b = left.created_at, right.created_at
            elif system == "updatedAt":
                a, b = left.updated_at, right.updated_at
            else:
                a, b = left.key_value, right.key_value
            result = (a > b) - (a < b) if a is not None and b is not None else 0
        if result:
            return -result if item["direction"] == "desc" else result
    return (
        (left.key_type, left.key_value) > (right.key_type, right.key_value)
        and 1
        or (
            -1
            if (left.key_type, left.key_value) < (right.key_type, right.key_value)
            else 0
        )
    )
