"""Add durable idempotency receipts for workflow document writes."""

import sqlalchemy as sa
from alembic import op

revision = "0012_workflow_document_requests"
down_revision = "0011_merge_android_project_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_document_requests",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_workflow_document_requests_workflow_id",
        "workflow_document_requests",
        ["workflow_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_document_requests_workflow_id",
        table_name="workflow_document_requests",
    )
    op.drop_table("workflow_document_requests")
