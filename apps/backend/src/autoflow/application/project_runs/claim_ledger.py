"""Processing records at claim time (remediation M2 Task 4, R2-03/R2-05).

The candidate query already skips ineligible primary rows; the commit repeats
the check under the write lock so a manual skip or resolve cannot race a claim,
and records which primary units the batch took in. Batch row limits count those
units, so retrying one unit never uses up the limit.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from autoflow.domain.project_automations.rules import processing_input
from autoflow.domain.project_runs.input_selection import SheetsLeaseKey
from autoflow.domain.project_runs.ledger import (
    LEGACY_CLAIM_MODE,
    claim_eligibility,
    scope_for,
)
from autoflow.infrastructure.database.project_claims import LedgerClaimPolicy
from autoflow.infrastructure.database.record_ledger import SqlAlchemyRecordLedger
from autoflow.infrastructure.database.record_ledger_models import (
    AutomationRecordLedgerRow,
    ProjectBatchUnitRow,
)


def batch_ledger_policy(automation_id: str, frozen_request: dict[str, Any], now: datetime) -> LedgerClaimPolicy | None:
    if frozen_request.get("executionMode") == "previewWrites":
        return None  # R2-30: a preview never consumes or gates processing records
    automation = frozen_request.get("automation") or {}
    chosen = processing_input(automation.get("inputPlan") or {})
    if not isinstance(chosen, str):
        return None
    mode = (automation.get("runPolicy") or {}).get("claimMode") or LEGACY_CLAIM_MODE
    return LedgerClaimPolicy(automation_id, chosen, mode, now)


def batch_unit_count(session: Session, batch_id: str) -> int:
    return int(session.scalar(
        select(func.count()).select_from(ProjectBatchUnitRow).where(ProjectBatchUnitRow.batch_id == batch_id)
    ) or 0)


def is_legacy(policy: LedgerClaimPolicy | None) -> bool:
    return policy is not None and policy.mode == LEGACY_CLAIM_MODE


def batch_waiting_until(session: Session, batch_id: str, now: datetime) -> datetime | None:
    """The next retry due for a unit this batch already took in (R2-05: wait, do not complete early)."""
    value = session.scalar(
        select(func.min(AutomationRecordLedgerRow.next_eligible_at))
        .join(ProjectBatchUnitRow, ProjectBatchUnitRow.ledger_id == AutomationRecordLedgerRow.id)
        .where(
            ProjectBatchUnitRow.batch_id == batch_id,
            AutomationRecordLedgerRow.state == "failed_retryable",
            AutomationRecordLedgerRow.next_eligible_at.is_not(None),
        )
    )
    return value


def batch_retry_refs(session: Session, batch_id: str) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(AutomationRecordLedgerRow)
        .join(ProjectBatchUnitRow, ProjectBatchUnitRow.ledger_id == AutomationRecordLedgerRow.id)
        .where(ProjectBatchUnitRow.batch_id == batch_id, AutomationRecordLedgerRow.state == "failed_retryable")
        .order_by(AutomationRecordLedgerRow.id)
    )
    return [
        {
            "projectId": row.project_id, "tableId": row.table_id, "datasetGeneration": row.dataset_generation,
            "recordKey": {"type": row.key_type, "value": row.key_value},
        }
        for row in rows
    ]


def _primary_scope(policy: LedgerClaimPolicy, selection: Any) -> Any:
    selected = next((item for item in selection.inputs if item.input_id == policy.processing_input_id), None)
    if selected is None:
        return None
    namespace = selected.lease_key.identity_namespace if isinstance(selected.lease_key, SheetsLeaseKey) else None
    return scope_for(policy.automation_id, policy.processing_input_id, selected.record_ref, namespace)


def quarantine_bad_primary(session: Session, policy: LedgerClaimPolicy, selection: Any, now: datetime) -> bool:
    """R2-17: isolate the primary row whose own values are invalid; reference rows keep the old gate."""
    bad = next((item for item in getattr(selection, "issue_inputs", ()) if item.input_id == policy.processing_input_id), None)
    if bad is None:
        return False
    namespace = bad.lease_key.identity_namespace if isinstance(bad.lease_key, SheetsLeaseKey) else None
    scope = scope_for(policy.automation_id, policy.processing_input_id, bad.record_ref, namespace)
    detail = dict(selection.issue_details).get(policy.processing_input_id, "")
    SqlAlchemyRecordLedger(session).quarantine(
        scope, {"code": "INPUT_VALUE_INVALID", "message": f"这条数据的取值不符合字段要求，已停止处理：{detail}"}, now
    )
    return True


def primary_eligible(session: Session, policy: LedgerClaimPolicy, selection: Any) -> bool:
    scope = _primary_scope(policy, selection)
    if scope is None:
        return True
    return claim_eligibility(SqlAlchemyRecordLedger(session).get(scope), policy.mode, policy.now) == "eligible"


def admit_primary(
    session: Session, policy: LedgerClaimPolicy, selection: Any, batch_id: str, task_id: str, now: datetime
) -> bool:
    """Record the (already rechecked) primary unit as a unit of this batch."""
    scope = _primary_scope(policy, selection)
    if scope is None:
        return True
    ledger = SqlAlchemyRecordLedger(session)
    ledger.ensure(scope, now)
    ledger.add_batch_unit(batch_id, scope, task_id, now)
    return True
