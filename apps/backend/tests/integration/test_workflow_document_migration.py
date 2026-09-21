import json
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from autoflow.infrastructure.database import session as database_session


def config_for(path: Path) -> Config:
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path}")
    return config


@pytest.mark.parametrize("existing", [False, True])
def test_workflow_command_migration_is_durable_and_preserves_documents(
    tmp_path: Path, existing: bool
):
    database = tmp_path / "workflow-commands.sqlite3"
    config = config_for(database)
    assert ScriptDirectory.from_config(config).get_heads() == [
        "0019_recording_commands"
    ]
    preserved: tuple | None = None
    if existing:
        command.upgrade(config, "0009_merge_project_data")
        with sqlite3.connect(database) as connection:
            connection.execute(
                "INSERT INTO workflow_documents VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "legacy-workflow",
                    "旧工作流",
                    json.dumps({"schemaVersion": 2, "nodes": []}),
                    json.dumps({"breakpoints": ["node"]}),
                    7,
                    "2026-09-13",
                    "2026-09-13",
                ),
            )
            preserved = connection.execute(
                "SELECT * FROM workflow_documents WHERE id='legacy-workflow'"
            ).fetchone()

    database_session.migrate_database(database)
    database_session.migrate_database(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchall() == [("0019_recording_commands",)]
        columns = {
            row[1]: row[2]
            for row in connection.execute(
                "PRAGMA table_info(workflow_document_operations)"
            )
        }
        assert columns == {
            "save_operation_id": "VARCHAR(36)",
            "workflow_id": "VARCHAR(36)",
            "request_digest": "VARCHAR(64)",
            "result": "JSON",
            "created_at": "DATETIME",
        }
        foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(workflow_document_operations)"
        ).fetchall()
        assert [(row[2], row[3], row[4], row[6]) for row in foreign_keys] == [
            ("workflow_documents", "workflow_id", "id", "RESTRICT")
        ]
        assert (
            connection.execute("SELECT * FROM workflow_document_operations").fetchall()
            == []
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        if preserved is not None:
            assert (
                connection.execute(
                    "SELECT * FROM workflow_documents WHERE id='legacy-workflow'"
                ).fetchone()
                == preserved
            )
