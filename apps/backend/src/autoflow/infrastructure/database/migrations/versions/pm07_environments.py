"""Persist saved environments, instances, occupancy, End and manual facts."""

import sqlalchemy as sa
from alembic import op

revision = "pm07_environments"
down_revision = "pm06_project_capability_reads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_environments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("content_generation", sa.Integer(), nullable=False),
        sa.Column("metadata_revision", sa.Integer(), nullable=False),
        sa.Column("current_digest", sa.String(64), nullable=False),
        sa.Column("created_from_source", sa.String(), nullable=False),
        sa.Column("created_from_task_id", sa.String(36)),
        sa.Column("unavailable_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_project_environments_active_name",
        "project_environments",
        ["project_id", "name_key"],
        unique=True,
        sqlite_where=sa.text("state != 'deleted'"),
    )
    op.create_index(
        "ix_project_environments_project_updated",
        "project_environments",
        ["project_id", "updated_at"],
    )
    op.create_table(
        "project_environment_instances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "environment_id",
            sa.String(36),
            sa.ForeignKey("project_environments.id", ondelete="RESTRICT"),
        ),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_content_generation", sa.Integer()),
        sa.Column("instance_use_generation", sa.Integer(), nullable=False),
        sa.Column("active_task_id", sa.String(36)),
        sa.Column("active_run_id", sa.String(36)),
        sa.Column("maintenance_operation_id", sa.String(36)),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("identity_package", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_project_environment_instances_project_state",
        "project_environment_instances",
        ["project_id", "state"],
    )
    op.create_table(
        "project_environment_occupancies",
        sa.Column(
            "environment_id",
            sa.String(36),
            sa.ForeignKey("project_environments.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "instance_id",
            sa.String(36),
            sa.ForeignKey("project_environment_instances.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("holder_kind", sa.String(), nullable=False),
        sa.Column("holder_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "project_environment_saves",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "instance_id",
            sa.String(36),
            sa.ForeignKey("project_environment_instances.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "environment_id",
            sa.String(36),
            sa.ForeignKey("project_environments.id", ondelete="RESTRICT"),
        ),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("phase", sa.String(), nullable=False),
        sa.Column("expected_content_generation", sa.Integer()),
        sa.Column("published_content_generation", sa.Integer()),
        sa.Column("candidate_digest", sa.String(64)),
        sa.Column("name", sa.Text()),
        sa.Column(
            "operation_id",
            sa.String(36),
            sa.ForeignKey("project_operations.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "project_end_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("phase", sa.String(), nullable=False),
        sa.Column("retain_environment", sa.Boolean(), nullable=False),
        sa.Column(
            "save_operation_id",
            sa.String(36),
            sa.ForeignKey("project_environment_saves.id", ondelete="RESTRICT"),
        ),
        sa.Column("intended_result", sa.JSON(), nullable=False),
        sa.Column("targets", sa.JSON(), nullable=False),
        sa.Column("association_result", sa.JSON()),
        sa.Column(
            "operation_id",
            sa.String(36),
            sa.ForeignKey("project_operations.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "project_manual_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column(
            "instance_id",
            sa.String(36),
            sa.ForeignKey("project_environment_instances.id", ondelete="RESTRICT"),
        ),
        sa.Column("checkpoint_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("status_revision", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("allowed_targets", sa.JSON(), nullable=False),
        sa.Column("resume_started", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_project_manual_items_project_status",
        "project_manual_items",
        ["project_id", "status"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        "project_manual_items",
        "project_end_operations",
        "project_environment_saves",
        "project_environment_occupancies",
        "project_environment_instances",
        "project_environments",
    ):
        if bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError(
                "Persisted environment evidence exists; restore a backup instead "
                "of discarding it."
            )
    op.drop_index(
        "ix_project_manual_items_project_status", table_name="project_manual_items"
    )
    op.drop_table("project_manual_items")
    op.drop_table("project_end_operations")
    op.drop_table("project_environment_saves")
    op.drop_table("project_environment_occupancies")
    op.drop_index(
        "ix_project_environment_instances_project_state",
        table_name="project_environment_instances",
    )
    op.drop_table("project_environment_instances")
    op.drop_index(
        "ix_project_environments_project_updated", table_name="project_environments"
    )
    op.drop_index(
        "uq_project_environments_active_name", table_name="project_environments"
    )
    op.drop_table("project_environments")
