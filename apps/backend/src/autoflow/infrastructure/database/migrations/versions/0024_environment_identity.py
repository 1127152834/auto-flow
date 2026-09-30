"""Persist saved identity without inventing identities for existing environments."""

import sqlalchemy as sa
from alembic import op

revision = "0024_environment_identity"
down_revision = "0023_merge_studio_android"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project_environments", sa.Column("identity_package", sa.JSON(), nullable=True))


def downgrade() -> None:
    if op.get_bind().execute(sa.text(
        "SELECT 1 FROM project_environments WHERE identity_package IS NOT NULL LIMIT 1"
    )).first():
        raise RuntimeError("Saved identities exist; restore a backup instead of losing browser identity.")
    op.drop_column("project_environments", "identity_package")
