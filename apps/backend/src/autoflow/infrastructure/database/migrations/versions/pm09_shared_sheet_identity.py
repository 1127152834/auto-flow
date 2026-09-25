"""Persist verified source identity without rewriting historical task leases."""

import sqlalchemy as sa
from alembic import op

revision = "pm09_shared_sheet_identity"
down_revision = "pm08_project_sync"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "project_sheets_bindings",
        sa.Column("identity_verification", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("project_sheets_bindings", "identity_verification")
