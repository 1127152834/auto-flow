"""Run-private preview writes (remediation M2 R2-30)."""

import sqlalchemy as sa
from alembic import op

revision = "rm2_preview_overlay"
down_revision = "rm2_record_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_preview_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("table_id", sa.String(36), nullable=False),
        sa.Column("dataset_generation", sa.String(36), nullable=False),
        sa.Column("key_type", sa.String(16), nullable=False),
        sa.Column("key_value", sa.Text(), nullable=False),
        sa.Column("values_json", sa.JSON(), nullable=False),
        sa.Column("status_id", sa.String(36), nullable=True),
        sa.Column("created", sa.Boolean(), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "run_id", "table_id", "dataset_generation", "key_type", "key_value",
            name="uq_project_preview_records_identity",
        ),
    )


def downgrade() -> None:
    op.drop_table("project_preview_records")
