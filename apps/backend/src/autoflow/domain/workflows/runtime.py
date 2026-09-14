from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Literal

CoreRunStatus = Literal[
    "queued",
    "running",
    "waiting_manual",
    "resume_queued",
    "finishing",
    "stopping",
    "reconciling",
    "succeeded",
    "failed",
    "cancelled",
    "timed_out",
    "interrupted",
]

TERMINAL_STATUSES = frozenset(
    {"succeeded", "failed", "cancelled", "timed_out", "interrupted"}
)

_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"running", "stopping", "reconciling", "timed_out"}),
    "running": frozenset(
        {
            "waiting_manual",
            "finishing",
            "stopping",
            "reconciling",
            "timed_out",
        }
    ),
    "waiting_manual": frozenset(
        {"resume_queued", "stopping", "reconciling", "timed_out"}
    ),
    "resume_queued": frozenset({"running", "stopping", "reconciling", "timed_out"}),
    "finishing": frozenset(
        {"succeeded", "failed", "stopping", "reconciling", "timed_out"}
    ),
    "stopping": frozenset({"cancelled", "reconciling"}),
    "reconciling": TERMINAL_STATUSES,
}


class WorkflowRuntimeError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int = 409,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = dict(details or {})


@dataclass(frozen=True)
class PreparedContent:
    prepared_content_id: str
    prepare_operation_id: str
    request_digest: str
    workflow_id: str
    source_revision: int | None
    checksum: str
    document: Mapping[str, Any]
    execution_plan: Mapping[str, Any]
    adapter_version: str
    capability_requirements: tuple[str, ...]
    provenance: Mapping[str, Any]
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "document", _freeze_mapping(self.document))
        object.__setattr__(self, "execution_plan", _freeze_mapping(self.execution_plan))
        object.__setattr__(
            self, "capability_requirements", tuple(self.capability_requirements)
        )
        object.__setattr__(self, "provenance", _freeze_mapping(self.provenance))
        object.__setattr__(self, "created_at", _utc(self.created_at))


@dataclass(frozen=True)
class CoreRun:
    run_id: str
    run_request_id: str
    request_digest: str
    prepared_content_id: str
    parameters: Mapping[str, Any]
    input_snapshot_ref: Mapping[str, Any] | None
    resource_request: Mapping[str, Any]
    capability_bindings: tuple[Mapping[str, Any], ...]
    status: CoreRunStatus
    status_revision: int
    execution_generation: int
    last_sequence: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error: Mapping[str, Any] | None
    _event_identities: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", _freeze_mapping(self.parameters))
        object.__setattr__(
            self,
            "input_snapshot_ref",
            _freeze_mapping(self.input_snapshot_ref)
            if self.input_snapshot_ref is not None
            else None,
        )
        object.__setattr__(
            self, "resource_request", _freeze_mapping(self.resource_request)
        )
        object.__setattr__(
            self,
            "capability_bindings",
            tuple(_freeze_mapping(binding) for binding in self.capability_bindings),
        )
        object.__setattr__(self, "created_at", _utc(self.created_at))
        object.__setattr__(self, "updated_at", _utc(self.updated_at))
        object.__setattr__(
            self, "started_at", _utc(self.started_at) if self.started_at else None
        )
        object.__setattr__(
            self, "completed_at", _utc(self.completed_at) if self.completed_at else None
        )
        object.__setattr__(
            self,
            "error",
            _freeze_mapping(self.error) if self.error is not None else None,
        )
        object.__setattr__(self, "_event_identities", tuple(self._event_identities))

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES


@dataclass(frozen=True)
class RunEvent:
    event_id: str
    run_id: str
    sequence: int
    execution_generation: int
    kind: str
    node_id: str | None
    node_visit_id: str | None
    attempt: int | None
    occurred_at: datetime
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at))
        object.__setattr__(self, "payload", _freeze_mapping(self.payload))


