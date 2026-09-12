"""Persist remote proxy commands without storing authentication values."""

import sqlalchemy as sa
from alembic import op

revision = "0004_proxy_remote_controls"
down_revision = "0003_merge_proxy_models"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("proxy_operations") as batch:
        for name, column_type in (
            ("connection_id", sa.String(36)),
            ("secret_ref", sa.String(255)),
            ("idempotency_key", sa.String(36)),
            ("fingerprint", sa.String(64)),
            ("payload", sa.JSON()),
            ("before", sa.JSON()),
        ):
            batch.add_column(sa.Column(name, column_type, nullable=True))
        batch.create_unique_constraint(
            "uq_proxy_operation_idempotency", ["idempotency_key"]
        )
    op.create_index(
        "uq_proxy_remote_active",
        "proxy_operations",
        ["target_id"],
        unique=True,
        sqlite_where=sa.text(
            "status IN ('queued','running','unknown') AND kind IN ('change_ip','relocate','save_rotation','clear_rotation')"
        ),
    )


def downgrade():
    op.drop_index("uq_proxy_remote_active", table_name="proxy_operations")
    with op.batch_alter_table("proxy_operations") as batch:
        batch.drop_constraint("uq_proxy_operation_idempotency", type_="unique")
        for name in (
            "connection_id",
            "secret_ref",
            "idempotency_key",
            "fingerprint",
            "payload",
            "before",
        ):
            batch.drop_column(name)
