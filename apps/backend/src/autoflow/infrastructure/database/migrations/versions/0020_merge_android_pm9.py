"""Join Android management and PM9 shared-sheet histories without rewriting either."""

revision = "0020_merge_android_pm9"
down_revision = ("am01_management_operations", "pm10_shared_sheet_cursors")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
