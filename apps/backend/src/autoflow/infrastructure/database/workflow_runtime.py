from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from autoflow.domain.workflows.runtime import (
    CoreRun,
    CoreRunStatus,
    PreparedContent,
    RunArtifact,
    RunEvent,
    WorkflowRuntimeError,
    create_core_run,
    create_prepared_content,
    create_run_artifact,
    create_run_event,
    event_identity_digest,
    restore_core_run,
    thaw_json,
    transition_core_run,
)
from autoflow.infrastructure.database.session import (
    is_sqlite_contention as _is_sqlite_contention,
)

from .workflow_runtime_models import (
    WorkflowPreparedContentRow,
    WorkflowRunArtifactRow,
    WorkflowRunEventRow,
    WorkflowRunRow,
)


class SqlAlchemyWorkflowRuntimeRepository:
    """Runtime writer scoped to a caller-owned SQLAlchemy Session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def prepare_content(
        self,
        *,
        prepared_content_id: str,
        prepare_operation_id: str,
        request_digest: str,
        workflow_id: str,
        source_revision: int | None,
        checksum: str,
        document: dict[str, Any],
        execution_plan: dict[str, Any],
        adapter_version: str,
        capability_requirements: list[str] | tuple[str, ...],
        provenance: dict[str, Any],
        created_at: datetime,
    ) -> PreparedContent:
        existing = self._session.scalar(
            select(WorkflowPreparedContentRow).where(
                WorkflowPreparedContentRow.prepare_operation_id == prepare_operation_id
            )
        )
        if existing is not None:
            if existing.request_digest != request_digest:
                raise WorkflowRuntimeError(
                    "OPERATION_PAYLOAD_MISMATCH", "幂等键已用于另一准备请求"
                )
            return _prepared_content(existing)

        content = create_prepared_content(
            prepared_content_id=prepared_content_id,
            prepare_operation_id=prepare_operation_id,
            request_digest=request_digest,
            workflow_id=workflow_id,
            source_revision=source_revision,
            checksum=checksum,
            document=document,
            execution_plan=execution_plan,
            adapter_version=adapter_version,
            capability_requirements=capability_requirements,
            provenance=provenance,
            created_at=created_at,
        )
        try:
            self._ensure_physical_transaction()
            with self._session.begin_nested():
                self._session.add(_prepared_content_row(content))
                self._session.flush()
        except OperationalError as error:
            if not _is_sqlite_contention(error):
                raise
            raise WorkflowRuntimeError(
                "PREPARED_CONTENT_CONCURRENT_WRITE",
                "执行内容正在由另一请求准备",
            ) from error
        except IntegrityError:
            existing = self._session.scalar(
                select(WorkflowPreparedContentRow).where(
                    WorkflowPreparedContentRow.prepare_operation_id
                    == prepare_operation_id
                )
            )
            if existing is not None:
                if existing.request_digest != request_digest:
                    raise WorkflowRuntimeError(
                        "OPERATION_PAYLOAD_MISMATCH",
                        "幂等键已用于另一准备请求",
                    ) from None
                return _prepared_content(existing)
            raise WorkflowRuntimeError(
                "PREPARED_CONTENT_ID_CONFLICT", "执行内容标识已被占用"
            ) from None
        return content

    def get_prepared_content(
        self,
        *,
        prepared_content_id: str | None = None,
        prepare_operation_id: str | None = None,
    ) -> PreparedContent | None:
        if (prepared_content_id is None) == (prepare_operation_id is None):
            raise ValueError("provide exactly one prepared content identity")
        if prepared_content_id is not None:
            row = self._session.get(WorkflowPreparedContentRow, prepared_content_id)
        else:
            row = self._session.scalar(
                select(WorkflowPreparedContentRow).where(
                    WorkflowPreparedContentRow.prepare_operation_id
                    == prepare_operation_id
                )
            )
        return _prepared_content(row) if row is not None else None

    def prepare_run(
        self,
        *,
        run_id: str,
        run_request_id: str,
        request_digest: str,
        prepared_content_id: str,
        parameters: dict[str, Any],
        input_snapshot_ref: dict[str, Any] | None,
        resource_request: dict[str, Any],
        capability_bindings: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        created_at: datetime,
    ) -> CoreRun:
        existing = self._session.scalar(
            select(WorkflowRunRow).where(
                WorkflowRunRow.run_request_id == run_request_id
            )
        )
        if existing is not None:
            if existing.request_digest != request_digest:
                raise WorkflowRuntimeError(
                    "RUN_REQUEST_CONFLICT", "运行请求身份已用于另一请求"
                )
            return _run(existing)

        prepared_row = self._session.get(
            WorkflowPreparedContentRow, prepared_content_id
        )
        if prepared_row is None:
            raise WorkflowRuntimeError(
                "PREPARED_CONTENT_MISSING", "不可变执行内容不存在", 404
            )
        if not _prepared_content_is_executable(prepared_row):
            raise WorkflowRuntimeError(
                "PREPARED_CONTENT_NOT_EXECUTABLE", "不可变执行内容仅供历史查询"
            )
        run = create_core_run(
            run_id=run_id,
            run_request_id=run_request_id,
            request_digest=request_digest,
            prepared_content_id=prepared_content_id,
            parameters=parameters,
            input_snapshot_ref=input_snapshot_ref,
            resource_request=resource_request,
            capability_bindings=capability_bindings,
            created_at=created_at,
        )
        try:
            self._ensure_physical_transaction()
            with self._session.begin_nested():
                self._session.add(_run_row(run))
                self._session.flush()
        except OperationalError as error:
            if not _is_sqlite_contention(error):
                raise
            raise WorkflowRuntimeError(
                "RUN_REQUEST_CONFLICT", "运行请求正在由另一事务准备"
            ) from error
        except IntegrityError:
            existing = self._session.scalar(
                select(WorkflowRunRow).where(
                    WorkflowRunRow.run_request_id == run_request_id
                )
            )
            if existing is not None:
                if existing.request_digest != request_digest:
                    raise WorkflowRuntimeError(
                        "RUN_REQUEST_CONFLICT",
                        "运行请求身份已用于另一请求",
                    ) from None
                return _run(existing)
            raise WorkflowRuntimeError("RUN_ID_CONFLICT", "运行标识已被占用") from None
        return run

    def get_run(
        self,
        *,
        run_id: str | None = None,
        run_request_id: str | None = None,
    ) -> CoreRun | None:
        if (run_id is None) == (run_request_id is None):
            raise ValueError("provide exactly one run identity")
        if run_id is not None:
            row = self._session.get(WorkflowRunRow, run_id)
        else:
            row = self._session.scalar(
                select(WorkflowRunRow).where(
                    WorkflowRunRow.run_request_id == run_request_id
                )
            )
        return _run(row) if row is not None else None

    def transition_run(
        self,
        run_id: str,
        *,
        target_status: CoreRunStatus,
        expected_status_revision: int,
        expected_execution_generation: int,
        now: datetime,
        error: dict[str, Any] | None = None,
    ) -> CoreRun:
        row = self._session.get(WorkflowRunRow, run_id)
        if row is None:
            raise WorkflowRuntimeError("RUN_NOT_FOUND", "运行不存在", 404)
        if target_status == "running":
            prepared_row = self._session.get(
                WorkflowPreparedContentRow, row.prepared_content_id
            )
            if prepared_row is None:
                raise WorkflowRuntimeError(
                    "PREPARED_CONTENT_MISSING", "不可变执行内容不存在", 404
                )
            if not _prepared_content_is_executable(prepared_row):
                raise WorkflowRuntimeError(
                    "PREPARED_CONTENT_NOT_EXECUTABLE",
                    "不可变执行内容仅供历史查询",
                )
        changed = transition_core_run(
            _run(row),
            target_status=target_status,
            expected_status_revision=expected_status_revision,
            expected_execution_generation=expected_execution_generation,
            now=now,
            error=error,
        )
        result = self._session.execute(
            update(WorkflowRunRow)
            .where(
                WorkflowRunRow.id == run_id,
                WorkflowRunRow.status_revision == expected_status_revision,
                WorkflowRunRow.execution_generation == expected_execution_generation,
            )
            .values(
                status=changed.status,
                status_revision=changed.status_revision,
                execution_generation=changed.execution_generation,
                updated_at=changed.updated_at,
                started_at=changed.started_at,
                completed_at=changed.completed_at,
                error=thaw_json(changed.error),
            )
            .execution_options(synchronize_session=False)
        )
        if getattr(result, "rowcount", 0) != 1:
            self._session.expire(row)
            current = _run(row)
            if current.execution_generation != expected_execution_generation:
                raise WorkflowRuntimeError(
                    "EXECUTION_GENERATION_REVOKED", "执行代次已失效"
                )
            raise WorkflowRuntimeError("RUN_STATUS_CONFLICT", "运行状态已发生变化")
        self._session.expire(row)
        return _run(row)

    def append_event(self, value: dict[str, Any]) -> RunEvent:
        run_id = str(value["runId"])
        event_id = str(value["eventId"])
        existing = self._session.scalar(
            select(WorkflowRunEventRow).where(
                WorkflowRunEventRow.run_id == run_id,
                WorkflowRunEventRow.event_id == event_id,
            )
        )
        if existing is not None:
            event = _event(existing)
            if event_identity_digest(event) != _event_dict_digest(
                value, assigned_sequence=event.sequence
            ):
                raise WorkflowRuntimeError(
                    "RUN_EVENT_CONFLICT", "事件身份已用于另一内容"
                )
            return event

        row = self._session.get(WorkflowRunRow, run_id)
        if row is None:
            raise WorkflowRuntimeError("RUN_NOT_FOUND", "运行不存在", 404)
        previous_sequence = row.last_sequence
        assigned_sequence = previous_sequence + 1
        if "sequence" in value and int(value["sequence"]) != assigned_sequence:
            raise WorkflowRuntimeError(
                "RUN_EVENT_SEQUENCE_CONFLICT",
                "运行事件序号由核心分配，提交值与当前事实不一致",
            )
        event = _event_from_value(value, assigned_sequence=assigned_sequence)
        artifact = (
            _artifact_from_event(
                event,
                ordinal=(
                    self._session.scalar(
                        select(func.max(WorkflowRunArtifactRow.ordinal)).where(
                            WorkflowRunArtifactRow.run_id == run_id
                        )
                    )
                    or 0
                )
                + 1,
            )
            if event.kind == "artifact"
            else None
        )
        # The CAS and insert share a savepoint. A losing writer cannot leave the
        # sequence advanced without its event, nor leak a database exception.
        try:
            self._ensure_physical_transaction()
            with self._session.begin_nested():
                result = self._session.execute(
                    update(WorkflowRunRow)
                    .where(
                        WorkflowRunRow.id == run_id,
                        WorkflowRunRow.execution_generation
                        == event.execution_generation,
                        WorkflowRunRow.last_sequence == previous_sequence,
                    )
                    .values(last_sequence=assigned_sequence)
                    .execution_options(synchronize_session=False)
                )
                if getattr(result, "rowcount", 0) != 1:
                    raise _EventAppendRace
                self._session.add(_event_row(event))
                if artifact is not None:
                    self._session.add(_artifact_row(artifact))
                self._session.flush()
        except OperationalError as error:
            if not _is_sqlite_contention(error):
                raise
            self._session.expire_all()
            raise WorkflowRuntimeError(
                "RUN_EVENT_SEQUENCE_CONFLICT",
                "运行事件序号正在由另一写入分配",
            ) from error
        except (IntegrityError, _EventAppendRace):
            self._session.expire_all()
            duplicate = self._session.scalar(
                select(WorkflowRunEventRow).where(
                    WorkflowRunEventRow.run_id == run_id,
                    WorkflowRunEventRow.event_id == event_id,
                )
            )
            if duplicate is not None:
                persisted = _event(duplicate)
                if event_identity_digest(persisted) == event_identity_digest(event):
                    return persisted
                raise WorkflowRuntimeError(
                    "RUN_EVENT_CONFLICT", "事件身份已用于另一内容"
                ) from None
            current = self._session.get(WorkflowRunRow, run_id)
            if (
                current is not None
                and current.execution_generation != event.execution_generation
            ):
                raise WorkflowRuntimeError(
                    "EXECUTION_GENERATION_REVOKED", "执行代次已失效"
                ) from None
            raise WorkflowRuntimeError(
                "RUN_EVENT_SEQUENCE_CONFLICT", "另一事件已占用当前运行序号"
            ) from None
        self._session.expire(row)
        return event

    def _ensure_physical_transaction(self) -> None:
        connection = self._session.connection()
        if connection.dialect.name != "sqlite":
            return
        driver = getattr(connection.connection, "driver_connection", None)
        if driver is not None and not driver.in_transaction:
            connection.exec_driver_sql("BEGIN")

    def list_events(
        self, run_id: str, *, after_sequence: int, limit: int
    ) -> list[RunEvent]:
        rows = self._session.scalars(
            select(WorkflowRunEventRow)
            .where(
                WorkflowRunEventRow.run_id == run_id,
                WorkflowRunEventRow.sequence > after_sequence,
            )
            .order_by(WorkflowRunEventRow.sequence)
            .limit(limit)
        ).all()
        return [_event(row) for row in rows]

    def get_artifact(self, run_id: str, artifact_id: str) -> RunArtifact | None:
        row = self._session.get(WorkflowRunArtifactRow, (run_id, artifact_id))
        return _artifact(row) if row is not None and row.purpose == "error" else None

    def list_artifacts(
        self, run_id: str, *, offset: int, limit: int
    ) -> tuple[list[RunArtifact], int]:
        total = self._session.scalar(
            select(func.count())
            .select_from(WorkflowRunArtifactRow)
            .where(
                WorkflowRunArtifactRow.run_id == run_id,
                WorkflowRunArtifactRow.purpose == "error",
            )
        )
        rows = self._session.scalars(
            select(WorkflowRunArtifactRow)
            .where(
                WorkflowRunArtifactRow.run_id == run_id,
                WorkflowRunArtifactRow.purpose == "error",
            )
            .order_by(WorkflowRunArtifactRow.ordinal)
            .offset(offset)
            .limit(limit)
        ).all()
        return [_artifact(row) for row in rows], int(total or 0)


def _prepared_content_row(value: PreparedContent) -> WorkflowPreparedContentRow:
    return WorkflowPreparedContentRow(
        id=value.prepared_content_id,
        prepare_operation_id=value.prepare_operation_id,
        request_digest=value.request_digest,
        workflow_id=value.workflow_id,
        source_revision=value.source_revision,
        checksum=value.checksum,
        document=thaw_json(value.document),
        execution_plan=thaw_json(value.execution_plan),
        adapter_version=value.adapter_version,
        capability_requirements=list(value.capability_requirements),
        provenance=thaw_json(value.provenance),
        created_at=value.created_at,
    )


def _prepared_content(row: WorkflowPreparedContentRow) -> PreparedContent:
    return create_prepared_content(
        prepared_content_id=row.id,
        prepare_operation_id=row.prepare_operation_id,
        request_digest=row.request_digest,
        workflow_id=row.workflow_id,
        source_revision=row.source_revision,
        checksum=row.checksum,
        document=row.document,
        execution_plan=row.execution_plan,
        adapter_version=row.adapter_version,
        capability_requirements=row.capability_requirements,
        provenance=row.provenance,
        created_at=_aware(row.created_at),
    )


def _run_row(value: CoreRun) -> WorkflowRunRow:
    return WorkflowRunRow(
        id=value.run_id,
        run_request_id=value.run_request_id,
        request_digest=value.request_digest,
        prepared_content_id=value.prepared_content_id,
        parameters=thaw_json(value.parameters),
        input_snapshot_ref=thaw_json(value.input_snapshot_ref),
        resource_request=thaw_json(value.resource_request),
        capability_bindings=thaw_json(value.capability_bindings),
        status=value.status,
        status_revision=value.status_revision,
        execution_generation=value.execution_generation,
        last_sequence=value.last_sequence,
        created_at=value.created_at,
        updated_at=value.updated_at,
        started_at=value.started_at,
        completed_at=value.completed_at,
        error=thaw_json(value.error),
    )


def _run(row: WorkflowRunRow) -> CoreRun:
    return restore_core_run(
        run_id=row.id,
        run_request_id=row.run_request_id,
        request_digest=row.request_digest,
        prepared_content_id=row.prepared_content_id,
        parameters=row.parameters,
        input_snapshot_ref=row.input_snapshot_ref,
        resource_request=row.resource_request,
        capability_bindings=row.capability_bindings,
        status=row.status,  # type: ignore[arg-type]
        status_revision=row.status_revision,
        execution_generation=row.execution_generation,
        last_sequence=row.last_sequence,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
        started_at=_aware(row.started_at) if row.started_at is not None else None,
        completed_at=(
            _aware(row.completed_at) if row.completed_at is not None else None
        ),
        error=row.error,
    )


def _event_from_value(value: dict[str, Any], *, assigned_sequence: int) -> RunEvent:
    occurred_at = value["occurredAt"]
    if isinstance(occurred_at, str):
        occurred_at = datetime.fromisoformat(occurred_at)
    return create_run_event(
        event_id=str(value["eventId"]),
        run_id=str(value["runId"]),
        sequence=assigned_sequence,
        execution_generation=int(value["executionGeneration"]),
        kind=str(value["kind"]),
        node_id=str(value["nodeId"]) if value.get("nodeId") is not None else None,
        node_visit_id=(
            str(value["nodeVisitId"]) if value.get("nodeVisitId") is not None else None
        ),
        attempt=int(value["attempt"]) if value.get("attempt") is not None else None,
        occurred_at=occurred_at,
        payload=value.get("payload", {}),
    )


def _event_row(value: RunEvent) -> WorkflowRunEventRow:
    return WorkflowRunEventRow(
        run_id=value.run_id,
        sequence=value.sequence,
        event_id=value.event_id,
        execution_generation=value.execution_generation,
        kind=value.kind,
        node_id=value.node_id,
        node_visit_id=value.node_visit_id,
        attempt=value.attempt,
        occurred_at=value.occurred_at,
        payload=thaw_json(value.payload),
    )


def _event(row: WorkflowRunEventRow) -> RunEvent:
    return create_run_event(
        event_id=row.event_id,
        run_id=row.run_id,
        sequence=row.sequence,
        execution_generation=row.execution_generation,
        kind=row.kind,
        node_id=row.node_id,
        node_visit_id=row.node_visit_id,
        attempt=row.attempt,
        occurred_at=_aware(row.occurred_at),
        payload=row.payload,
    )


def _artifact_from_event(event: RunEvent, *, ordinal: int) -> RunArtifact:
    payload = thaw_json(event.payload)
    return create_run_artifact(
        artifact_id=str(payload.get("artifactId", "")),
        run_id=event.run_id,
        ordinal=ordinal,
        node_id=event.node_id or "",
        node_visit_id=event.node_visit_id,
        purpose=str(payload.get("purpose", "")),
        event_sequence=event.sequence,
        execution_generation=event.execution_generation,
        kind=str(payload.get("kind", "")),
        availability=str(payload.get("availability", "")),
        relative_path=payload.get("relativePath"),
        media_type=payload.get("mediaType"),
        byte_size=payload.get("byteSize"),
        sha256=payload.get("sha256"),
        created_at=event.occurred_at,
        unavailable_reason=payload.get("unavailableReason"),
    )


def _artifact_row(value: RunArtifact) -> WorkflowRunArtifactRow:
    payload = {
        "artifactId": value.artifact_id,
        "kind": value.kind,
        "purpose": value.purpose,
        "availability": value.availability,
        "relativePath": value.relative_path,
        "mediaType": value.media_type,
        "byteSize": value.byte_size,
        "sha256": value.sha256,
        "executionGeneration": value.execution_generation,
        "createdAt": value.created_at.isoformat(),
        "unavailableReason": value.unavailable_reason,
    }
    return WorkflowRunArtifactRow(
        run_id=value.run_id,
        id=value.artifact_id,
        ordinal=value.ordinal,
        node_id=value.node_id,
        execution_id=value.node_visit_id,
        payload=payload,
        purpose=value.purpose,
        event_seq=value.event_sequence,
    )


def _artifact(row: WorkflowRunArtifactRow) -> RunArtifact:
    payload = row.payload if isinstance(row.payload, dict) else {}
    try:
        created_at = datetime.fromisoformat(str(payload["createdAt"]))
        return create_run_artifact(
            artifact_id=row.id,
            run_id=row.run_id,
            ordinal=row.ordinal,
            node_id=row.node_id,
            node_visit_id=row.execution_id,
            purpose=row.purpose,
            event_sequence=row.event_seq,
            execution_generation=payload["executionGeneration"],
            kind=payload["kind"],
            availability=payload["availability"],
            relative_path=payload.get("relativePath"),
            media_type=payload.get("mediaType"),
            byte_size=payload.get("byteSize"),
            sha256=payload.get("sha256"),
            created_at=created_at,
            unavailable_reason=payload.get("unavailableReason"),
        )
    except (KeyError, TypeError, ValueError, WorkflowRuntimeError):
        return create_run_artifact(
            artifact_id=row.id,
            run_id=row.run_id,
            ordinal=max(row.ordinal, 1),
            node_id=row.node_id or "legacy",
            node_visit_id=row.execution_id,
            purpose="error",
            event_sequence=max(row.event_seq, 1),
            execution_generation=0,
            kind="screenshot",
            availability="unavailable",
            relative_path=None,
            media_type=None,
            byte_size=None,
            sha256=None,
            created_at=datetime.fromtimestamp(0, UTC),
            unavailable_reason="LEGACY_ARTIFACT_UNAVAILABLE",
        )


def _event_dict_digest(value: dict[str, Any], *, assigned_sequence: int) -> str:
    return event_identity_digest(
        _event_from_value(value, assigned_sequence=assigned_sequence)
    )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class _EventAppendRace(Exception):
    pass


def _prepared_content_is_executable(row: WorkflowPreparedContentRow) -> bool:
    return (
        row.adapter_version in {"webrpa-chain/v1", "webrpa-graph/v2"}
        and row.execution_plan.get("replayable") is not False
    )
