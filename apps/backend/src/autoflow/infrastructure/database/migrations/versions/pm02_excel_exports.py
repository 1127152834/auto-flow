"""Freeze authorized export jobs and evidence before external publication."""

import sqlalchemy as sa
from alembic import op

revision = "pm02_excel_exports"
down_revision = "pm02_excel_imports"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_excel_export_jobs",
        sa.Column("operation_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("table_id", sa.String(36), nullable=False),
        sa.Column("dataset_generation", sa.String(36), nullable=False),
        sa.Column("selection_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("window_id", sa.Integer(), nullable=False),
        sa.Column("window_token_hash", sa.String(64), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_project_excel_export_jobs_project_id",
        "project_excel_export_jobs",
        ["project_id"],
    )
    op.create_table(
        "project_excel_publications",
        sa.Column("operation_id", sa.String(36), primary_key=True),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("digest", sa.String(64)),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("record_count", sa.Integer()),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM project_excel_export_jobs LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Cannot remove persisted export evidence")
    op.drop_table("project_excel_publications")
    op.drop_index(
        "ix_project_excel_export_jobs_project_id",
        table_name="project_excel_export_jobs",
    )
    op.drop_table("project_excel_export_jobs")
