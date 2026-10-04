"""Per-environment override of the browser cache exclusion (remediation M3 R3-09)."""

import sqlalchemy as sa
from alembic import op

revision = "rm3_environment_cache"
down_revision = "rm3_claim_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_environments") as batch:
        batch.add_column(sa.Column("keep_browser_cache", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("project_environments") as batch:
        batch.drop_column("keep_browser_cache")
