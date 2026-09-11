import sqlalchemy as sa
from alembic import op

revision = "0002_proxy_management"
down_revision = "0001_browser_resources"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "proxy_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("secret_ref", sa.String(240), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sync_token", sa.String(36)),
        sa.Column("sync_started_at", sa.DateTime(timezone=True)),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.JSON()),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "proxy_projections",
        sa.Column("proxy_id", sa.String(36), sa.ForeignKey("proxies.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("connection_id", sa.String(36), sa.ForeignKey("proxy_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", sa.String(240), nullable=False),
        sa.Column("remote_name", sa.String(240), nullable=False),
        sa.Column("name_override", sa.String(120)),
        sa.Column("remote_status", sa.String(120)),
        sa.Column("remote_missing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("carrier", sa.String(240)),
        sa.Column("city", sa.String(240)),
        sa.Column("region", sa.String(240)),
        sa.Column("exit_ip", sa.String(64)),
        sa.Column("http_host", sa.String(255)),
        sa.Column("http_port", sa.Integer()),
        sa.Column("socks5_host", sa.String(255)),
        sa.Column("socks5_port", sa.Integer()),
        sa.Column("credential_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("health_state", sa.String(30), nullable=False, server_default="untested"),
        sa.Column("health_latency_ms", sa.Float()),
        sa.Column("health_exit_ip", sa.String(64)),
        sa.Column("health_checked_at", sa.DateTime(timezone=True)),
        sa.Column("health_source", sa.String(30), nullable=False, server_default="none"),
        sa.Column("health_error", sa.JSON()),
        sa.Column("subscription_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("connection_id", "provider_id"),
    )
    op.create_index("ix_proxy_projections_connection_id", "proxy_projections", ["connection_id"])
    op.create_table(
        "proxy_group_details",
        sa.Column("proxy_pool_id", sa.String(36), sa.ForeignKey("proxy_pools.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cursor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cursor_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "proxy_group_members",
        sa.Column("group_id", sa.String(36), sa.ForeignKey("proxy_pools.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("proxy_id", sa.String(36), sa.ForeignKey("proxies.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("group_id", "position"),
    )
    op.create_table(
        "proxy_group_resolutions",
        sa.Column("group_id", sa.String(36), sa.ForeignKey("proxy_pools.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("request_id", sa.String(120), primary_key=True),
        sa.Column("proxy_id", sa.String(36), sa.ForeignKey("proxies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "proxy_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("resource_revision", sa.Integer()),
        sa.Column("error", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    for table in (
        "proxy_operations",
        "proxy_group_resolutions",
        "proxy_group_members",
        "proxy_group_details",
        "proxy_projections",
        "proxy_connections",
    ):
        op.drop_table(table)
