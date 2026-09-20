import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from autoflow.infrastructure.database import session as database_session

EXPECTED_HEAD = "0015_workflow_mcp"


def config_for(database: Path) -> Config:
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    return config


def test_claim_migration_is_the_single_head_and_creates_durable_facts(tmp_path):
    database = tmp_path / "claims.sqlite3"
    config = config_for(database)

    assert ScriptDirectory.from_config(config).get_heads() == [EXPECTED_HEAD]
    database_session.migrate_database(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == (EXPECTED_HEAD,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "project_record_leases",
            "project_task_record_cursors",
            "project_task_record_reads",
        } <= tables
        batch_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(project_batches)")
        }
        assert {"claim_gate_state", "selection_outcome"} <= batch_columns
        read_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(project_task_record_reads)"
            )
        }
        assert "execution_generation" in read_columns


def test_claim_tables_use_restrictive_project_task_run_and_lease_references(tmp_path):
    database = tmp_path / "claims-foreign-keys.sqlite3"
    database_session.migrate_database(database)

    expected = {
        "project_record_leases": {
            ("projects", "project_id"),
            ("project_batches", "batch_id"),
            ("project_tasks", "task_id"),
            ("project_workflow_runs", "run_id"),
        },
        "project_task_record_cursors": {
            ("project_tasks", "task_id"),
            ("project_record_leases", "lease_id"),
        },
        "project_task_record_reads": {
            ("projects", "project_id"),
            ("project_tasks", "task_id"),
            ("project_workflow_runs", "run_id"),
        },
    }
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        for table, references in expected.items():
            rows = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
            assert {(row[2], row[3]) for row in rows} == references
            assert {row[6] for row in rows} == {"RESTRICT"}
        index_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' "
            "AND name='uq_project_record_leases_active_key'"
        ).fetchone()
        assert index_sql is not None
        assert " WHERE state IN ('held', 'reconciling')" in index_sql[0]


def test_empty_claim_tables_can_downgrade_and_upgrade(tmp_path):
    database = tmp_path / "claims-roundtrip.sqlite3"
    config = config_for(database)
    command.upgrade(config, EXPECTED_HEAD)

    command.downgrade(config, "pm04_project_runs")
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "project_record_leases" not in tables
        assert "project_task_record_cursors" not in tables
        assert "project_task_record_reads" not in tables
        batch_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(project_batches)")
        }
        assert "claim_gate_state" not in batch_columns
        assert "selection_outcome" not in batch_columns

    command.upgrade(config, EXPECTED_HEAD)
