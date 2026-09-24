"""Persist Studio scheduled tasks and deduplicated executions."""

import sqlalchemy as sa
from alembic import op

revision = "0018_scheduled_tasks"
down_revision = "0017_studio_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_scheduled_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("is_running", sa.Boolean(), nullable=False),
        sa.Column("next_execution_time", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflow_scheduled_tasks_workflow_id", "workflow_scheduled_tasks", ["workflow_id"])
    op.create_table(
        "workflow_scheduled_task_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("workflow_scheduled_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("occurrence_key", sa.String(160), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "occurrence_key", name="uq_scheduled_task_occurrence"),
    )
    op.create_index(
        "ix_scheduled_task_execution_queue",
        "workflow_scheduled_task_executions",
        ["status", "due_at", "created_at"],
    )
    op.create_index("ix_scheduled_task_execution_started", "workflow_scheduled_task_executions", ["task_id", "started_at"])


def downgrade() -> None:
    op.drop_table("workflow_scheduled_task_executions")
    op.drop_index("ix_workflow_scheduled_tasks_workflow_id", table_name="workflow_scheduled_tasks")
    op.drop_table("workflow_scheduled_tasks")
