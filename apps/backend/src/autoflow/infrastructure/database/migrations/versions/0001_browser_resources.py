import sqlalchemy as sa
from alembic import op

revision = "0001_browser_resources"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("profiles", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(120), nullable=False, unique=True), sa.Column("spec", sa.JSON(), nullable=False), sa.Column("fingerprint_seed", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("proxies", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("proxy_pools", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(120), nullable=False))
    op.create_table("kernel_settings", sa.Column("key", sa.String(120), primary_key=True), sa.Column("value", sa.Text(), nullable=False), sa.Column("revision", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("kernel_operations", sa.Column("id", sa.String(36), primary_key=True), sa.Column("kind", sa.String(80), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("result", sa.JSON()), sa.Column("error", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    for table in ("kernel_operations", "kernel_settings", "proxy_pools", "proxies", "profiles"):
        op.drop_table(table)
