from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from sqlalchemy import event
from sqlalchemy.engine import Engine

from autoflow.infrastructure.database import session as database_session


def _config(database: Path) -> Config:
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    return config


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


@pytest.mark.parametrize(
    "starting_revision",
    [
        None,
        "0005_workflow_documents",
        "0008_workflow_debug",
        "0009_merge_android_m5",
        "0009_merge_project_data",
        "0010_android_fleet",
    ],
)
def test_all_supported_histories_upgrade_without_losing_existing_rows(
    tmp_path: Path, starting_revision: str | None
) -> None:
    database = tmp_path / "compatibility.sqlite3"
    config = _config(database)
    if starting_revision is not None:
        command.upgrade(config, starting_revision)
        with sqlite3.connect(database) as connection:
            tables = _tables(connection)
            if "workflow_documents" in tables:
                connection.execute(
                    "INSERT INTO workflow_documents VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        "workflow",
                        "保留流程",
                        '{"nodes":[]}',
                        "{}",
                        7,
                        "2026-09-15",
                        "2026-09-15",
                    ),
                )
            if "android_devices" in tables:
                connection.execute(
                    "INSERT INTO android_devices VALUES (?, ?, ?)",
                    ("device", None, '{"name":"保留设备"}'),
                )
            if "android_resources" in tables:
                connection.execute(
                    "INSERT INTO android_resources VALUES (?, ?, ?)",
                    ("template", "resource", '{"name":"保留模板"}'),
                )

    database_session.migrate_database(database)
    database_session.migrate_database(database)

    with sqlite3.connect(database) as connection:
        tables = _tables(connection)
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchall() == [("pm07_environments",)]
        assert {
            "workflow_documents",
            "workflow_runs",
            "workflow_run_events",
            "workflow_run_artifacts",
            "workflow_debug_commands",
            "android_devices",
            "android_resources",
            "projects",
        } <= tables
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        if starting_revision is not None:
            assert connection.execute(
                "SELECT name, revision FROM workflow_documents WHERE id='workflow'"
            ).fetchone() == ("保留流程", 7)
        if starting_revision in {"0009_merge_android_m5", "0010_android_fleet"}:
            assert connection.execute(
                "SELECT payload FROM android_devices WHERE id='device'"
            ).fetchone() == ('{"name":"保留设备"}',)
        if starting_revision == "0010_android_fleet":
            assert connection.execute(
                "SELECT payload FROM android_resources WHERE id='resource'"
            ).fetchone() == ('{"name":"保留模板"}',)


def test_unknown_revision_fails_without_clearing_or_stamping_database(
    tmp_path: Path,
) -> None:
    database = tmp_path / "unknown.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
            INSERT INTO alembic_version VALUES ('unknown_user_revision');
            CREATE TABLE retained_data (id TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO retained_data VALUES ('sentinel', '不得修改');
            """
        )

    before = database.read_bytes()
    with pytest.raises(CommandError):
        database_session.migrate_database(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT * FROM alembic_version").fetchall() == [
            ("unknown_user_revision",)
        ]
        assert connection.execute("SELECT * FROM retained_data").fetchall() == [
            ("sentinel", "不得修改")
        ]
    assert database.read_bytes() == before


def test_interrupted_branch_merge_rolls_back_and_can_restart(tmp_path: Path) -> None:
    database = tmp_path / "interrupted.sqlite3"
    command.upgrade(_config(database), "0008_workflow_debug")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO workflow_documents VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "workflow",
                "迁移中断仍保留",
                '{"nodes":[]}',
                "{}",
                3,
                "2026-09-15",
                "2026-09-15",
            ),
        )

    def fail_mid_upgrade(
        connection, cursor, statement, parameters, context, executemany
    ) -> None:
        if "CREATE TABLE android_resources" in statement:
            raise RuntimeError("synthetic branch merge interruption")

    event.listen(Engine, "before_cursor_execute", fail_mid_upgrade)
    try:
        with pytest.raises(RuntimeError, match="synthetic branch merge interruption"):
            database_session.migrate_database(database)
    finally:
        event.remove(Engine, "before_cursor_execute", fail_mid_upgrade)

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchall() == [("0008_workflow_debug",)]
        assert "android_devices" not in _tables(connection)
        assert "android_resources" not in _tables(connection)
        assert connection.execute(
            "SELECT name, revision FROM workflow_documents WHERE id='workflow'"
        ).fetchone() == ("迁移中断仍保留", 3)

    database_session.migrate_database(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchall() == [("pm07_environments",)]
        assert {"android_devices", "android_resources"} <= _tables(connection)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
