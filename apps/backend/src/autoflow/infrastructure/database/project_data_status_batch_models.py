from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from autoflow.infrastructure.database.models import Base


class DataStatusBatchRow(Base):
    __tablename__ = "project_data_status_batches"
    operation_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("project_operations.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    table_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    status_id: Mapped[str | None] = mapped_column(sa.String(36))
    request: Mapped[dict[str, Any]] = mapped_column(sa.JSON(), nullable=False)
    block_size: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(
        sa.Boolean(), nullable=False, default=False
    )


class DataStatusBatchBlockRow(Base):
    __tablename__ = "project_data_status_batch_blocks"
    operation_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("project_data_status_batches.operation_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    block_index: Mapped[int] = mapped_column(sa.Integer(), primary_key=True)
    targets: Mapped[list[dict[str, Any]]] = mapped_column(sa.JSON(), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    blockers: Mapped[list[dict[str, Any]]] = mapped_column(sa.JSON(), nullable=False)
    committed_revisions: Mapped[list[dict[str, Any]]] = mapped_column(
        sa.JSON(), nullable=False
    )
