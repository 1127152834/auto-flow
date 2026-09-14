"""Persist idempotent workflow document save commands."""

import sqlalchemy as sa
from alembic import op

revision = "0010_workflow_document_commands"
down_revision = "0009_merge_project_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_document_operations",
        sa.Column("save_operation_id", sa.String(36), primary_key=True),
        sa.Column(
            "workflow_id",
            sa.String(36),
            sa.ForeignKey("workflow_documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_workflow_document_operations_workflow_created",
        "workflow_document_operations",
        ["workflow_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_document_operations_workflow_created",
        table_name="workflow_document_operations",
    )
    op.drop_table("workflow_document_operations")
