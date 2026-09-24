"""Persist Studio credential metadata and idempotent field commands."""

import sqlalchemy as sa
from alembic import op

revision = "0017_studio_credentials"
down_revision = "0016_workflow_recordings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    state = op.create_table(
        "studio_credential_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
    )
    op.bulk_insert(state, [{"id": 1, "revision": 0}])
    op.create_table(
        "studio_credentials",
        sa.Column("name", sa.String(120), primary_key=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("field_names", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "studio_credential_commands",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("studio_credential_commands")
    op.drop_table("studio_credentials")
    op.drop_table("studio_credential_state")
