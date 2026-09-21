"""Preserve one local cursor per RecordRef even when a source lease is shared."""

import sqlalchemy as sa
from alembic import op

revision = "pm10_shared_sheet_cursors"
down_revision = "pm09_shared_sheet_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_task_record_cursors") as batch:
        batch.drop_constraint("uq_project_task_record_cursors_lease", type_="unique")
        batch.create_unique_constraint("uq_project_task_record_cursors_ref", ["task_id", "record_ref"])


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT 1 FROM project_task_record_cursors GROUP BY task_id, lease_id HAVING COUNT(*) > 1 LIMIT 1")).first():
        raise RuntimeError("Shared lease cursors exist; restore a backup instead of losing local write versions.")
    with op.batch_alter_table("project_task_record_cursors") as batch:
        batch.drop_constraint("uq_project_task_record_cursors_ref", type_="unique")
        batch.create_unique_constraint("uq_project_task_record_cursors_lease", ["task_id", "lease_id"])
