"""Freeze project ownership on new recording sessions, reviews and receipts.

Historical rows remain unbound; a recording cannot be assigned from guessed UI state.
"""

import sqlalchemy as sa
from alembic import op

revision = "0020_recording_project_scope"
down_revision = "0019_recording_commands"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("workflow_recording_sessions", "workflow_recording_reviews", "workflow_recording_commands"):
        op.add_column(table, sa.Column("project_id", sa.String(36), nullable=True))
        op.create_index(f"ix_{table}_project_id", table, ["project_id"])
    op.add_column("workflow_recording_sessions", sa.Column("document_id", sa.String(128), nullable=True))
    op.create_index("ix_workflow_recording_sessions_document_id", "workflow_recording_sessions", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_recording_sessions_document_id", table_name="workflow_recording_sessions")
    op.drop_column("workflow_recording_sessions", "document_id")
    for table in ("workflow_recording_commands", "workflow_recording_reviews", "workflow_recording_sessions"):
        op.drop_index(f"ix_{table}_project_id", table_name=table)
        op.drop_column(table, "project_id")
