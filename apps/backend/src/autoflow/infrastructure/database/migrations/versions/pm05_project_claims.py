"""Persist project input leases and task-local record cursors."""

import sqlalchemy as sa
from alembic import op

revision = "pm05_project_claims"
down_revision = "pm04_project_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_batches",
        sa.Column(
            "claim_gate_state",
            sa.String(),
            nullable=False,
            server_default="closed",
        ),
    )
    op.add_column(
        "project_batches", sa.Column("selection_outcome", sa.JSON(), nullable=True)
    )
    op.create_table(
        "project_record_leases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lease_key", sa.String(1024), nullable=False),
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
            "task_id",
            sa.String(36),
            sa.ForeignKey("project_tasks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("record_ref", sa.JSON(), nullable=False),
        sa.Column("lease_generation", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "task_id", "lease_key", name="uq_project_record_leases_task_key"
        ),
    )
    op.create_index(
        "uq_project_record_leases_active_key",
        "project_record_leases",
        ["lease_key"],
        unique=True,
        sqlite_where=sa.text("state IN ('held', 'reconciling')"),
    )
    op.create_index(
        "ix_project_record_leases_task",
        "project_record_leases",
        ["project_id", "task_id"],
    )
    op.create_table(
        "project_task_record_cursors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("project_tasks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "lease_id",
            sa.String(36),
            sa.ForeignKey("project_record_leases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("record_ref", sa.JSON(), nullable=False),
        sa.Column("content_revision", sa.Integer(), nullable=False),
        sa.Column("status_revision", sa.Integer(), nullable=False),
        sa.Column("link_revision", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "task_id", "lease_id", name="uq_project_task_record_cursors_lease"
        ),
    )
    op.create_index(
        "ix_project_task_record_cursors_task",
        "project_task_record_cursors",
        ["task_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM project_task_record_cursors LIMIT 1")).first():
        raise RuntimeError(
            "Project task write cursors exist; restore a backup instead of discarding them."
        )
    if bind.execute(sa.text("SELECT 1 FROM project_record_leases LIMIT 1")).first():
        raise RuntimeError(
            "Project record leases exist; restore a backup instead of discarding them."
        )
    op.drop_index(
        "ix_project_task_record_cursors_task",
        table_name="project_task_record_cursors",
    )
    op.drop_table("project_task_record_cursors")
    op.drop_index(
        "ix_project_record_leases_task", table_name="project_record_leases"
    )
    op.drop_index(
        "uq_project_record_leases_active_key", table_name="project_record_leases"
    )
    op.drop_table("project_record_leases")
    op.drop_column("project_batches", "selection_outcome")
    op.drop_column("project_batches", "claim_gate_state")
