"""Persist idempotent Studio recording control commands."""

import sqlalchemy as sa
from alembic import op

revision = "0019_recording_commands"
down_revision = "0018_scheduled_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_recording_commands",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_workflow_recording_commands_session_id",
        "workflow_recording_commands",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_recording_commands_session_id",
        table_name="workflow_recording_commands",
    )
    op.drop_table("workflow_recording_commands")
