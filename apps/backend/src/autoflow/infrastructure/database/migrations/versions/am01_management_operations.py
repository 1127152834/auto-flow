"""Persist Android management operations and idempotency receipts."""

import sqlalchemy as sa
from alembic import op

revision = "am01_management_operations"
down_revision = "0019_recording_commands"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "android_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_identity", sa.String(255), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("request_digest", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("stage_code", sa.String(64), nullable=False),
        sa.Column("stage_label", sa.String(128), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("retry_of", sa.String(36)),
        sa.Column("result_code", sa.String(64)),
        sa.Column("message", sa.String(512)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("workspace_identity", "request_id", name="uq_android_operation_request"),
    )
    op.create_index("ix_android_operations_target_created", "android_operations", ["target_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_android_operations_target_created", table_name="android_operations")
    op.drop_table("android_operations")
