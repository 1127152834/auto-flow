"""Automation schedules and triggers (remediation M2 R2-25/R2-26)."""

import sqlalchemy as sa
from alembic import op

revision = "rm2_automation_schedules"
down_revision = "rm2_preview_overlay"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("automation_id", sa.String(36), sa.ForeignKey("project_automations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("cron", sa.String(120), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("overlap", sa.String(16), nullable=False),
        sa.Column("missed", sa.String(16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("max_tasks", sa.Integer(), nullable=True),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("webhook_secret_hash", sa.String(64), nullable=True),
        sa.Column("last_fire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_automation_schedules_automation", "automation_schedules", ["automation_id"])
    op.create_table(
        "automation_schedule_triggers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("schedule_id", sa.String(36), sa.ForeignKey("automation_schedules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger_key", sa.Text(), nullable=False),
        sa.Column("planned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("schedule_id", "trigger_key", name="uq_automation_schedule_triggers_key"),
    )
    op.create_index("ix_automation_schedule_triggers_schedule", "automation_schedule_triggers", ["schedule_id", "received_at"])


def downgrade() -> None:
    op.drop_index("ix_automation_schedule_triggers_schedule", table_name="automation_schedule_triggers")
    op.drop_table("automation_schedule_triggers")
    op.drop_index("ix_automation_schedules_automation", table_name="automation_schedules")
    op.drop_table("automation_schedules")
