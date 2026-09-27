from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
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
        ForeignKey("project_workflow_prepared_contents.id", ondelete="RESTRICT")
    )
    automation_revision: Mapped[int] = mapped_column(Integer)
    workflow_revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    status_revision: Mapped[int] = mapped_column(Integer)
    frozen_request: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_gate_state: Mapped[str] = mapped_column(
        String, server_default="closed", default="closed"
    )
    selection_outcome: Mapped[dict | None] = mapped_column(JSON)


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
        ForeignKey("project_workflow_runs.id", ondelete="RESTRICT"), unique=True
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


class ProjectRecordLeaseRow(Base):
    __tablename__ = "project_record_leases"
    __table_args__ = (
        UniqueConstraint(
            "task_id", "lease_key", name="uq_project_record_leases_task_key"
        ),
        Index(
            "uq_project_record_leases_active_key",
            "lease_key",
            unique=True,
            sqlite_where=text("state IN ('held', 'reconciling')"),
        ),
        Index("ix_project_record_leases_task", "project_id", "task_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lease_key: Mapped[str] = mapped_column(String(1024))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT")
    )
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("project_batches.id", ondelete="RESTRICT")
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("project_tasks.id", ondelete="RESTRICT")
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("project_workflow_runs.id", ondelete="RESTRICT")
    )
    record_ref: Mapped[dict] = mapped_column(JSON)
    lease_generation: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectTaskRecordCursorRow(Base):
    __tablename__ = "project_task_record_cursors"
    __table_args__ = (
        UniqueConstraint(
            "task_id", "record_ref", name="uq_project_task_record_cursors_ref"
        ),
        Index("ix_project_task_record_cursors_task", "task_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("project_tasks.id", ondelete="RESTRICT")
    )
    lease_id: Mapped[str] = mapped_column(
        ForeignKey("project_record_leases.id", ondelete="RESTRICT")
    )
    record_ref: Mapped[dict] = mapped_column(JSON)
    content_revision: Mapped[int] = mapped_column(Integer)
    status_revision: Mapped[int] = mapped_column(Integer)
    link_revision: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProjectTaskRecordReadRow(Base):
    """Immutable evidence that a task observed an exact record snapshot.

    A read never grants a lease.  Later workflow writes use this evidence to
    prove that an exact RecordRef came from an allowed query before attempting
    the non-blocking dynamic lease transaction.
    """

    __tablename__ = "project_task_record_reads"
    __table_args__ = (
        Index("ix_project_task_record_reads_task", "task_id", "created_at"),
        Index(
            "ix_project_task_record_reads_ref",
            "project_id",
            "table_id",
            "dataset_generation",
            "key_type",
            "key_value",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT")
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("project_tasks.id", ondelete="RESTRICT")
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("project_workflow_runs.id", ondelete="RESTRICT")
    )
    execution_generation: Mapped[int] = mapped_column(Integer)
    table_id: Mapped[str] = mapped_column(String(36))
    dataset_generation: Mapped[str] = mapped_column(String(36))
    key_type: Mapped[str] = mapped_column(String)
    key_value: Mapped[str] = mapped_column(String)
    field_ids: Mapped[list] = mapped_column(JSON)
    read_purpose: Mapped[str] = mapped_column(String)
    content_revision: Mapped[int] = mapped_column(Integer)
    status_revision: Mapped[int] = mapped_column(Integer)
    link_revision: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProjectTaskRecordQueryRow(Base):
    """Immutable evidence and identity for one frozen query result."""

    __tablename__ = "project_task_record_queries"
    __table_args__ = (
        Index("ix_project_task_record_queries_task", "task_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT")
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("project_tasks.id", ondelete="RESTRICT")
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("project_workflow_runs.id", ondelete="RESTRICT")
    )
    execution_generation: Mapped[int] = mapped_column(Integer)
    table_id: Mapped[str] = mapped_column(String(36))
    dataset_generation: Mapped[str] = mapped_column(String(36))
    request_digest: Mapped[str] = mapped_column(String(64))
    request_payload: Mapped[dict] = mapped_column(JSON)
    result_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProjectTaskRecordQueryItemRow(Base):
    """One ordered record snapshot in a frozen task query."""

    __tablename__ = "project_task_record_query_items"
    query_id: Mapped[str] = mapped_column(
        ForeignKey("project_task_record_queries.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
