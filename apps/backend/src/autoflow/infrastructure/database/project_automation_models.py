from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class ProjectAutomationRow(Base):
    __tablename__ = "project_automations"
    __table_args__ = (
        UniqueConstraint("workflow_id", name="uq_project_automations_workflow"),
        UniqueConstraint(
            "project_id", "name_key", name="uq_project_automations_project_name"
        ),
        Index("ix_project_automations_project_updated", "project_id", "updated_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_documents.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_key: Mapped[str] = mapped_column(Text, nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    management_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    input_plan: Mapped[dict] = mapped_column(JSON, nullable=False)
    parameter_schema: Mapped[list] = mapped_column(JSON, nullable=False)
    environment_policy: Mapped[dict] = mapped_column(JSON, nullable=False)
    run_policy: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
