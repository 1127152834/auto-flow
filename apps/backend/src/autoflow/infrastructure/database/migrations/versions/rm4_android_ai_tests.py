"""Android AI test run records (S1)."""

import sqlalchemy as sa
from alembic import op

revision = "rm4_android_ai_tests"
down_revision = "rm4_record_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "android_ai_test_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(128), nullable=False, unique=True),
        sa.Column("device_kind", sa.String(16), nullable=False),
        sa.Column("device_id", sa.String(36)),
        sa.Column("serial", sa.String(128)),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_android_ai_test_runs_device_created", "android_ai_test_runs",
        ["device_kind", "device_id", "serial", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_android_ai_test_runs_device_created", table_name="android_ai_test_runs")
    op.drop_table("android_ai_test_runs")
