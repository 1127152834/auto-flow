"""Persist hidden Excel candidates and import operation identities."""

import sqlalchemy as sa
from alembic import op

revision = "pm02_excel_imports"
down_revision = "pm02_excel_inspections"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "project_data_tables",
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "project_excel_import_jobs",
        sa.Column("operation_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("table_id", sa.String(36)),
        sa.Column("inspection_id", sa.String(36), nullable=False),
        sa.Column("target_generation", sa.String(36), nullable=False, unique=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_project_excel_import_jobs_project_id",
        "project_excel_import_jobs",
        ["project_id"],
    )


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM project_excel_import_jobs LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Cannot remove persisted import evidence")
    op.drop_column("project_data_tables", "published")
    op.drop_index(
        "ix_project_excel_import_jobs_project_id",
        table_name="project_excel_import_jobs",
    )
    op.drop_table("project_excel_import_jobs")
