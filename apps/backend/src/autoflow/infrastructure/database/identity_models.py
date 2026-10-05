from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class SeedRegistryRow(Base):
    """Every fingerprint seed ever handed out (remediation M4 R4-02); a value is registered once."""

    __tablename__ = "seed_registry"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    seed_value: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    # Only migration may let several identities share one registration (older duplicate seeds).
    legacy_shared: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IdentityRow(Base):
    __tablename__ = "identities"
    __table_args__ = (
        Index("uq_identities_project_name", "project_id", "name_key", unique=True),
        Index("ix_identities_seed", "seed_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_key: Mapped[str] = mapped_column(Text, nullable=False)
    template_profile_id: Mapped[str | None] = mapped_column(String(36))
    seed_id: Mapped[str] = mapped_column(ForeignKey("seed_registry.id", ondelete="RESTRICT"), nullable=False)
    region: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    proxy_binding: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    environment_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_environments.id", ondelete="RESTRICT"), unique=True,
    )
    health: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
