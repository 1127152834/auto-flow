"""Persist fixed-target business status batches and committed block evidence."""

import sqlalchemy as sa
from alembic import op

revision = "pm02_status_batches"
down_revision = "pm02_status_tombstones"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_data_status_batches",
        sa.Column(
            "operation_id",
            sa.String(36),
            sa.ForeignKey("project_operations.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("table_id", sa.String(36), nullable=False),
        sa.Column("status_id", sa.String(36)),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("block_size", sa.Integer(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "project_data_status_batch_blocks",
        sa.Column(
            "operation_id",
            sa.String(36),
            sa.ForeignKey(
                "project_data_status_batches.operation_id", ondelete="RESTRICT"
            ),
            primary_key=True,
        ),
        sa.Column("block_index", sa.Integer(), primary_key=True),
        sa.Column("targets", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("blockers", sa.JSON(), nullable=False),
        sa.Column("committed_revisions", sa.JSON(), nullable=False),
    )


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM project_data_status_batches LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Cannot remove durable status operation history")
    op.drop_table("project_data_status_batch_blocks")
    op.drop_table("project_data_status_batches")
