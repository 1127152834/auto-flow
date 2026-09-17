from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class WorkflowDocumentOperationRow(Base):
    __tablename__ = "workflow_document_operations"
    __table_args__ = (
        Index(
            "ix_workflow_document_operations_workflow_created",
            "workflow_id",
            "created_at",
        ),
    )

    save_operation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
