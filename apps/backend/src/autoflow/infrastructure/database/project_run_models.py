from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class ProjectBatchRow(Base):
    __tablename__ = "project_batches"
    __table_args__ = (
        Index("ix_project_batches_project_created", "project_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT")
    )
    automation_id: Mapped[str] = mapped_column(
        ForeignKey("project_automations.id", ondelete="RESTRICT")
    )
    start_operation_id: Mapped[str] = mapped_column(
        ForeignKey("project_operations.id", ondelete="RESTRICT"), unique=True
    )
    prepared_content_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_prepared_contents.id", ondelete="RESTRICT")
    )
    automation_revision: Mapped[int] = mapped_column(Integer)
    workflow_revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    status_revision: Mapped[int] = mapped_column(Integer)
    frozen_request: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectTaskRow(Base):
    __tablename__ = "project_tasks"
    __table_args__ = (
        UniqueConstraint("batch_id", "ordinal", name="uq_project_tasks_batch_ordinal"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT")
    )
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("project_batches.id", ondelete="RESTRICT")
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"), unique=True
    )
    run_request_id: Mapped[str] = mapped_column(String(36), unique=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProjectTaskInputSnapshotRow(Base):
    __tablename__ = "project_task_input_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("project_tasks.id", ondelete="RESTRICT"), unique=True
    )
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("project_batches.id", ondelete="RESTRICT")
    )
    parameters: Mapped[dict] = mapped_column(JSON)
    inputs: Mapped[list] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
