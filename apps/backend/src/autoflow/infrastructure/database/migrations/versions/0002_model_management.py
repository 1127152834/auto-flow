import sqlalchemy as sa
from alembic import op

revision = "0002_model_management"
down_revision = "0001_browser_resources"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "model_providers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "name", sa.String(120, collation="BINARY"), nullable=False, unique=True
        ),
        sa.Column("preset_id", sa.String(80)),
        sa.Column("provider_kind", sa.String(40), nullable=False),
        sa.Column("base_url", sa.Text()),
        sa.Column("secret_ref", sa.String(100), unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("connection_status", sa.String(20), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("last_check_latency_ms", sa.Float()),
        sa.Column("last_check_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "models",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "provider_id",
            sa.String(36),
            sa.ForeignKey("model_providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_key", sa.String(160, collation="BINARY"), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("context_window", sa.Integer()),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider_id", "model_key", name="uq_models_provider_key"),
    )
    op.create_table(
        "model_credential_cleanup",
        sa.Column("secret_ref", sa.String(100), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("model_credential_cleanup")
    op.drop_table("models")
    op.drop_table("model_providers")
