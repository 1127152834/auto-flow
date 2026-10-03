"""Automation schedules and their triggers (remediation M2 R2-25/R2-26)."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
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


class AutomationScheduleRow(Base):
    __tablename__ = "automation_schedules"
    __table_args__ = (Index("ix_automation_schedules_automation", "automation_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    automation_id: Mapped[str] = mapped_column(ForeignKey("project_automations.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(16))
    cron: Mapped[str | None] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64))
    overlap: Mapped[str] = mapped_column(String(16))
    missed: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(Boolean)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    max_tasks: Mapped[int | None] = mapped_column(Integer)
    concurrency: Mapped[int] = mapped_column(Integer)
    webhook_secret_hash: Mapped[str | None] = mapped_column(String(64))
    last_fire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AutomationScheduleTriggerRow(Base):
    """One planned time or webhook event; its key makes every trigger start at most once."""

    __tablename__ = "automation_schedule_triggers"
    __table_args__ = (
        UniqueConstraint("schedule_id", "trigger_key", name="uq_automation_schedule_triggers_key"),
        Index("ix_automation_schedule_triggers_schedule", "schedule_id", "received_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    schedule_id: Mapped[str] = mapped_column(ForeignKey("automation_schedules.id", ondelete="CASCADE"))
    trigger_key: Mapped[str] = mapped_column(Text)
    planned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(16))
    batch_id: Mapped[str | None] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text)
