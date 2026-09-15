from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class WorkflowPreparedContentRow(Base):
    __tablename__ = "workflow_prepared_contents"
    __table_args__ = (
        Index(
            "ix_workflow_prepared_contents_workflow_created",
            "workflow_id",
            "created_at",
        ),
        CheckConstraint(
            "source_revision IS NULL OR source_revision >= 1",
            name="ck_workflow_prepared_source_revision",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    prepare_operation_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False
    )
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_revision: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict] = mapped_column(JSON, nullable=False)
    execution_plan: Mapped[dict] = mapped_column(JSON, nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(80), nullable=False)
    capability_requirements: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class WorkflowRunRow(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_workflow_runs_prepared_status", "prepared_content_id", "status"),
        CheckConstraint(
            "status IN ('queued','running','waiting_manual','resume_queued',"
            "'finishing','stopping','reconciling','succeeded','failed',"
            "'cancelled','timed_out','interrupted')",
            name="ck_workflow_runs_status",
        ),
        CheckConstraint(
            "status_revision >= 1 AND execution_generation >= 0 AND last_sequence >= 0",
            name="ck_workflow_runs_revisions",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_request_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    prepared_content_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_prepared_contents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    input_snapshot_ref: Mapped[dict | None] = mapped_column(JSON)
    resource_request: Mapped[dict] = mapped_column(JSON, nullable=False)
    capability_bindings: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    status_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    last_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[dict | None] = mapped_column(JSON)


class WorkflowRunEventRow(Base):
    __tablename__ = "workflow_run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "event_id", name="uq_workflow_run_event_id"),
        CheckConstraint("sequence >= 1", name="ck_workflow_run_event_sequence"),
        CheckConstraint(
            "execution_generation >= 0",
            name="ck_workflow_run_event_generation",
        ),
        CheckConstraint(
            "attempt IS NULL OR attempt >= 1",
            name="ck_workflow_run_event_attempt",
        ),
    )

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    execution_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    node_id: Mapped[str | None] = mapped_column(String(120))
    node_visit_id: Mapped[str | None] = mapped_column(String(120))
    attempt: Mapped[int | None] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class WorkflowRunArtifactRow(Base):
    __tablename__ = "workflow_run_artifacts"
    __table_args__ = (
        UniqueConstraint("run_id", "ordinal", name="uq_workflow_artifact_ordinal"),
        Index("ix_workflow_artifacts_node", "run_id", "node_id", "ordinal"),
        Index(
            "ix_workflow_artifacts_execution",
            "run_id",
            "execution_id",
            "ordinal",
        ),
        Index("ix_workflow_artifacts_purpose", "run_id", "purpose", "ordinal"),
    )

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    node_id: Mapped[str] = mapped_column(String(120), nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False)
