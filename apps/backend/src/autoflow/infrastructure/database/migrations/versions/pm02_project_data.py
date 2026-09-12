"""Local project data with typed identities and independent revisions."""

import sqlalchemy as sa
from alembic import op

revision = "pm02_project_data"
down_revision = "pm01_projects"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_project_operations_scope",
        "project_operations",
        ["project_id", "id"],
        unique=True,
    )
    op.create_table(
        "project_data_tables",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(20), nullable=False),
        sa.Column("current_generation", sa.String(36), nullable=False),
        sa.Column("table_revision", sa.Integer(), nullable=False),
        sa.Column("identity", sa.JSON(), nullable=False),
        sa.Column("slot_definitions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "id", name="uq_project_data_table_scope"),
        sa.ForeignKeyConstraint(
            ["project_id", "id", "current_generation"],
            [
                "project_data_generations.project_id",
                "project_data_generations.table_id",
                "project_data_generations.id",
            ],
            name="fk_project_data_current_generation",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint(
            "project_id", "name_key", name="uq_project_data_table_name"
        ),
        sa.CheckConstraint(
            "table_revision >= 1", name="ck_project_data_table_revision"
        ),
        sa.CheckConstraint(
            "source_kind IN ('local','excel','sheets','unconfigured')",
            name="ck_project_data_source_kind",
        ),
    )
    op.create_index(
        "ix_project_data_tables_directory",
        "project_data_tables",
        ["project_id", "updated_at", "id"],
    )
    op.create_table(
        "project_data_generations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("table_id", sa.String(36), nullable=False),
        sa.Column("identity", sa.JSON(), nullable=False),
        sa.Column("source", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "project_id", "table_id", "id", name="uq_project_data_generation_scope"
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "table_id"],
            ["project_data_tables.project_id", "project_data_tables.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "project_data_fields",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("table_id", sa.String(36), nullable=False),
        sa.Column("dataset_generation", sa.String(36), primary_key=True),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("writable", sa.Boolean(), nullable=False),
        sa.Column("formula", sa.Boolean(), nullable=False),
        sa.Column("validation", sa.JSON(), nullable=False),
        sa.Column("field_revision", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "dataset_generation", "key", name="uq_project_data_field_key"
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "table_id", "dataset_generation"],
            [
                "project_data_generations.project_id",
                "project_data_generations.table_id",
                "project_data_generations.id",
            ],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "type IN ('string','number','boolean','date')",
            name="ck_project_data_field_type",
        ),
        sa.CheckConstraint(
            "field_revision >= 1", name="ck_project_data_field_revision"
        ),
    )
    op.create_table(
        "project_data_statuses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("table_id", sa.String(36), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status_revision", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "project_id", "table_id", "id", name="uq_project_data_status_scope"
        ),
        sa.UniqueConstraint("table_id", "name_key", name="uq_project_data_status_name"),
        sa.ForeignKeyConstraint(
            ["project_id", "table_id"],
            ["project_data_tables.project_id", "project_data_tables.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status_revision >= 1", name="ck_project_data_status_revision"
        ),
        sa.CheckConstraint("position >= 0", name="ck_project_data_status_position"),
    )
    op.create_table(
        "project_data_records",
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("table_id", sa.String(36), nullable=False),
        sa.Column("dataset_generation", sa.String(36), primary_key=True),
        sa.Column("key_type", sa.String(10), primary_key=True),
        sa.Column("key_value", sa.Text(), primary_key=True),
        sa.Column("values_json", sa.JSON(), nullable=False),
        sa.Column("record_slots", sa.JSON(), nullable=False),
        sa.Column("status_id", sa.String(36)),
        sa.Column("current_environment_id", sa.String(36)),
        sa.Column("content_revision", sa.Integer(), nullable=False),
        sa.Column("status_revision", sa.Integer(), nullable=False),
        sa.Column("link_revision", sa.Integer(), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id", "table_id", "dataset_generation"],
            [
                "project_data_generations.project_id",
                "project_data_generations.table_id",
                "project_data_generations.id",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "table_id", "status_id"],
            [
                "project_data_statuses.project_id",
                "project_data_statuses.table_id",
                "project_data_statuses.id",
            ],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "key_type IN ('text','integer','uuid')", name="ck_project_data_key_type"
        ),
        sa.CheckConstraint(
            "content_revision >= 1 AND status_revision >= 1 AND link_revision >= 1",
            name="ck_project_data_record_revisions",
        ),
    )
    op.create_index(
        "ix_project_data_records_status",
        "project_data_records",
        ["dataset_generation", "deleted", "status_id", "key_type", "key_value"],
    )
    op.create_index(
        "ix_project_data_records_updated",
        "project_data_records",
        ["dataset_generation", "deleted", "updated_at"],
    )
    op.create_table(
        "project_data_changes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("operation_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("resource", sa.JSON(), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.Column("before", sa.JSON()),
        sa.Column("after", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "operation_id", "sequence", name="uq_project_data_change_operation"
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "operation_id"],
            ["project_operations.project_id", "project_operations.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_project_data_changes_project",
        "project_data_changes",
        ["project_id", "created_at"],
    )
    op.create_table(
        "project_data_impacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("target", sa.JSON(), nullable=False),
        sa.Column("change_digest", sa.String(64), nullable=False),
        sa.Column("expected_revisions", sa.JSON(), nullable=False),
        sa.Column("facts_digest", sa.String(64), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sqlite_autoincrement=True,
    )


def downgrade():
    for table in (
        "project_data_impacts",
        "project_data_changes",
        "project_data_records",
        "project_data_statuses",
        "project_data_fields",
        "project_data_generations",
        "project_data_tables",
    ):
        op.drop_table(table)

    op.drop_index("uq_project_operations_scope", table_name="project_operations")
