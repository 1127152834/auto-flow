"""Persist revisioned custom workflow modules and idempotent writes."""

import sqlalchemy as sa
from alembic import op

revision = "0013_workflow_custom_modules"
down_revision = "0012_workflow_document_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_custom_modules",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("dependency_ids", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workflow_custom_module_requests",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("module_id", sa.String(120), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_workflow_custom_module_requests_module_id",
        "workflow_custom_module_requests",
        ["module_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_custom_module_requests_module_id",
        table_name="workflow_custom_module_requests",
    )
    op.drop_table("workflow_custom_module_requests")
    op.drop_table("workflow_custom_modules")
