"""Status tombstones retain historical foreign keys across the real migration."""

import sqlite3

import pytest
from alembic import command
from sqlalchemy import event
from sqlalchemy.engine import Engine

from autoflow.infrastructure.database.session import migrate_database
from tests.integration.test_project_data_migrations import (
    add_record,
    config_for,
    seed_project,
    seed_table,
)


def seed_status(connection, status_id="s", deleted=None):
    columns = "id,project_id,table_id,name,name_key,color,position,status_revision"
    values = [status_id, "p", "t", "Done", "done", "#AABBCC", 0, 1]
    if deleted is not None:
        columns += ",deleted"
        values.append(deleted)
    connection.execute(
        f"INSERT INTO project_data_statuses ({columns}) VALUES ({','.join('?' for _ in values)})",
        values,
    )


@pytest.mark.parametrize("existing", [False, True])
def test_status_upgrade_preserves_records_and_enforces_active_names(tmp_path, existing):
    path = tmp_path / "status.sqlite3"
    config = config_for(path)
    command.upgrade(config, "pm02_project_data")
    before = []
    if existing:
        with sqlite3.connect(path) as connection:
            seed_project(connection)
            seed_table(connection)
            seed_status(connection)
            add_record(connection, key="current", status="s")
            add_record(connection, key="deleted", status="s")
            connection.execute(
                "UPDATE project_data_records SET deleted=1 WHERE key_value='deleted'"
            )
            connection.execute(
                "INSERT INTO project_data_generations VALUES ('old','p','t','{}','{}','2026-09-13')"
            )
            add_record(connection, key="history", generation="old", status="s")
            before = connection.execute(
                "SELECT * FROM project_data_records ORDER BY key_value"
            ).fetchall()
    migrate_database(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        assert connection.execute(
            "SELECT version_num FROM alembic_version"

        ).fetchone() == ("pm08_project_sync",)

        assert (
            connection.execute(
                "SELECT * FROM project_data_records ORDER BY key_value"
            ).fetchall()
            == before
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        if not existing:
            seed_project(connection)
            seed_table(connection)
            seed_status(connection)
        assert connection.execute(
            "SELECT deleted FROM project_data_statuses"
        ).fetchall() == [(0,)]
        with pytest.raises(sqlite3.IntegrityError):
            seed_status(connection, "duplicate")
        # Storage-only probe; the application must separately reject live references.
        connection.execute("UPDATE project_data_statuses SET deleted=1 WHERE id='s'")
        seed_status(connection, "new")
        assert connection.execute(
            "SELECT id FROM project_data_statuses WHERE deleted=0"
        ).fetchall() == [("new",)]
        if existing:
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM project_data_statuses WHERE id='s'")
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_status_migration_failure_rolls_back_rebuild_and_restarts(tmp_path):
    path = tmp_path / "failure.sqlite3"
    config = config_for(path)
    command.upgrade(config, "pm02_project_data")
    with sqlite3.connect(path) as connection:
        seed_project(connection)
        seed_table(connection)
        seed_status(connection)
        add_record(connection, status="s")

    def fail(connection, cursor, statement, parameters, context, executemany):
        if "CREATE UNIQUE INDEX uq_project_data_status_active_name" in statement:
            raise RuntimeError("synthetic status migration failure")

    event.listen(Engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="synthetic status migration failure"):
            migrate_database(path)
    finally:
        event.remove(Engine, "before_cursor_execute", fail)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("pm02_project_data",)
        assert "deleted" not in [
            row[1]
            for row in connection.execute("PRAGMA table_info(project_data_statuses)")
        ]
        assert connection.execute(
            "SELECT status_id FROM project_data_records"
        ).fetchall() == [("s",)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    migrate_database(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT deleted FROM project_data_statuses"
        ).fetchall() == [(0,)]


def test_downgrade_preserves_live_data_but_refuses_to_resurrect_deleted_status(
    tmp_path,
):
    path = tmp_path / "downgrade.sqlite3"
    config = config_for(path)
    migrate_database(path)
    with sqlite3.connect(path) as connection:
        seed_project(connection)
        seed_table(connection)
        seed_status(connection)
        add_record(connection, status="s")
    command.downgrade(config, "pm02_project_data")
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT status_id FROM project_data_records"
        ).fetchall() == [("s",)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    migrate_database(path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE project_data_statuses SET deleted=1")
    with pytest.raises(RuntimeError, match="deleted statuses"):
        command.downgrade(config, "pm02_project_data")
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT deleted FROM project_data_statuses"
        ).fetchall() == [(1,)]
        assert connection.execute(
            "SELECT version_num FROM alembic_version"

        ).fetchone() == ("pm08_project_sync",)
