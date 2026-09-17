"""Persist task-scoped project-data read and query evidence."""

import sqlalchemy as sa
from alembic import op

revision = "pm06_project_capability_reads"
down_revision = "pm05_project_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_task_record_reads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
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
        sa.Column("execution_generation", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.String(36), nullable=False),
        sa.Column("dataset_generation", sa.String(36), nullable=False),
        sa.Column("key_type", sa.String(), nullable=False),
        sa.Column("key_value", sa.String(), nullable=False),
        sa.Column("field_ids", sa.JSON(), nullable=False),
        sa.Column("read_purpose", sa.String(), nullable=False),
        sa.Column("content_revision", sa.Integer(), nullable=False),
        sa.Column("status_revision", sa.Integer(), nullable=False),
        sa.Column("link_revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_project_task_record_reads_task",
        "project_task_record_reads",
        ["task_id", "created_at"],
    )
    op.create_index(
        "ix_project_task_record_reads_ref",
        "project_task_record_reads",
        [
            "project_id",
            "table_id",
            "dataset_generation",
            "key_type",
            "key_value",
        ],
    )
    op.create_table(
        "project_task_record_queries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
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
        sa.Column("execution_generation", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.String(36), nullable=False),
        sa.Column("dataset_generation", sa.String(36), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_project_task_record_queries_task",
        "project_task_record_queries",
        ["task_id", "created_at"],
    )
    op.create_table(
        "project_task_record_query_items",
        sa.Column(
            "query_id",
            sa.String(36),
            sa.ForeignKey("project_task_record_queries.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if (
        bind.execute(sa.text("SELECT 1 FROM project_task_record_reads LIMIT 1")).first()
        or bind.execute(
            sa.text("SELECT 1 FROM project_task_record_queries LIMIT 1")
        ).first()
    ):
        raise RuntimeError(
            "Project task read/query evidence exists; restore a backup instead of discarding it."
        )
    op.drop_table("project_task_record_query_items")
    op.drop_index(
        "ix_project_task_record_queries_task",
        table_name="project_task_record_queries",
    )
    op.drop_table("project_task_record_queries")
    op.drop_index(
        "ix_project_task_record_reads_ref", table_name="project_task_record_reads"
    )
    op.drop_index(
        "ix_project_task_record_reads_task", table_name="project_task_record_reads"
    )
    op.drop_table("project_task_record_reads")
