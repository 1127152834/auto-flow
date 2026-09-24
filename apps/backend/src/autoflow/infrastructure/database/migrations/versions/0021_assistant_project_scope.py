"""Bind new assistant sessions to a project without assigning historical sessions."""

import sqlalchemy as sa
from alembic import op

revision = "0021_assistant_project_scope"
down_revision = "0020_recording_project_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workflow_assistant_sessions", sa.Column("project_id", sa.String(36), nullable=True))
    op.create_index("ix_workflow_assistant_sessions_project_id", "workflow_assistant_sessions", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_assistant_sessions_project_id", table_name="workflow_assistant_sessions")
    op.drop_column("workflow_assistant_sessions", "project_id")
