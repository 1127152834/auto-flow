"""Several automations of one project may share a workflow (remediation M2 R2-18)."""

from alembic import op

revision = "rm2_workflow_reuse"
down_revision = "rm2_automation_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_automations") as batch:
        batch.drop_constraint("uq_project_automations_workflow", type_="unique")
        batch.create_index("ix_project_automations_workflow", ["workflow_id"])


def downgrade() -> None:
    # Only possible while no workflow is shared; the unique constraint fails otherwise.
    with op.batch_alter_table("project_automations") as batch:
        batch.drop_index("ix_project_automations_workflow")
        batch.create_unique_constraint("uq_project_automations_workflow", ["workflow_id"])