def create_prepared_content(
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
    return PreparedContent(
        prepared_content_id=prepared_content_id,
        prepare_operation_id=prepare_operation_id,
        request_digest=request_digest,
        workflow_id=workflow_id,
        source_revision=source_revision,
        checksum=checksum,
        document=_freeze_mapping(document),
        execution_plan=_freeze_mapping(execution_plan),
        adapter_version=adapter_version,
        capability_requirements=tuple(capability_requirements),
        provenance=_freeze_mapping(provenance),
        created_at=created_at,
    )


def create_core_run(
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
    return CoreRun(
        run_id=run_id,
        run_request_id=run_request_id,
        request_digest=request_digest,
        prepared_content_id=prepared_content_id,
        parameters=_freeze_mapping(parameters),
        input_snapshot_ref=(
            _freeze_mapping(input_snapshot_ref)
            if input_snapshot_ref is not None
            else None
        ),
        resource_request=_freeze_mapping(resource_request),
        capability_bindings=tuple(
            _freeze_mapping(binding) for binding in capability_bindings
        ),
        status="queued",
        status_revision=1,
        execution_generation=0,
        last_sequence=0,
        created_at=created_at,
        updated_at=created_at,
        started_at=None,
        completed_at=None,
        error=None,
    )


def restore_core_run(
    *,
    run_id: str,
    run_request_id: str,
    request_digest: str,
    prepared_content_id: str,
    parameters: Mapping[str, Any],
    input_snapshot_ref: Mapping[str, Any] | None,
    resource_request: Mapping[str, Any],
    capability_bindings: Sequence[Mapping[str, Any]],
    status: CoreRunStatus,
    status_revision: int,
    execution_generation: int,
    last_sequence: int,
    created_at: datetime,
    updated_at: datetime,
    started_at: datetime | None,
    completed_at: datetime | None,
    error: Mapping[str, Any] | None,
) -> CoreRun:
    base = create_core_run(
        run_id=run_id,
        run_request_id=run_request_id,
        request_digest=request_digest,
        prepared_content_id=prepared_content_id,
        parameters=dict(parameters),
        input_snapshot_ref=(
            dict(input_snapshot_ref) if input_snapshot_ref is not None else None
        ),
        resource_request=dict(resource_request),
        capability_bindings=[dict(binding) for binding in capability_bindings],
        created_at=created_at,
    )
    return replace(
        base,
        status=status,
        status_revision=status_revision,
        execution_generation=execution_generation,
        last_sequence=last_sequence,
        updated_at=updated_at,
        started_at=started_at,
        completed_at=completed_at,
        error=_freeze_mapping(error) if error is not None else None,
    )


def transition_core_run(
    run: CoreRun,
    *,
    target_status: CoreRunStatus,
    expected_status_revision: int,
    expected_execution_generation: int,
    now: datetime,
    error: dict[str, Any] | None = None,
) -> CoreRun:
    if expected_status_revision != run.status_revision:
        raise WorkflowRuntimeError(
            "RUN_STATUS_CONFLICT",
            "运行状态已发生变化",
            details={
                "expectedStatusRevision": expected_status_revision,
                "currentStatusRevision": run.status_revision,
            },
        )
    if expected_execution_generation != run.execution_generation:
        raise WorkflowRuntimeError(
            "EXECUTION_GENERATION_REVOKED",
            "执行代次已失效",
            details={
                "expectedExecutionGeneration": expected_execution_generation,
                "currentExecutionGeneration": run.execution_generation,
            },
        )
    if run.terminal:
        if target_status == run.status:
            return run
        raise WorkflowRuntimeError("RUN_TERMINAL", "运行已结束")
    if target_status == run.status:
        return run
    if target_status not in _TRANSITIONS.get(run.status, frozenset()):
        raise WorkflowRuntimeError(
            "RUN_STATUS_TRANSITION_INVALID",
            "运行状态转换不合法",
            details={"currentStatus": run.status, "targetStatus": target_status},
        )

    generation = run.execution_generation
    if target_status == "running" and run.status in {"queued", "resume_queued"}:
        generation += 1
    elif target_status == "reconciling":
        # Reconciliation starts by revoking the previous worker's write authority.
        generation += 1
    started_at = run.started_at
    if target_status == "running" and started_at is None:
        started_at = now
    completed_at = now if target_status in TERMINAL_STATUSES else None
    return replace(
        run,
        status=target_status,
        status_revision=run.status_revision + 1,
        execution_generation=generation,
        updated_at=now,
        started_at=started_at,
        completed_at=completed_at,
        error=_freeze_mapping(error) if error is not None else None,
    )


def append_run_event(
    run: CoreRun, event: dict[str, Any] | RunEvent
) -> tuple[CoreRun, bool]:
    parsed = (
        event
        if isinstance(event, RunEvent)
        else _event_from_dict(event, assigned_sequence=run.last_sequence + 1)
    )
    digest = event_identity_digest(parsed)
    known = dict(run._event_identities)
    if parsed.event_id in known:
        if known[parsed.event_id] != digest:
            raise WorkflowRuntimeError("RUN_EVENT_CONFLICT", "事件身份已用于另一内容")
        return run, False
    if parsed.run_id != run.run_id:
        raise WorkflowRuntimeError("RUN_EVENT_RUN_MISMATCH", "事件不属于当前运行")
    if parsed.execution_generation != run.execution_generation:
        raise WorkflowRuntimeError("EXECUTION_GENERATION_REVOKED", "执行代次已失效")
    if parsed.sequence != run.last_sequence + 1:
        raise WorkflowRuntimeError(
            "RUN_EVENT_SEQUENCE_CONFLICT",
            "运行事件序号不连续",
            details={
                "expectedSequence": run.last_sequence + 1,
                "receivedSequence": parsed.sequence,
            },
        )
    advanced = replace(
        run,
        last_sequence=parsed.sequence,
        _event_identities=run._event_identities + ((parsed.event_id, digest),),
    )
    return advanced, True


def create_run_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    execution_generation: int,
    kind: str,
    node_id: str | None,
    node_visit_id: str | None,
    attempt: int | None,
    occurred_at: datetime,
    payload: Mapping[str, Any],
) -> RunEvent:
    return RunEvent(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        execution_generation=execution_generation,
        kind=kind,
        node_id=node_id,
        node_visit_id=node_visit_id,
        attempt=attempt,
        occurred_at=_utc(occurred_at),
        payload=_freeze_mapping(payload),
    )


def _event_from_dict(value: dict[str, Any], *, assigned_sequence: int) -> RunEvent:
    occurred_at = value["occurredAt"]
    if isinstance(occurred_at, str):
        occurred_at = datetime.fromisoformat(occurred_at)
    return create_run_event(
        event_id=str(value["eventId"]),
        run_id=str(value["runId"]),
        sequence=int(value.get("sequence", assigned_sequence)),
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


def event_identity_digest(event: RunEvent) -> str:
    value = {
        "eventId": event.event_id,
        "runId": event.run_id,
        "executionGeneration": event.execution_generation,
        "kind": event.kind,
        "nodeId": event.node_id,
        "nodeVisitId": event.node_visit_id,
        "attempt": event.attempt,
        "occurredAt": _utc(event.occurred_at).isoformat(),
        "payload": thaw_json(event.payload),
    }
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(
        {str(key): _freeze_json(item) for key, item in value.items()}
    )


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
