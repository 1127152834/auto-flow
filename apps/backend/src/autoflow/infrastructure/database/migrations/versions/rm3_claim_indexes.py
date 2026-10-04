"""Claim ordering indexes on live records (remediation M3 R3-01).

The expressions must match the ORDER BY in project_claims.CLAIM_KEY_ORDER exactly so SQLite
reads candidates in claim order without sorting the whole table.
"""

import sqlalchemy as sa
from alembic import op

revision = "rm3_claim_indexes"
down_revision = "rm2_workflow_reuse"
branch_labels = None
depends_on = None

KEY_RANK = "(CASE key_type WHEN 'text' THEN 0 WHEN 'integer' THEN 1 ELSE 2 END)"
KEY_NUMBER = "(CASE WHEN key_type = 'integer' THEN CAST(key_value AS INTEGER) END)"


def upgrade() -> None:
    for name, leading in (
        ("ix_project_data_records_claim_key", []),
        ("ix_project_data_records_claim_created", ["created_at"]),
        ("ix_project_data_records_claim_updated", ["updated_at"]),
    ):
        op.create_index(
            name,
            "project_data_records",
            ["dataset_generation", *leading, sa.text(KEY_RANK), sa.text(KEY_NUMBER), "key_value"],
            sqlite_where=sa.text("deleted = 0"),
        )


def downgrade() -> None:
    for name in ("ix_project_data_records_claim_updated", "ix_project_data_records_claim_created", "ix_project_data_records_claim_key"):
        op.drop_index(name, table_name="project_data_records")
