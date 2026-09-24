import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from autoflow.infrastructure.database import session as database_session


def _config(database: Path) -> Config:
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    return config


def test_custom_module_database_upgrades_to_integrated_head_without_data_loss(
    tmp_path: Path,
) -> None:
    database = tmp_path / "custom-modules.sqlite3"
    config = _config(database)
    command.upgrade(config, "0013_workflow_custom_modules")

    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO workflow_custom_modules
               (id, name, definition, dependency_ids, revision, usage_count,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "module-1",
                "保留模块",
                '{"nodes":[]}',
                "[]",
                3,
                2,
                "2026-09-17T00:00:00Z",
                "2026-09-17T00:00:00Z",
            ),
        )
        connection.execute(
            """INSERT INTO workflow_custom_module_requests
               (id, request_digest, kind, module_id, response, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "request-1",
                "digest-1",
                "create",
                "module-1",
                '{"id":"module-1"}',
                "2026-09-17T00:00:00Z",
            ),
        )

    database_session.migrate_database(database)
    database_session.migrate_database(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchall() == [("0023_merge_studio_android",)]
        assert connection.execute(
            "SELECT id, name, revision, usage_count FROM workflow_custom_modules"
        ).fetchall() == [("module-1", "保留模块", 3, 2)]
        assert connection.execute(
            "SELECT id, module_id FROM workflow_custom_module_requests"
        ).fetchall() == [("request-1", "module-1")]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
