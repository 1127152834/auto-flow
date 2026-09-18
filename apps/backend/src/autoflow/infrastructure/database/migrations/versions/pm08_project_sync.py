"""Google Sheets connections, bindings, outbound sync operations and remote marks."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "pm08_project_sync"
down_revision: str | None = "pm07_environments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_sheets_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("account_label", sa.Text(), nullable=False),
        sa.Column("credential_key", sa.Text(), nullable=False),
        sa.Column("auth_method", sa.String(20), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("readable", sa.Boolean(), nullable=False),
        sa.Column("writable", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "auth_method IN ('oauth','service_account')",
            name="ck_project_sheets_connection_auth",
        ),
        sa.CheckConstraint(
            "state IN ('available','loginRequired','missing','invalid')",
            name="ck_project_sheets_connection_state",
        ),
    )
    op.create_index(
        "ix_project_sheets_connections_project",
        "project_sheets_connections",
        ["project_id", "created_at"],
    )

    op.create_table(
        "project_sheets_bindings",
        sa.Column(
            "table_id",
            sa.String(36),
            sa.ForeignKey("project_data_tables.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("project_sheets_connections.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("spreadsheet_id", sa.String(256), nullable=False),
        sa.Column("sheet_id", sa.Integer(), nullable=False),
        sa.Column("spreadsheet_title", sa.Text(), nullable=False),
        sa.Column("sheet_name", sa.Text(), nullable=False),
        sa.Column("binding_epoch", sa.Integer(), nullable=False),
        sa.Column("identity_strategy", sa.JSON(), nullable=False),
        sa.Column("mapping", sa.JSON(), nullable=False),
        sa.Column("sync_paused", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("binding_epoch >= 1", name="ck_project_sheets_binding_epoch"),
        sa.CheckConstraint("sheet_id >= 0", name="ck_project_sheets_binding_sheet_id"),
    )
    op.create_index(
        "ix_project_sheets_bindings_source",
        "project_sheets_bindings",
        ["spreadsheet_id", "sheet_id"],
    )
    op.create_index(
        "ix_project_sheets_bindings_project",
        "project_sheets_bindings",
        ["project_id", "updated_at"],
    )

    op.create_table(
        "project_sync_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "table_id",
            sa.String(36),
            sa.ForeignKey("project_data_tables.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "operation_id",
            sa.String(36),
            sa.ForeignKey("project_operations.id", ondelete="RESTRICT"),
        ),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("record_key_type", sa.String(8)),
        sa.Column("record_key", sa.Text()),
        sa.Column("binding_epoch", sa.Integer(), nullable=False),
        sa.Column("target_content_revision", sa.Integer()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("status_revision", sa.Integer(), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("target", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON()),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "kind IN ('pull','push','reconcile','binding','column','systemIdentity')",
            name="ck_project_sync_operation_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending','sending','verifying','confirmed','failed','unknown','paused')",
            name="ck_project_sync_operation_status",
        ),
        sa.CheckConstraint(
            "status_revision >= 1", name="ck_project_sync_operation_status_revision"
        ),
        sa.CheckConstraint(
            "attempts >= 0", name="ck_project_sync_operation_attempts"
        ),
        sa.CheckConstraint(
            "(record_key_type IS NULL) = (record_key IS NULL)",
            name="ck_project_sync_operation_record_key",
        ),
        sa.UniqueConstraint(
            "table_id", "dedupe_key", name="uq_project_sync_operation_dedupe"
        ),
    )
    op.create_index(
        "ix_project_sync_operation_queue",
        "project_sync_operations",
        ["table_id", "status", "next_attempt_at"],
    )
    op.create_index(
        "ix_project_sync_operation_record",
        "project_sync_operations",
        ["table_id", "record_key_type", "record_key", "target_content_revision"],
    )

    op.create_table(
        "project_sync_record_marks",
        sa.Column(
            "table_id",
            sa.String(36),
            sa.ForeignKey("project_data_tables.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("record_key_type", sa.String(8), primary_key=True),
        sa.Column("record_key", sa.Text(), primary_key=True),
        sa.Column("remote_missing", sa.Boolean(), nullable=False),
        sa.Column("observed", sa.JSON()),
        sa.Column("remote_seen_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("project_sync_record_marks")
    op.drop_table("project_sync_operations")
    op.drop_table("project_sheets_bindings")
    op.drop_table("project_sheets_connections")
