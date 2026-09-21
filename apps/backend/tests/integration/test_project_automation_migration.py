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


@pytest.mark.parametrize(
    "previous", [None, "pm01_projects", "0011_workflow_runtime_contracts"]
)
def test_automation_upgrade_preserves_existing_rows_and_enforces_binding(
    tmp_path, previous
):
    database = tmp_path / "automation-migration.sqlite3"
    config = config_for(database)
    assert ScriptDirectory.from_config(config).get_heads() == ["pm09_shared_sheet_identity"]
    before = {}
    if previous:
        command.upgrade(config, previous)
        with sqlite3.connect(database) as connection:
            connection.execute(
                "INSERT INTO workflow_documents VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "workflow-fixture",
                    "既有流程",
                    json.dumps({"original": True}),
                    "{}",
                    7,
                    "2026-09-15",
                    "2026-09-15",
                ),
            )
            connection.execute(
                "INSERT INTO projects (id,name,name_key,description,search_text,default_resources,management_revision,lifecycle_state,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    "project-fixture",
                    "既有项目",
                    "既有项目",
                    "",
                    "既有项目",
                    "{}",
                    1,
                    "active",
                    "2026-09-15",
                    "2026-09-15",
                ),
            )
            for table in ("workflow_documents", "projects"):
                before[table] = connection.execute(f"SELECT * FROM {table}").fetchall()
    database_session.migrate_database(database)
    database_session.migrate_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("pm09_shared_sheet_identity",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        for table, rows in before.items():
            assert connection.execute(f"SELECT * FROM {table}").fetchall() == rows
        foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(project_automations)"
        ).fetchall()
        assert {(row[2], row[3], row[6]) for row in foreign_keys} == {
            ("projects", "project_id", "RESTRICT"),
            ("workflow_documents", "workflow_id", "RESTRICT"),
        }
        assert connection.execute("SELECT * FROM project_automations").fetchall() == []
        if previous:
            values = (
                "automation-fixture",
                "project-fixture",
                "workflow-fixture",
                "A",
                "a",
                "a",
                "",
                1,
                '{"inputs":[]}',
                "[]",
                "{}",
                "{}",
                "2026-09-15",
                "2026-09-15",
            )
            # Use explicit columns so the test does not depend on physical ordering.
            insert = "INSERT INTO project_automations (id,project_id,workflow_id,name,name_key,search_text,description,management_revision,input_plan,parameter_schema,environment_policy,run_policy,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            connection.execute(insert, values)
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    insert, ("second", *values[1:3], "B", "b", "b", *values[6:])
                )
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "DELETE FROM workflow_documents WHERE id='workflow-fixture'"
                )
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM projects WHERE id='project-fixture'")


def test_empty_downgrade_roundtrip_and_nonempty_downgrade_preserves_data(tmp_path):
    database = tmp_path / "downgrade.sqlite3"
    config = config_for(database)
    command.upgrade(config, "head")
    command.downgrade(config, "0011_workflow_runtime_contracts")
    command.upgrade(config, "head")
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "INSERT INTO workflow_documents VALUES (?,?,?,?,?,?,?)",
            ("w", "W", "{}", "{}", 1, "2026-09-15", "2026-09-15"),
        )
        connection.execute(
            "INSERT INTO projects (id,name,name_key,description,search_text,default_resources,management_revision,lifecycle_state,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("p", "P", "p", "", "p", "{}", 1, "active", "2026-09-15", "2026-09-15"),
        )
        connection.execute(
            "INSERT INTO project_automations (id,project_id,workflow_id,name,name_key,search_text,description,management_revision,input_plan,parameter_schema,environment_policy,run_policy,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "a",
                "p",
                "w",
                "A",
                "a",
                "a",
                "",
                1,
                "{}",
                "[]",
                "{}",
                "{}",
                "2026-09-15",
                "2026-09-15",
            ),
        )
        original = connection.execute("SELECT * FROM project_automations").fetchall()
    with pytest.raises(RuntimeError, match="configuration exists"):
        command.downgrade(config, "0011_workflow_runtime_contracts")
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT * FROM project_automations").fetchall()
            == original
        )
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("pm09_shared_sheet_identity",)
