"""Persist Android ownership independently of interrupted run history."""
import sqlalchemy as sa
from alembic import op

revision = "0007_android_devices"
down_revision = "0006_workflow_runs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("android_devices", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("owner_run_id", sa.String(36)), sa.Column("payload", sa.JSON(), nullable=False))


def downgrade():
    op.drop_table("android_devices")
