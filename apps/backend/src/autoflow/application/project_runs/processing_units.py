"""Processing unit queries and audited manual commands (remediation M2 R2-06).

Every change names one complete unit, carries the revision the person saw and
an idempotency key, and is refused while a Task of this automation still holds
the record. An unknown outcome leaves only through ``resolve``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_runs.ledger import LedgerEntry, LedgerError, LedgerScope
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.domain.projects.models import ProjectOperation
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectRecordLeaseRow,
)
from autoflow.infrastructure.database.projects import _operation, _operation_row
from autoflow.infrastructure.database.record_ledger import SqlAlchemyRecordLedger

KIND = "changeProcessingUnit"
ACTIONS = frozenset({"reset", "skip", "resolve"})
STATES = frozenset({"pending", "succeeded", "failed_retryable", "quarantined", "needs_review", "skipped"})


class ProcessingUnitService:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def list(
        self, project_id: str, automation_id: str, *, state: str | None, after: str | None, limit: int
    ) -> dict[str, Any]:
        if state is not None and state not in STATES:
            raise ProjectRunError("VALIDATION_ERROR", "处理状态无效", 422)
        with self._factory() as session:
            _automation(session, project_id, automation_id)
            page = SqlAlchemyRecordLedger(session).list(automation_id, state=state, after=after, limit=limit + 1)
        items = [unit_view(stored.id, stored.entry) for stored in page[:limit]]
        return {"items": items, "nextAfter": page[limit - 1].id if len(page) > limit else None}

    def command(
        self, project_id: str, automation_id: str, unit_id: str, key: str, action: str, payload: dict[str, Any]
    ) -> tuple[ProjectOperation, dict[str, Any]]:
        expected, reason, decision = _validate(action, payload)
        digest = hashlib.sha256(json.dumps(
            {"kind": KIND, "projectId": project_id, "automationId": automation_id, "unitId": unit_id,
             "action": action, "request": payload},
            sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode()).hexdigest()
        try:
            if str(UUID(key)) != key:
                raise ValueError
        except ValueError as error:
            raise ProjectRunError("VALIDATION_ERROR", "操作身份无效", 422) from error
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            _automation(session, project_id, automation_id)
            ledger = SqlAlchemyRecordLedger(session)
            existing = session.scalar(select(ProjectOperationRow).where(ProjectOperationRow.idempotency_key == key))
            if existing is not None:
                if existing.project_id != project_id or existing.kind != KIND or existing.request_digest != digest:
                    raise ProjectRunError("OPERATION_PAYLOAD_MISMATCH", "同一操作身份已用于其他请求", 409)
                stored = ledger.by_id(automation_id, unit_id)
                if stored is None:
                    raise ProjectRunError("NOT_FOUND", "处理记录不存在", 404)
                return _operation(existing), unit_view(stored.id, stored.entry)
            stored = ledger.by_id(automation_id, unit_id)
            if stored is None:
                raise ProjectRunError("NOT_FOUND", "处理记录不存在", 404)
            if _active(session, stored.entry.scope):
                raise ProjectRunError("PROCESSING_UNIT_ACTIVE", "这条数据正在被任务处理，请等任务结束后再操作", 409)
            now = datetime.now(UTC)
            try:
                if action == "resolve":
                    after = ledger.resolve(stored.entry.scope, expected_revision=expected, decision=str(decision),
                                           reason=reason, now=now)
                elif action == "reset":
                    after = ledger.reset(stored.entry.scope, expected_revision=expected, reason=reason, now=now)
                else:
                    after = ledger.skip(stored.entry.scope, expected_revision=expected, reason=reason, now=now)
            except LedgerError as error:
                raise ProjectRunError(error.code, error.message, error.status,
                                      {"currentRevision": stored.entry.revision}) from error
            view = unit_view(stored.id, after)
            operation = ProjectOperation(
                str(uuid4()), project_id, key, KIND, digest, "succeeded", 1,
                {"type": "automation", "projectId": project_id, "automationId": automation_id},
                None, None, now, now, now,
            )
            session.add(_operation_row(operation))
            session.commit()
            return operation, view


def unit_view(unit_id: str, entry: LedgerEntry) -> dict[str, Any]:
    scope = entry.scope
    return {
        "unitId": unit_id,
        "processingInputId": scope.processing_input_id,
        "recordRef": {
            "projectId": scope.project_id, "tableId": scope.table_id,
            "datasetGeneration": scope.dataset_generation,
            "recordKey": {"type": scope.key_type, "value": scope.key_value},
        },
        "identityNamespace": scope.identity_namespace or None,
        "state": entry.state,
        "attempts": entry.attempts,
        "processingCycle": entry.processing_cycle,
        "cycleAttempts": entry.cycle_attempts,
        "lastOutcome": entry.last_outcome,
        "lastError": entry.last_error,
        "lastTaskId": entry.last_task_id,
        "lastAt": entry.last_at,
        "nextEligibleAt": entry.next_eligible_at,
        "revision": entry.revision,
        "review": entry.review,
    }


def _validate(action: str, payload: dict[str, Any]) -> tuple[int, str, str | None]:
    allowed = {"expectedRevision", "reason"} | ({"decision"} if action == "resolve" else set())
    expected, reason = payload.get("expectedRevision"), payload.get("reason")
    if (
        action not in ACTIONS
        or set(payload) - allowed
        or type(expected) is not int or expected < 1
        or not isinstance(reason, str) or not reason.strip() or len(reason) > 500
        or (action == "resolve" and payload.get("decision") not in {"confirmedSucceeded", "confirmedNotPerformed", "abandon"})
    ):
        raise ProjectRunError("VALIDATION_ERROR", "操作内容无效，请填写原因", 422)
    return expected, reason, payload.get("decision")


def _automation(session: Session, project_id: str, automation_id: str) -> ProjectAutomationRow:
    row = session.get(ProjectAutomationRow, automation_id)
    if row is None or row.project_id != project_id:
        raise ProjectRunError("NOT_FOUND", "自动化不存在", 404)
    return row


def _active(session: Session, scope: LedgerScope) -> bool:
    """A held lease on this record in a batch of the same automation means a Task is still running."""
    leases = session.scalars(
        select(ProjectRecordLeaseRow)
        .join(ProjectBatchRow, ProjectBatchRow.id == ProjectRecordLeaseRow.batch_id)
        .where(
            ProjectBatchRow.automation_id == scope.automation_id,
            ProjectRecordLeaseRow.state.in_(("held", "reconciling")),
        )
    )
    for lease in leases:
        ref = lease.record_ref if isinstance(lease.record_ref, dict) else {}
        key = ref.get("recordKey") or {}
        if (ref.get("tableId"), ref.get("datasetGeneration"), key.get("type"), str(key.get("value"))) == (
            scope.table_id, scope.dataset_generation, scope.key_type, scope.key_value
        ):
            return True
    return False
