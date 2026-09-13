"""ORM facts for controlled project Excel jobs; migration registration is external."""

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class ProjectFileSelectionRow(Base):
    __tablename__ = "project_file_selections"
    token_hash: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    path: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    project_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    window_id: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    window_token_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    workspace_id: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    instance_id: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class ProjectExcelInspectionRow(Base):
    __tablename__ = "project_excel_inspections"
    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.String(36), nullable=False, index=True)
    selection_token_hash: Mapped[str] = mapped_column(
        sa.String(64), nullable=False, unique=True
    )
    path: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    fingerprint: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    window_id: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    window_token_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    snapshot: Mapped[dict[str, Any]] = mapped_column(sa.JSON(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )


class ProjectExcelInspectionJobRow(Base):
    __tablename__ = "project_excel_inspection_jobs"
    operation_id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(
        sa.String(36), nullable=False, unique=True
    )
    project_id: Mapped[str] = mapped_column(sa.String(36), nullable=False, index=True)
    path: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    selection_token_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    window_id: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    window_token_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    state: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    claim_token: Mapped[str | None] = mapped_column(sa.String(36))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )


class ProjectExcelImportJobRow(Base):
    __tablename__ = "project_excel_import_jobs"
    operation_id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.String(36), nullable=False, index=True)
    table_id: Mapped[str | None] = mapped_column(sa.String(36))
    inspection_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    target_generation: Mapped[str] = mapped_column(
        sa.String(36), nullable=False, unique=True
    )
    action: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    request: Mapped[dict[str, Any]] = mapped_column(sa.JSON(), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    claim_token: Mapped[str | None] = mapped_column(sa.String(36))
    candidate_count: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )


class ProjectExcelExportJobRow(Base):
    __tablename__ = "project_excel_export_jobs"
    operation_id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.String(36), nullable=False, index=True)
    table_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    dataset_generation: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    selection_token_hash: Mapped[str] = mapped_column(
        sa.String(64), nullable=False, unique=True
    )
    path: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    window_id: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    window_token_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    request: Mapped[dict[str, Any]] = mapped_column(sa.JSON(), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    claim_token: Mapped[str | None] = mapped_column(sa.String(36))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )


class ProjectExcelPublicationRow(Base):
    __tablename__ = "project_excel_publications"
    operation_id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    path: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    digest: Mapped[str | None] = mapped_column(sa.String(64))
    size_bytes: Mapped[int | None] = mapped_column(sa.Integer())
    record_count: Mapped[int | None] = mapped_column(sa.Integer())
    filename: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
