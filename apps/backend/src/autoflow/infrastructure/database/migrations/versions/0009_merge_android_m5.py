"""Join shipped Android management and M5 migrations without rewriting history."""
revision = "0009_merge_android_m5"
down_revision = ("0008_merge_android_m4", "0008_workflow_debug")
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
