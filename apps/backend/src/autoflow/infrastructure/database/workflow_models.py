from __future__ import annotations

from datetime import datetime
from typing import Any

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


class WorkflowDocumentRow(Base):
    __tablename__ = "workflow_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    document: Mapped[dict] = mapped_column(JSON, nullable=False)
    layout: Mapped[dict] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class WorkflowDocumentRequestRow(Base):
    __tablename__ = "workflow_document_requests"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    response: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class WorkflowCustomModuleRow(Base):
    __tablename__ = "workflow_custom_modules"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    dependency_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class WorkflowCustomModuleRequestRow(Base):
    __tablename__ = "workflow_custom_module_requests"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    module_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    response: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class WorkflowRunRow(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[str] = mapped_column(String(40), nullable=False)
    active_slot: Mapped[int | None] = mapped_column(Integer, unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class WorkflowRunEventRow(Base):
    __tablename__ = "workflow_run_events"

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), primary_key=True
    )
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class WorkflowRunArtifactRow(Base):
    __tablename__ = "workflow_run_artifacts"
    __table_args__ = (
        UniqueConstraint("run_id", "ordinal", name="uq_workflow_artifact_ordinal"),
        Index("ix_workflow_artifacts_node", "run_id", "node_id", "ordinal"),
        Index("ix_workflow_artifacts_execution", "run_id", "execution_id", "ordinal"),
        Index("ix_workflow_artifacts_purpose", "run_id", "purpose", "ordinal"),
    )

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), primary_key=True
    )
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    node_id: Mapped[str] = mapped_column(String(120), nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(120))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False, default="result")
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class WorkflowDebugCommandRow(Base):
    __tablename__ = "workflow_debug_commands"

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), primary_key=True
    )
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class WorkflowAssistantSessionRow(Base):
    __tablename__ = "workflow_assistant_sessions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowAssistantCommandRow(Base):
    __tablename__ = "workflow_assistant_commands"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("workflow_assistant_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
