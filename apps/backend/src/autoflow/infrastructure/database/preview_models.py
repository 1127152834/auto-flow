"""Run-private preview writes (remediation M2 R2-30)."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class PreviewRecordRow(Base):
    """One record as a preview run sees it; never read by real writes, ledgers or sync."""

    __tablename__ = "project_preview_records"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "table_id", "dataset_generation", "key_type", "key_value",
            name="uq_project_preview_records_identity",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36))
    project_id: Mapped[str] = mapped_column(String(36))
    table_id: Mapped[str] = mapped_column(String(36))
    dataset_generation: Mapped[str] = mapped_column(String(36))
    key_type: Mapped[str] = mapped_column(String(16))
    key_value: Mapped[str] = mapped_column(Text)
    values_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    status_id: Mapped[str | None] = mapped_column(String(36))
    created: Mapped[bool] = mapped_column(Boolean)
    deleted: Mapped[bool] = mapped_column(Boolean)
    revision: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
