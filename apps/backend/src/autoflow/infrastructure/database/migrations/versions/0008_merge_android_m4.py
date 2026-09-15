"""Merge existing Android and workflow artifact histories without rewriting either."""
revision = "0008_merge_android_m4"
down_revision = ("0007_android_devices", "0007_workflow_artifacts")
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
