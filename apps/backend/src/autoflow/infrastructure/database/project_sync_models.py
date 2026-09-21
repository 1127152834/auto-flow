"""Persistence of Google Sheets connections, bindings and outbound sync facts."""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class SheetsConnectionRow(Base):
    __tablename__ = "project_sheets_connections"
    __table_args__ = (
        sa.CheckConstraint(
            "auth_method IN ('oauth','service_account')",
            name="ck_project_sheets_connection_auth",
        ),
        sa.CheckConstraint(
            "state IN ('available','loginRequired','missing','invalid')",
            name="ck_project_sheets_connection_state",
        ),
        sa.Index("ix_project_sheets_connections_project", "project_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    account_label: Mapped[str] = mapped_column(sa.Text, nullable=False)
    credential_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    auth_method: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    readable: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    writable: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class SheetsBindingRow(Base):
    __tablename__ = "project_sheets_bindings"
    __table_args__ = (
        sa.CheckConstraint(
            "binding_epoch >= 1", name="ck_project_sheets_binding_epoch"
        ),
        sa.CheckConstraint("sheet_id >= 0", name="ck_project_sheets_binding_sheet_id"),
        sa.Index("ix_project_sheets_bindings_source", "spreadsheet_id", "sheet_id"),
        sa.Index("ix_project_sheets_bindings_project", "project_id", "updated_at"),
    )
    table_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("project_data_tables.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    connection_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("project_sheets_connections.id", ondelete="RESTRICT"),
        nullable=False,
    )
    spreadsheet_id: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    sheet_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    spreadsheet_title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    sheet_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    binding_epoch: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    identity_strategy: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    identity_verification: Mapped[dict | None] = mapped_column(sa.JSON)
    mapping: Mapped[list[dict]] = mapped_column(sa.JSON, nullable=False)
    sync_paused: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )


class SyncOperationRow(Base):
    __tablename__ = "project_sync_operations"
    __table_args__ = (
        sa.CheckConstraint(
            "kind IN ('pull','push','reconcile','binding','column','systemIdentity')",
            name="ck_project_sync_operation_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending','sending','verifying','confirmed',"
            "'failed','unknown','paused')",
            name="ck_project_sync_operation_status",
        ),
        sa.CheckConstraint(
            "status_revision >= 1", name="ck_project_sync_operation_status_revision"
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_project_sync_operation_attempts"),
        sa.CheckConstraint(
            "(record_key_type IS NULL) = (record_key IS NULL)",
            name="ck_project_sync_operation_record_key",
        ),
        sa.UniqueConstraint(
            "table_id", "dedupe_key", name="uq_project_sync_operation_dedupe"
        ),
        sa.Index(
            "ix_project_sync_operation_queue", "table_id", "status", "next_attempt_at"
        ),
        sa.Index(
            "ix_project_sync_operation_record",
            "table_id",
            "record_key_type",
            "record_key",
            "target_content_revision",
        ),
    )
    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    table_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("project_data_tables.id", ondelete="RESTRICT"),
        nullable=False,
    )
    operation_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("project_operations.id", ondelete="RESTRICT")
    )
    kind: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    record_key_type: Mapped[str | None] = mapped_column(sa.String(8))
    record_key: Mapped[str | None] = mapped_column(sa.Text)
    binding_epoch: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    target_content_revision: Mapped[int | None] = mapped_column(sa.Integer)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    status_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    request: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    target: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    evidence: Mapped[dict | None] = mapped_column(sa.JSON)
    attempts: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    error: Mapped[dict | None] = mapped_column(sa.JSON)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class SyncRecordMarkRow(Base):
    __tablename__ = "project_sync_record_marks"
    table_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("project_data_tables.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    record_key_type: Mapped[str] = mapped_column(sa.String(8), primary_key=True)
    record_key: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    remote_missing: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    observed: Mapped[dict | None] = mapped_column(sa.JSON)
    remote_seen_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
