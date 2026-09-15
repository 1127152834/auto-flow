"""Durable Android templates, creation batches and allocation requests."""

import sqlalchemy as sa
from alembic import op

revision = "0010_android_fleet"
down_revision = "0009_merge_android_m5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "android_resources",
        sa.Column("kind", sa.String(24), primary_key=True),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("android_resources")
