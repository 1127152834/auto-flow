import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from autoflow.infrastructure.database import session as database_session


@pytest.mark.parametrize("existing", [False, True])
def test_pm1_upgrade_preserves_0005_resources(tmp_path: Path, existing: bool):
    database = tmp_path / "projects.sqlite3"
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    assert ScriptDirectory.from_config(config).get_heads() == ["pm01_projects"]
    preserved = {}
    if existing:
        command.upgrade(config, "0005_workflow_documents")
        with sqlite3.connect(database) as connection:
            connection.executescript("""
                INSERT INTO profiles VALUES ('profile','浏览器','{}',123,'2026-09-13','2026-09-13');
                INSERT INTO proxies VALUES ('proxy','代理',1);
                INSERT INTO proxy_pools VALUES ('pool','代理池');
                INSERT INTO model_providers
                    (id,name,provider_kind,enabled,description,connection_status,created_at,updated_at)
                    VALUES ('provider','模型供应商','custom',1,'','untested','2026-09-13','2026-09-13');
                INSERT INTO models
                    (id,provider_id,model_key,display_name,tags_json,enabled,description,created_at,updated_at)
                    VALUES ('model','provider','synthetic','测试模型','[]',1,'','2026-09-13','2026-09-13');
                INSERT INTO workflow_documents VALUES
                    ('workflow','工作流','{"nodes":[]}','{}',3,'2026-09-13','2026-09-13');
            """)
            for table in ("profiles", "proxies", "proxy_pools", "model_providers", "models", "workflow_documents"):
                preserved[table] = connection.execute(f"SELECT * FROM {table}").fetchall()
    database_session.migrate_database(database)
    database_session.migrate_database(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [("pm01_projects",)]
        assert connection.execute("SELECT * FROM projects").fetchall() == []
        assert connection.execute("SELECT * FROM project_operations").fetchall() == []
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        for table, rows in preserved.items():
            assert connection.execute(f"SELECT * FROM {table}").fetchall() == rows
