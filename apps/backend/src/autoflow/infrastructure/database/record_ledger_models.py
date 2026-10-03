"""Record processing ledger tables (remediation M2 R2-01)."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base

LEDGER_STATE_CHECK = (
    "state IN ('pending','succeeded','failed_retryable','quarantined','needs_review','skipped')"
)


class AutomationRecordLedgerRow(Base):
    __tablename__ = "automation_record_ledger"
    __table_args__ = (
        UniqueConstraint(
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
        CheckConstraint(LEDGER_STATE_CHECK, name="ck_automation_record_ledger_state"),
        CheckConstraint(
            "attempts >= 0 AND processing_cycle >= 1 AND cycle_attempts >= 0 AND revision >= 1",
            name="ck_automation_record_ledger_counts",
        ),
        Index("ix_automation_record_ledger_state", "automation_id", "state", "next_eligible_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    automation_id: Mapped[str] = mapped_column(
        ForeignKey("project_automations.id", ondelete="RESTRICT")
    )
    processing_input_id: Mapped[str] = mapped_column(String(36))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    table_id: Mapped[str] = mapped_column(String(36))
    dataset_generation: Mapped[str] = mapped_column(String(36))
    key_type: Mapped[str] = mapped_column(String(16))
    key_value: Mapped[str] = mapped_column(Text)
    identity_namespace: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(24))
    attempts: Mapped[int] = mapped_column(Integer)
    processing_cycle: Mapped[int] = mapped_column(Integer)
    cycle_attempts: Mapped[int] = mapped_column(Integer)
    last_outcome: Mapped[str | None] = mapped_column(String(24))
    last_error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    last_task_id: Mapped[str | None] = mapped_column(String(36))
    last_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_eligible_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer)
    review: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProjectBatchUnitRow(Base):
    """The primary processing units a batch took in, kept for historical batch counts."""

    __tablename__ = "project_batch_units"
    __table_args__ = (
        UniqueConstraint("batch_id", "ledger_id", name="uq_project_batch_units_unit"),
        Index("ix_project_batch_units_ledger", "ledger_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("project_batches.id", ondelete="RESTRICT")
    )
    ledger_id: Mapped[str] = mapped_column(
        ForeignKey("automation_record_ledger.id", ondelete="RESTRICT")
    )
    first_task_id: Mapped[str] = mapped_column(
        ForeignKey("project_tasks.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
