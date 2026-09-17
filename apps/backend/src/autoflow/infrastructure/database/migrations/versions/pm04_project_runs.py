"""Persist project batches and task identities without copying core run state."""

import sqlalchemy as sa
from alembic import op

revision = "pm04_project_runs"
down_revision = "pm03_project_automations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "automation_id",
            sa.String(36),
            sa.ForeignKey("project_automations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "start_operation_id",
            sa.String(36),
            sa.ForeignKey("project_operations.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "prepared_content_id",
            sa.String(36),
            sa.ForeignKey("workflow_prepared_contents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("automation_revision", sa.Integer(), nullable=False),
        sa.Column("workflow_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("status_revision", sa.Integer(), nullable=False),
        sa.Column("frozen_request", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_project_batches_project_created",
        "project_batches",
        ["project_id", "created_at"],
    )
    op.create_table(
        "project_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "batch_id",
            sa.String(36),
            sa.ForeignKey("project_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("run_request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "batch_id", "ordinal", name="uq_project_tasks_batch_ordinal"
        ),
    )
    op.create_table(
        "project_task_input_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("project_tasks.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "batch_id",
            sa.String(36),
            sa.ForeignKey("project_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT 1 FROM project_batches LIMIT 1")).first():
        raise RuntimeError(
            "Project run evidence exists; restore a backup instead of discarding it."
        )
    op.drop_table("project_task_input_snapshots")
    op.drop_table("project_tasks")
    op.drop_index("ix_project_batches_project_created", table_name="project_batches")
    op.drop_table("project_batches")
