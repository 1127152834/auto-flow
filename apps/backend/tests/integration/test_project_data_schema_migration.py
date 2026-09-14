"""Real SQLite upgrades and transactional current-generation schema guards."""

import sqlite3

import pytest
from alembic import command

from tests.integration.test_project_data_migrations import (
    add_record,
    config_for,
    seed_project,
    seed_table,
)


@pytest.fixture
def upgraded(tmp_path):
    path = tmp_path / "schema-guard.sqlite3"
    config = config_for(path)
    command.upgrade(config, "pm02_excel_exports")
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        seed_project(connection)
        seed_table(connection)
        add_record(connection, key="001")
    command.upgrade(config, "head")
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        yield connection, config


def guard(connection):
    return connection.execute(
        "SELECT schema_guard_revision FROM project_data_tables WHERE id='t'"
    ).fetchone()[0]


def test_upgrade_preserves_existing_records_and_adds_guard(upgraded):
    connection, _ = upgraded
    assert guard(connection) == 1
    assert connection.execute(
        "SELECT key_type,key_value,content_revision,status_revision,link_revision "
        "FROM project_data_records"
    ).fetchall() == [("text", "001", 1, 1, 1)]
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute(
        "PRAGMA index_info(ix_project_data_records_current_status)"
    ).fetchall() == [
        (0, 0, "project_id"),
        (1, 1, "table_id"),
        (2, 2, "dataset_generation"),
        (3, 7, "status_id"),
    ]


def test_current_record_mutations_and_rollback_share_guard_transaction(upgraded):
    connection, _ = upgraded
    add_record(connection, key="1")
    assert guard(connection) == 2
    connection.execute(
        "UPDATE project_data_records SET status_revision=2 WHERE key_value='1'"
    )
    assert guard(connection) == 3
    connection.execute("DELETE FROM project_data_records WHERE key_value='1'")
    assert guard(connection) == 4
    connection.rollback()
    assert guard(connection) == 1
    assert (
        connection.execute("SELECT count(*) FROM project_data_records").fetchone()[0]
        == 1
    )


def test_hidden_generation_does_not_invalidate_current_preview(upgraded):
    connection, _ = upgraded
    connection.execute(
        "INSERT INTO project_data_generations VALUES ('g2','p','t','{}','{}','2026-09-14')"
    )
    add_record(connection, generation="g2")
    connection.execute(
        "UPDATE project_data_records SET content_revision=2 WHERE dataset_generation='g2'"
    )
    connection.execute("DELETE FROM project_data_records WHERE dataset_generation='g2'")
    assert guard(connection) == 1


def test_moving_a_record_out_of_current_generation_invalidates_preview(upgraded):
    connection, _ = upgraded
    connection.execute(
        "INSERT INTO project_data_generations VALUES ('g2','p','t','{}','{}','2026-09-14')"
    )
    connection.execute(
        "UPDATE project_data_records SET dataset_generation='g2' WHERE key_value='001'"
    )
    assert guard(connection) == 2


def test_guard_downgrade_removes_only_new_schema(tmp_path):
    config = config_for(tmp_path / "downgrade.sqlite3")
    command.upgrade(config, "head")
    command.downgrade(config, "pm02_excel_exports")
    with sqlite3.connect(tmp_path / "downgrade.sqlite3") as connection:
        assert "schema_guard_revision" not in {
            row[1]
            for row in connection.execute("PRAGMA table_info(project_data_tables)")
        }
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'project_schema_guard_%'"
            ).fetchall()
            == []
        )
