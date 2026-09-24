from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class AndroidDeviceRow(Base):
    __tablename__ = "android_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_run_id: Mapped[str | None] = mapped_column(String(36))
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class AndroidResourceRow(Base):
    __tablename__ = "android_resources"

    kind: Mapped[str] = mapped_column(String(24), primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class AndroidOperationRow(Base):
    __tablename__ = "android_operations"
    __table_args__ = (UniqueConstraint("workspace_identity", "request_id", name="uq_android_operation_request"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_identity: Mapped[str] = mapped_column(String(255), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    stage_code: Mapped[str] = mapped_column(String(64), nullable=False)
    stage_label: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retry_of: Mapped[str | None] = mapped_column(String(36))
    result_code: Mapped[str | None] = mapped_column(String(64))
    message: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
