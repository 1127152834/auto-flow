"""Join independently applied proxy/model revisions without rewriting history."""

revision = "0003_merge_proxy_models"
down_revision = ("0002_proxy_management", "0002_model_management")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
