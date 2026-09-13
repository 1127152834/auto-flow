import sqlite3

import pytest
from alembic import command

from autoflow.infrastructure.database.session import migrate_database
from tests.integration.test_project_data_migrations import config_for, seed_project


@pytest.mark.parametrize("start", [None, "pm01_projects", "pm02_status_tombstones"])
def test_durable_status_migration_preserves_existing_project(tmp_path, start):
    path = tmp_path / "durable.sqlite3"
    if start:
        command.upgrade(config_for(path), start)
        with sqlite3.connect(path) as connection:
            seed_project(connection)
    migrate_database(path)
    with sqlite3.connect(path) as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "project_data_status_batches",
            "project_data_status_batch_blocks",
            "project_file_selections",
            "project_excel_inspections",
            "project_excel_inspection_jobs",
        } <= names
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT count(*) FROM projects").fetchone()[0] == int(
            start is not None
        )
