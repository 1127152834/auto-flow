"""Track current-generation mutations for bounded atomic schema commits."""

import sqlalchemy as sa
from alembic import op

revision = "pm02_schema_drafts"
down_revision = "pm02_excel_exports"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "project_data_tables",
        sa.Column(
            "schema_guard_revision", sa.Integer(), nullable=False, server_default="1"
        ),
    )
    for action, row in (("insert", "NEW"), ("delete", "OLD")):
        op.execute(f"""
            CREATE TRIGGER project_schema_guard_{action}
            AFTER {action.upper()} ON project_data_records
            BEGIN
                UPDATE project_data_tables
                SET schema_guard_revision = schema_guard_revision + 1
                WHERE id = {row}.table_id AND project_id = {row}.project_id
                    AND current_generation = {row}.dataset_generation;
            END;
        """)
    op.execute("""
        CREATE TRIGGER project_schema_guard_update AFTER UPDATE ON project_data_records
        BEGIN
            UPDATE project_data_tables SET schema_guard_revision = schema_guard_revision + 1
            WHERE (id = NEW.table_id AND project_id = NEW.project_id
                AND current_generation = NEW.dataset_generation)
               OR (id = OLD.table_id AND project_id = OLD.project_id
                AND current_generation = OLD.dataset_generation);
        END;
    """)
    op.create_index(
        "ix_project_data_records_current_status",
        "project_data_records",
        ["project_id", "table_id", "dataset_generation", "status_id"],
    )


def downgrade():
    for action in ("insert", "update", "delete"):
        op.execute(f"DROP TRIGGER project_schema_guard_{action}")
    op.drop_index(
        "ix_project_data_records_current_status", table_name="project_data_records"
    )
    op.drop_column("project_data_tables", "schema_guard_revision")
