"""Retain deleted status identities while allowing active names to be reused."""

import sqlalchemy as sa
from alembic import op

revision = "pm02_status_tombstones"
down_revision = "pm02_project_data"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("project_data_statuses", recreate="always") as batch:
        batch.add_column(
            sa.Column(
                "deleted", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch.drop_constraint("uq_project_data_status_name", type_="unique")
    op.create_index(
        "uq_project_data_status_active_name",
        "project_data_statuses",
        ["table_id", "name_key"],
        unique=True,
        sqlite_where=sa.text("deleted = 0"),
    )


def downgrade():
    # Dropping the marker would resurrect historical identities and may violate names.
    if (
        op.get_bind()
        .execute(
            sa.text("SELECT 1 FROM project_data_statuses WHERE deleted = 1 LIMIT 1")
        )
        .first()
    ):
        raise RuntimeError("Cannot downgrade while deleted statuses exist")
    op.drop_index(
        "uq_project_data_status_active_name", table_name="project_data_statuses"
    )
    with op.batch_alter_table("project_data_statuses", recreate="always") as batch:
        batch.drop_column("deleted")
        batch.create_unique_constraint(
            "uq_project_data_status_name", ["table_id", "name_key"]
        )
