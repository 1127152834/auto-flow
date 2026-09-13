import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from autoflow.infrastructure.database import session as database_session


@pytest.mark.parametrize(
    "revision", [None, "0001_browser_resources", "0002_proxy_management", "0002_model_management"]
)
def test_merge_upgrade_preserves_each_branch_database(tmp_path: Path, revision: str | None):
    database = tmp_path / "merged.sqlite3"
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    assert ScriptDirectory.from_config(config).get_heads() == ["0009_merge_android_m5"]
    if revision:
        command.upgrade(config, revision)
        with sqlite3.connect(database) as connection:
            connection.execute("INSERT INTO proxy_pools (id,name) VALUES ('existing','Retained group')")
            if revision == "0002_proxy_management":
                connection.execute(
                    "INSERT INTO proxy_group_details (proxy_pool_id,created_at,updated_at) "
                    "VALUES ('existing','2026-09-12','2026-09-12')"
                )
            if revision == "0002_model_management":
                connection.execute(
                    "INSERT INTO model_credential_cleanup (secret_ref,created_at) "
                    "VALUES ('synthetic-ref','2026-09-12')"
                )
    database_session.migrate_database(database)
    database_session.migrate_database(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            ("0009_merge_android_m5",)
        ]
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"profiles", "proxy_projections", "proxy_group_details", "model_providers", "models", "kernel_operations", "workflow_documents"} <= tables
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        if revision:
            assert connection.execute("SELECT name FROM proxy_pools WHERE id='existing'").fetchone() == ("Retained group",)
        if revision == "0002_proxy_management":
            assert connection.execute("SELECT proxy_pool_id FROM proxy_group_details").fetchall() == [("existing",)]
        if revision == "0002_model_management":
            assert connection.execute("SELECT secret_ref FROM model_credential_cleanup").fetchall() == [("synthetic-ref",)]
