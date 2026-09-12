"""Store editable workflow documents; no execution or product history tables."""

import sqlalchemy as sa
from alembic import op

revision = "0005_workflow_documents"
down_revision = "0004_proxy_remote_controls"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workflow_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("layout", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("workflow_documents")
