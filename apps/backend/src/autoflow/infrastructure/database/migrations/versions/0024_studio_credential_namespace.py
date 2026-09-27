"""Add a stable credential namespace without reading or moving native secrets."""

import sqlalchemy as sa
from alembic import op

revision = "0024_studio_credential_namespace"
down_revision = "0023_merge_studio_android"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Initialized once under BEGIN IMMEDIATE by the repository. Moving the
    # workspace retains this identity; no filesystem path enters a secret key.
    op.add_column("studio_credential_state", sa.Column("workspace_id", sa.String(36)))


def downgrade() -> None:
    # Native keys remain untouched. Restore the matching database backup when
    # returning to this schema after a downgrade to retain the scoped identity.
    op.drop_column("studio_credential_state", "workspace_id")
