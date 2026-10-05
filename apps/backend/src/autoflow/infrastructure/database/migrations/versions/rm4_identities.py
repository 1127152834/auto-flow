"""Identities and the global fingerprint seed registry (remediation M4 R4-01, R4-02)."""

import sqlalchemy as sa
from alembic import op

revision = "rm4_identities"
down_revision = "rm3_environment_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seed_registry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("seed_value", sa.Integer(), nullable=False, unique=True),
        sa.Column("legacy_shared", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "identities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("template_profile_id", sa.String(36)),
        sa.Column("seed_id", sa.String(36), sa.ForeignKey("seed_registry.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("region", sa.JSON(), nullable=False),
        sa.Column("proxy_binding", sa.JSON()),
        sa.Column("environment_id", sa.String(36), sa.ForeignKey("project_environments.id", ondelete="RESTRICT"), unique=True),
        sa.Column("health", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("uq_identities_project_name", "identities", ["project_id", "name_key"], unique=True)
    op.create_index("ix_identities_seed", "identities", ["seed_id"])


def downgrade() -> None:
    op.drop_index("ix_identities_seed", "identities")
    op.drop_index("uq_identities_project_name", "identities")
    op.drop_table("identities")
    op.drop_table("seed_registry")
