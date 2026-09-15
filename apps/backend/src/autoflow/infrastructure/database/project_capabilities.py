from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.capabilities import (
    CreateProjectRecordCommand,
    SetRecordStatusCommand,
    TaskCapabilityScope,
)
from autoflow.domain.project_data.identity import (
    RecordKey,
    record_key,
    system_record_key,
)
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_data import (
    _operation_result,
    _operation_row,
)
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
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
    ProjectTaskRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow


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
            return TaskCapabilityScope(
                project_id,
                task_id,
                run_id,
                run.execution_generation,
                refs,
                create_record_targets,
            )

    def set_record_status(
        self, scope: TaskCapabilityScope, command: SetRecordStatusCommand
    ) -> tuple[dict, bool]:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            _task, run, _snapshot = self._facts(
                session, scope.project_id, scope.task_id, scope.run_id
            )
            existing = self._existing(
                session, scope, "setRecordStatus", command.operation_id, command.request_digest
            )
            if existing is not None:
                session.rollback()
                return _operation_result(existing), True
            scope.authorize_set_status(
                command, current_execution_generation=run.execution_generation
            )
            lease, cursor = self._leased_cursor(session, scope, command.record_ref)
            row = SqlAlchemyProjectDataRecords._required_record(
                SqlAlchemyProjectDataRecords(self._factory),
                session,
                command.record_ref.project_id,
                command.record_ref.table_id,
                command.record_ref.dataset_generation,
                command.record_ref.record_key,
            )
            if (
                row.status_revision != command.expected_status_revision
                or cursor.status_revision != command.expected_status_revision
            ):
                raise _revision_conflict(
                    command.expected_status_revision, row.status_revision
                )
            if command.status_id is not None and session.scalar(
                select(DataStatusRow.id).where(
                    DataStatusRow.project_id == scope.project_id,
                    DataStatusRow.table_id == command.record_ref.table_id,
                    DataStatusRow.id == command.status_id,
                    DataStatusRow.deleted.is_(False),
                )
            ) is None:
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
                scope, command.operation_id, "setRecordStatus", command.request_digest, after
            )
            session.add(_operation_row(operation))
            session.flush()
            if changed:
                session.add(_change(operation, before, after))
            self._commit(session)
            return after, False

    def create_record(
        self, scope: TaskCapabilityScope, command: CreateProjectRecordCommand
    ) -> tuple[dict, bool]:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            _task, run, _snapshot = self._facts(
                session, scope.project_id, scope.task_id, scope.run_id
            )
            existing = self._existing(
                session, scope, "createRecord", command.operation_id, command.request_digest
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
                scope, command.operation_id, "createRecord", command.request_digest, after
            )
            try:
                session.add(row)
                session.add(_operation_row(operation))
                session.flush()
                session.add(_change(operation, None, after))
                self._commit(session)
            except IntegrityError as error:
                session.rollback()
                raise ProjectError(
                    "RECORD_ALREADY_EXISTS", "Record already exists", 409
                ) from error
            return after, False

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
        if row is not None and (
            row.request_digest != digest or row.kind != kind
        ):
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
            raise ProjectError("CAPABILITY_SCOPE_DENIED", "Task capability facts do not match", 403)
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
            raise ProjectError("CAPABILITY_SCOPE_DENIED", "Record is not leased by this task", 403)
        cursor = session.scalar(
            select(ProjectTaskRecordCursorRow).where(
                ProjectTaskRecordCursorRow.task_id == scope.task_id,
                ProjectTaskRecordCursorRow.lease_id == lease.id,
            )
        )
        if cursor is None:
            raise ProjectError("CAPABILITY_FACTS_INCOMPLETE", "Task write cursor is missing", 409)
        return lease, cursor

    @staticmethod
    def _commit(session: Session) -> None:
        try:
            session.commit()
        except Exception:
            session.invalidate()
            raise


def _completed_operation(scope: TaskCapabilityScope, operation_id: str, kind: str, digest: str, result: dict) -> ProjectOperation:
    now = datetime.now(UTC)
    return ProjectOperation(
        operation_id,
        scope.project_id,
        operation_id,
        kind,
        digest,
        "succeeded",
        1,
        {
            "type": "record",
            "projectId": scope.project_id,
            "taskId": scope.task_id,
            "runId": scope.run_id,
            "executionGeneration": scope.execution_generation,
        },
        result,
        None,
        now,
        now,
        now,
    )


def _change(operation: ProjectOperation, before: dict | None, after: dict) -> DataChangeRow:
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
