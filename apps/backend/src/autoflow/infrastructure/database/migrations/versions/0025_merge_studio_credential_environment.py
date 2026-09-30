"""Join Studio credential namespace and environment identity histories."""

revision = "0025_merge_studio_credential_environment"
down_revision = ("0024_studio_credential_namespace", "0024_environment_identity")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
