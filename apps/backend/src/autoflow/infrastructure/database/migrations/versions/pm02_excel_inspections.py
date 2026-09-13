"""Persist controlled file authority and reusable Excel inspection facts."""

import sqlalchemy as sa
from alembic import op

revision = "pm02_excel_inspections"
down_revision = "pm02_status_batches"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_file_selections",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("window_id", sa.Integer(), nullable=False),
        sa.Column("window_token_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("workspace_id", sa.Text(), nullable=False),
        sa.Column("instance_id", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "project_excel_inspections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("selection_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("window_id", sa.Integer(), nullable=False),
        sa.Column("window_token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_project_excel_inspections_project_id",
        "project_excel_inspections",
        ["project_id"],
    )

    op.create_table(
        "project_excel_inspection_jobs",
        sa.Column("operation_id", sa.String(36), primary_key=True),
        sa.Column("inspection_id", sa.String(36), nullable=False, unique=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("selection_token_hash", sa.String(64), nullable=False),
        sa.Column("window_id", sa.Integer(), nullable=False),
        sa.Column("window_token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_project_excel_inspection_jobs_project_id",
        "project_excel_inspection_jobs",
        ["project_id"],
    )


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM project_excel_inspections UNION ALL SELECT 1 FROM project_excel_inspection_jobs LIMIT 1"
            )
        )
        .first()
    ):
        raise RuntimeError("Cannot remove persisted Excel inspection evidence")
    op.drop_index(
        "ix_project_excel_inspection_jobs_project_id",
        table_name="project_excel_inspection_jobs",
    )
    op.drop_table("project_excel_inspection_jobs")
    op.drop_index(
        "ix_project_excel_inspections_project_id",
        table_name="project_excel_inspections",
    )
    op.drop_table("project_excel_inspections")
    op.drop_table("project_file_selections")
