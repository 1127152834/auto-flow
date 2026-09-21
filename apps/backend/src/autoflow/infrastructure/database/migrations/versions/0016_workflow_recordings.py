"""Persist confirmed Studio recording steps and editable reviews."""

import sqlalchemy as sa
from alembic import op

revision = "0016_workflow_recordings"
down_revision = "0015_workflow_mcp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_recording_sessions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("active_slot", sa.Integer(), nullable=True, unique=True),
        sa.Column("last_sequence", sa.Integer(), nullable=False),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workflow_recording_events",
        sa.Column(
            "session_id",
            sa.String(128),
            sa.ForeignKey("workflow_recording_sessions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("sequence", sa.Integer(), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
    )
    op.create_table(
        "workflow_recording_reviews",
        sa.Column("document_id", sa.String(128), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("auto_wait", sa.Boolean(), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workflow_recording_reviews")
    op.drop_table("workflow_recording_events")
    op.drop_table("workflow_recording_sessions")
