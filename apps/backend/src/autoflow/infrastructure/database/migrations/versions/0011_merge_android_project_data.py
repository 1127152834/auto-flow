"""Merge Android fleet and project-data migration branches.

Revision ID: 0011_merge_android_project_data
Revises: 0010_android_fleet, 0009_merge_project_data
"""

from collections.abc import Sequence

revision: str = "0011_merge_android_project_data"
down_revision: tuple[str, str] = ("0010_android_fleet", "0009_merge_project_data")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge the two compatible schema branches."""


def downgrade() -> None:
    """Split back to both parent revisions without changing schema."""
