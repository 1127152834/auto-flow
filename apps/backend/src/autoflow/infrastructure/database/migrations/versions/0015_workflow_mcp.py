"""Persist Studio MCP settings without storing connection secrets in SQLite."""

import sqlalchemy as sa
from alembic import op

revision = "0015_workflow_mcp"
down_revision = "0014_workflow_assistant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_mcp_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("secret_ref", sa.String(180), nullable=False),
        sa.Column("config_digest", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workflow_mcp_commands",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workflow_mcp_commands")
    op.drop_table("workflow_mcp_settings")
