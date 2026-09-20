"""Persist Studio assistant sessions and idempotent frontend command results."""

import sqlalchemy as sa
from alembic import op

revision = "0014_workflow_assistant"
down_revision = "pm08_project_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_assistant_sessions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workflow_assistant_commands",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(128),
            sa.ForeignKey("workflow_assistant_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_workflow_assistant_commands_session_id",
        "workflow_assistant_commands",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_assistant_commands_session_id",
        table_name="workflow_assistant_commands",
    )
    op.drop_table("workflow_assistant_commands")
    op.drop_table("workflow_assistant_sessions")
