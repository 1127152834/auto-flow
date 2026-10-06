"""One live environment instance per identity (remediation M4 S8-1, R4-06).

``identity_id`` marks the instance an identity's task works in. Exclusivity used to come only from the
environment occupancy (keyed by environment id), which an identity without a saved login does not have.
The partial unique index makes "one unreleased instance per identity" a database fact; an instance is
released once its work copy is gone (``cleaned``) or handed to a person (``retained_unsaved``).
``retain_on_release`` records that a task asked for the login to be saved when the identity's instance
is released (S8-3); ``held_batch_id`` names the batch whose tasks may re-attach an instance the identity
holds between tasks (S8-2). Both are unused until those slices.
"""

import sqlalchemy as sa
from alembic import op

revision = "rm4_instance_identity"
down_revision = "rm4_record_identity"
branch_labels = None
depends_on = None

INDEX = "uq_project_environment_instances_live_identity"


def upgrade() -> None:
    # Plain ALTER TABLE, like rm4_record_identity: no batch rebuild of the instances table.
    op.add_column("project_environment_instances", sa.Column("identity_id", sa.String(36)))
    op.add_column(
        "project_environment_instances",
        sa.Column("retain_on_release", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("project_environment_instances", sa.Column("held_batch_id", sa.String(36)))
    op.create_index(
        INDEX, "project_environment_instances", ["identity_id"], unique=True,
        sqlite_where=sa.text("identity_id IS NOT NULL AND state NOT IN ('cleaned', 'retained_unsaved')"),
    )


def downgrade() -> None:
    op.drop_index(INDEX, table_name="project_environment_instances")
    op.drop_column("project_environment_instances", "held_batch_id")
    op.drop_column("project_environment_instances", "retain_on_release")
    op.drop_column("project_environment_instances", "identity_id")
