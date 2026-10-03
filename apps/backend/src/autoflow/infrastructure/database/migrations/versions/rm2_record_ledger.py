"""Record processing ledger and primary processing input (remediation M2 Task 1).

Re-entrant data steps:
- an automation with exactly one required input gets that input as its
  ``processingInputId``; several required inputs stay unset and are reported
  (new batches are refused until the user chooses);
- every project task whose run ended with an unknown outcome becomes a
  ``needs_review`` ledger entry for its frozen primary record, so upgrading
  cannot forget unverified runs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "rm2_record_ledger"
down_revision = "rm1_app_settings"
branch_labels = None
depends_on = None

UNKNOWN_CODE = "WORKFLOW_RESULT_UNKNOWN"


def upgrade() -> None:
    op.create_table(
        "automation_record_ledger",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "automation_id",
            sa.String(36),
            sa.ForeignKey("project_automations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("processing_input_id", sa.String(36), nullable=False),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("table_id", sa.String(36), nullable=False),
        sa.Column("dataset_generation", sa.String(36), nullable=False),
        sa.Column("key_type", sa.String(16), nullable=False),
        sa.Column("key_value", sa.Text(), nullable=False),
        sa.Column("identity_namespace", sa.Text(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("processing_cycle", sa.Integer(), nullable=False),
        sa.Column("cycle_attempts", sa.Integer(), nullable=False),
        sa.Column("last_outcome", sa.String(24), nullable=True),
        sa.Column("last_error", sa.JSON(), nullable=True),
        sa.Column("last_task_id", sa.String(36), nullable=True),
        sa.Column("last_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_eligible_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("review", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "automation_id",
            "processing_input_id",
            "project_id",
            "table_id",
            "dataset_generation",
            "key_type",
            "key_value",
            "identity_namespace",
            name="uq_automation_record_ledger_scope",
        ),
        sa.CheckConstraint(
            "state IN ('pending','succeeded','failed_retryable','quarantined','needs_review','skipped')",
            name="ck_automation_record_ledger_state",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND processing_cycle >= 1 AND cycle_attempts >= 0 AND revision >= 1",
            name="ck_automation_record_ledger_counts",
        ),
    )
    op.create_index(
        "ix_automation_record_ledger_state",
        "automation_record_ledger",
        ["automation_id", "state", "next_eligible_at"],
    )
    op.create_table(
        "project_batch_units",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(36),
            sa.ForeignKey("project_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "ledger_id",
            sa.String(36),
            sa.ForeignKey("automation_record_ledger.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "first_task_id",
            sa.String(36),
            sa.ForeignKey("project_tasks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("batch_id", "ledger_id", name="uq_project_batch_units_unit"),
    )
    op.create_index("ix_project_batch_units_ledger", "project_batch_units", ["ledger_id"])
    connection = op.get_bind()
    backfill_processing_inputs(connection)
    gate_unknown_runs(connection, datetime.now(UTC))


def downgrade() -> None:
    op.drop_index("ix_project_batch_units_ledger", table_name="project_batch_units")
    op.drop_table("project_batch_units")
    op.drop_index("ix_automation_record_ledger_state", table_name="automation_record_ledger")
    op.drop_table("automation_record_ledger")


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def single_required_input(plan: Any) -> str | None:
    if not isinstance(plan, dict):
        return None
    chosen = plan.get("processingInputId")
    if isinstance(chosen, str):
        return chosen
    required = [
        item.get("inputId")
        for item in plan.get("inputs", [])
        if isinstance(item, dict) and item.get("required") is True
    ]
    return required[0] if len(required) == 1 and isinstance(required[0], str) else None


def backfill_processing_inputs(connection: sa.Connection) -> None:
    rows = connection.execute(sa.text("SELECT id, input_plan FROM project_automations")).all()
    for automation_id, raw in rows:
        plan = _json(raw)
        if not isinstance(plan, dict) or "processingInputId" in plan:
            continue
        chosen = single_required_input(plan)
        if chosen is None:
            continue
        connection.execute(
            sa.text("UPDATE project_automations SET input_plan = :plan WHERE id = :id"),
            {"plan": json.dumps({**plan, "processingInputId": chosen}, ensure_ascii=False), "id": automation_id},
        )


def gate_unknown_runs(connection: sa.Connection, now: datetime) -> None:
    rows = connection.execute(
        sa.text(
            "SELECT t.id, t.run_id, b.automation_id, b.project_id, b.frozen_request, s.inputs, r.error "
            "FROM project_tasks t "
            "JOIN project_batches b ON b.id = t.batch_id "
            "JOIN project_workflow_runs r ON r.id = t.run_id "
            "JOIN project_task_input_snapshots s ON s.task_id = t.id "
            "WHERE r.status = 'interrupted' ORDER BY t.created_at, t.id"
        )
    ).all()
    for task_id, run_id, automation_id, project_id, frozen, inputs, error in rows:
        if (_json(error) or {}).get("code") != UNKNOWN_CODE:
            continue
        frozen_plan = ((_json(frozen) or {}).get("automation") or {}).get("inputPlan")
        processing_input = single_required_input(frozen_plan)
        selected = next(
            (item for item in _json(inputs) or [] if isinstance(item, dict) and item.get("inputId") == processing_input),
            None,
        )
        if processing_input is None or selected is None or not isinstance(selected.get("recordRef"), dict):
            continue
        ref = selected["recordRef"]
        key = ref.get("recordKey") or {}
        namespace = _lease_namespace(connection, selected.get("leaseId"))
        scope = {
            "automation_id": automation_id,
            "processing_input_id": processing_input,
            "project_id": ref.get("projectId") or project_id,
            "table_id": ref.get("tableId"),
            "dataset_generation": ref.get("datasetGeneration"),
            "key_type": key.get("type"),
            "key_value": key.get("value"),
            "identity_namespace": namespace,
        }
        if any(value is None for value in scope.values()):
            continue
        exists = connection.execute(
            sa.text(
                "SELECT 1 FROM automation_record_ledger WHERE automation_id = :automation_id "
                "AND processing_input_id = :processing_input_id AND project_id = :project_id "
                "AND table_id = :table_id AND dataset_generation = :dataset_generation "
                "AND key_type = :key_type AND key_value = :key_value "
                "AND identity_namespace = :identity_namespace"
            ),
            scope,
        ).first()
        if exists is not None:
            continue
        review = {"unknown": {"taskId": task_id, "runId": run_id, "code": UNKNOWN_CODE, "source": "upgrade"}}
        connection.execute(
            _LEDGER.insert().values(
                **scope,
                id=str(uuid4()),
                state="needs_review",
                attempts=1,
                processing_cycle=1,
                cycle_attempts=1,
                last_outcome="unknown",
                last_error={"code": UNKNOWN_CODE},
                last_task_id=task_id,
                last_at=now,
                next_eligible_at=None,
                revision=1,
                review=review,
                created_at=now,
                updated_at=now,
            )
        )


_LEDGER = sa.table(
    "automation_record_ledger",
    *(sa.column(name) for name in (
        "id", "automation_id", "processing_input_id", "project_id", "table_id",
        "dataset_generation", "key_type", "key_value", "identity_namespace", "state",
        "attempts", "processing_cycle", "cycle_attempts", "last_outcome", "last_task_id", "revision",
    )),
    sa.column("last_error", sa.JSON()),
    sa.column("review", sa.JSON()),
    sa.column("last_at", sa.DateTime(timezone=True)),
    sa.column("next_eligible_at", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def _lease_namespace(connection: sa.Connection, lease_id: Any) -> str:
    if not isinstance(lease_id, str):
        return ""
    row = connection.execute(
        sa.text("SELECT lease_key FROM project_record_leases WHERE id = :id"), {"id": lease_id}
    ).first()
    try:
        key = json.loads(row[0]) if row is not None else {}
    except (TypeError, ValueError):
        key = {}
    namespace = key.get("identityNamespace") if key.get("source") == "sheets" else None
    return namespace if isinstance(namespace, str) else ""
