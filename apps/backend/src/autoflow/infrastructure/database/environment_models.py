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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class ProjectEnvironmentRow(Base):
    __tablename__ = "project_environments"
    __table_args__ = (
        Index("ix_project_environments_project_updated", "project_id", "updated_at"),
        Index("uq_project_environments_active_name", "project_id", "name_key",
              unique=True, sqlite_where=text("state != 'deleted'")),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_key: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False)
    content_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    current_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    identity_package: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    keep_browser_cache: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("0"))
    created_from_source: Mapped[str] = mapped_column(String, nullable=False)
    created_from_task_id: Mapped[str | None] = mapped_column(String(36))
    unavailable_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProjectEnvironmentInstanceRow(Base):
    __tablename__ = "project_environment_instances"
    __table_args__ = (
        Index(
            "ix_project_environment_instances_project_state",
            "project_id",
            "state",
        ),
        # Remediation M4 S8-1: one unreleased instance per identity (see rm4_instance_identity).
        Index(
            "uq_project_environment_instances_live_identity", "identity_id", unique=True,
            sqlite_where=text("identity_id IS NOT NULL AND state NOT IN ('cleaned', 'retained_unsaved')"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    environment_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_environments.id", ondelete="RESTRICT")
    )
    state: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_content_generation: Mapped[int | None] = mapped_column(Integer)
    instance_use_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    active_task_id: Mapped[str | None] = mapped_column(String(36))
    active_run_id: Mapped[str | None] = mapped_column(String(36))
    maintenance_operation_id: Mapped[str | None] = mapped_column(String(36))
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False)
    identity_package: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    identity_id: Mapped[str | None] = mapped_column(String(36))
    retain_on_release: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProjectEnvironmentOccupancyRow(Base):
    __tablename__ = "project_environment_occupancies"
    environment_id: Mapped[str] = mapped_column(
        ForeignKey("project_environments.id", ondelete="RESTRICT"), primary_key=True
    )
    instance_id: Mapped[str] = mapped_column(
        ForeignKey("project_environment_instances.id", ondelete="RESTRICT"),
        nullable=False,
    )
    holder_kind: Mapped[str] = mapped_column(String, nullable=False)
    holder_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProjectEnvironmentSaveRow(Base):
    __tablename__ = "project_environment_saves"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    instance_id: Mapped[str] = mapped_column(
        ForeignKey("project_environment_instances.id", ondelete="RESTRICT"),
        nullable=False,
    )
    environment_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_environments.id", ondelete="RESTRICT")
    )
    mode: Mapped[str] = mapped_column(String, nullable=False)
    phase: Mapped[str] = mapped_column(String, nullable=False)
    expected_content_generation: Mapped[int | None] = mapped_column(Integer)
    published_content_generation: Mapped[int | None] = mapped_column(Integer)
    candidate_digest: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(Text)
    operation_id: Mapped[str] = mapped_column(
        ForeignKey("project_operations.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProjectEndOperationRow(Base):
    __tablename__ = "project_end_operations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    phase: Mapped[str] = mapped_column(String, nullable=False)
    retain_environment: Mapped[bool] = mapped_column(Boolean, nullable=False)
    save_operation_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_environment_saves.id", ondelete="RESTRICT")
    )
    intended_result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    targets: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    association_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    operation_id: Mapped[str] = mapped_column(
        ForeignKey("project_operations.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProjectManualItemRow(Base):
    __tablename__ = "project_manual_items"
    __table_args__ = (
        Index("ix_project_manual_items_project_status", "project_id", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    instance_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_environment_instances.id", ondelete="RESTRICT")
    )
    checkpoint_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    status_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    allowed_targets: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    resume_started: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
