"""Persistence of project tables, generations and immutable mutation facts."""

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class DataTableRow(Base):
    __tablename__ = "project_data_tables"
    __table_args__ = (
        sa.UniqueConstraint("project_id", "id", name="uq_project_data_table_scope"),
        sa.ForeignKeyConstraint(
            ["project_id", "id", "current_generation"],
            [
                "project_data_generations.project_id",
                "project_data_generations.table_id",
                "project_data_generations.id",
            ],
            name="fk_project_data_current_generation",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint(
            "project_id", "name_key", name="uq_project_data_table_name"
        ),
        sa.CheckConstraint(
            "table_revision >= 1", name="ck_project_data_table_revision"
        ),
        sa.CheckConstraint(
            "source_kind IN ('local','excel','sheets','unconfigured')",
            name="ck_project_data_source_kind",
        ),
        sa.Index("ix_project_data_tables_directory", "project_id", "updated_at", "id"),
    )
    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    name_key: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    source_kind: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    current_generation: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    table_revision: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    identity: Mapped[dict[str, Any]] = mapped_column(sa.JSON(), nullable=False)
    slot_definitions: Mapped[list[dict[str, Any]]] = mapped_column(
        sa.JSON(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )


class DataGenerationRow(Base):
    __tablename__ = "project_data_generations"
    __table_args__ = (
        sa.UniqueConstraint(
            "project_id", "table_id", "id", name="uq_project_data_generation_scope"
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "table_id"],
            ["project_data_tables.project_id", "project_data_tables.id"],
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    table_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    identity: Mapped[dict[str, Any]] = mapped_column(sa.JSON(), nullable=False)
    source: Mapped[dict[str, Any]] = mapped_column(sa.JSON(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )


class DataFieldRow(Base):
    __tablename__ = "project_data_fields"
    __table_args__ = (
        sa.UniqueConstraint(
            "dataset_generation", "key", name="uq_project_data_field_key"
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "table_id", "dataset_generation"],
            [
                "project_data_generations.project_id",
                "project_data_generations.table_id",
                "project_data_generations.id",
            ],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "type IN ('string','number','boolean','date')",
            name="ck_project_data_field_type",
        ),
        sa.CheckConstraint(
            "field_revision >= 1", name="ck_project_data_field_revision"
        ),
    )
    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    table_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    dataset_generation: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    key: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    required: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False)
    writable: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False)
    formula: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False)
    validation: Mapped[dict[str, Any]] = mapped_column(sa.JSON(), nullable=False)
    field_revision: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    position: Mapped[int] = mapped_column(sa.Integer(), nullable=False)


class DataStatusRow(Base):
    __tablename__ = "project_data_statuses"
    __table_args__ = (
        sa.UniqueConstraint(
            "project_id", "table_id", "id", name="uq_project_data_status_scope"
        ),
        sa.UniqueConstraint("table_id", "name_key", name="uq_project_data_status_name"),
        sa.ForeignKeyConstraint(
            ["project_id", "table_id"],
            ["project_data_tables.project_id", "project_data_tables.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status_revision >= 1", name="ck_project_data_status_revision"
        ),
        sa.CheckConstraint("position >= 0", name="ck_project_data_status_position"),
    )
    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    table_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    name_key: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    color: Mapped[str] = mapped_column(sa.String(7), nullable=False)
    position: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    status_revision: Mapped[int] = mapped_column(sa.Integer(), nullable=False)


class DataRecordRow(Base):
    __tablename__ = "project_data_records"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["project_id", "table_id", "dataset_generation"],
            [
                "project_data_generations.project_id",
                "project_data_generations.table_id",
                "project_data_generations.id",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "table_id", "status_id"],
            [
                "project_data_statuses.project_id",
                "project_data_statuses.table_id",
                "project_data_statuses.id",
            ],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "key_type IN ('text','integer','uuid')", name="ck_project_data_key_type"
        ),
        sa.CheckConstraint(
            "content_revision >= 1 AND status_revision >= 1 AND link_revision >= 1",
            name="ck_project_data_record_revisions",
        ),
        sa.Index(
            "ix_project_data_records_status",
            "dataset_generation",
            "deleted",
            "status_id",
            "key_type",
            "key_value",
        ),
        sa.Index(
            "ix_project_data_records_updated",
            "dataset_generation",
            "deleted",
            "updated_at",
        ),
    )
    project_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    table_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    dataset_generation: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    key_type: Mapped[str] = mapped_column(sa.String(10), primary_key=True)
    key_value: Mapped[str] = mapped_column(sa.Text(), primary_key=True)
    values_json: Mapped[dict[str, Any]] = mapped_column(sa.JSON(), nullable=False)
    record_slots: Mapped[list[dict[str, Any]]] = mapped_column(
        sa.JSON(), nullable=False
    )
    status_id: Mapped[str | None] = mapped_column(sa.String(36))
    current_environment_id: Mapped[str | None] = mapped_column(sa.String(36))
    content_revision: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    status_revision: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    link_revision: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    deleted: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )


class DataChangeRow(Base):
    __tablename__ = "project_data_changes"
    __table_args__ = (
        sa.UniqueConstraint(
            "operation_id", "sequence", name="uq_project_data_change_operation"
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "operation_id"],
            ["project_operations.project_id", "project_operations.id"],
            ondelete="RESTRICT",
        ),
        sa.Index("ix_project_data_changes_project", "project_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    operation_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    sequence: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    resource: Mapped[dict[str, Any]] = mapped_column(sa.JSON(), nullable=False)
    origin: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON())
    after: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON())
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )


class DataImpactRow(Base):
    __tablename__ = "project_data_impacts"
    __table_args__ = ({"sqlite_autoincrement": True},)
    id: Mapped[int] = mapped_column(sa.Integer(), primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    target: Mapped[dict[str, Any]] = mapped_column(sa.JSON(), nullable=False)
    change_digest: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    expected_revisions: Mapped[dict[str, Any]] = mapped_column(
        sa.JSON(), nullable=False
    )
    facts_digest: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    report: Mapped[dict[str, Any]] = mapped_column(sa.JSON(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
