"""Exercise the shipped migration, with SQLite foreign keys enabled."""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from autoflow.infrastructure.database import session as database_session


def config_for(path):
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path}")
    return config


def seed_project(connection, project="p"):
    connection.execute(
        "INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            project,
            project,
            project,
            "",
            project,
            "{}",
            1,
            "active",
            "2026-09-13",
            "2026-09-13",
            None,
        ),
    )


def seed_table(connection, table="t", generation="g", project="p"):
    connection.execute(
        """INSERT INTO project_data_tables
        (id,project_id,name,name_key,search_text,description,source_kind,current_generation,table_revision,
        identity,slot_definitions,created_at,updated_at)
        VALUES (?,?,?,?,?,?,'local',?,1,'{"mode":"system"}','[]',?,?)""",
        (
            table,
            project,
            table,
            table,
            table.casefold(),
            "",
            generation,
            "2026-09-13",
            "2026-09-13",
        ),
    )
    connection.execute(
        """INSERT INTO project_data_generations
        (id,project_id,table_id,identity,source,created_at)
        VALUES (?,?,?,'{"mode":"system"}','{}','2026-09-13')""",
        (generation, project, table),
    )


def add_record(
    connection,
    key_type="text",
    key="1",
    generation="g",
    table="t",
    project="p",
    status=None,
):
    connection.execute(
        """INSERT INTO project_data_records
        (project_id,table_id,dataset_generation,key_type,key_value,values_json,record_slots,
        status_id,current_environment_id,content_revision,status_revision,link_revision,
        deleted,created_at,updated_at)
        VALUES (?,?,?,?,?,'{}','[]',?,NULL,1,1,1,0,'2026-09-13','2026-09-13')""",
        (project, table, generation, key_type, key, status),
    )


@pytest.mark.parametrize("existing", [False, True])
def test_pm2_upgrade_preserves_projects_and_has_one_head(tmp_path, existing):
    path = tmp_path / "data.sqlite3"
    config = config_for(path)

    assert ScriptDirectory.from_config(config).get_heads() == ["0015_workflow_mcp"]

    before = []
    if existing:
        command.upgrade(config, "pm01_projects")
        with sqlite3.connect(path) as c:
            seed_project(c)
            before = c.execute("SELECT * FROM projects").fetchall()
    database_session.migrate_database(path)
    database_session.migrate_database(path)
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT * FROM projects").fetchall() == before
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
        tables = {
            row[0]
            for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {
            "project_data_tables",
            "project_data_generations",
            "project_data_fields",
            "project_data_statuses",
            "project_data_records",
            "project_data_changes",
            "project_data_impacts",
        } <= tables


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "data.sqlite3"
    database_session.migrate_database(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        seed_project(connection)
        seed_table(connection)
        yield connection


def test_typed_identity_generation_uniqueness_and_record_revisions(database):
    add_record(database, key="001")
    add_record(database, key="1")
    add_record(database, key_type="integer", key="1")
    with pytest.raises(sqlite3.IntegrityError):
        add_record(database, key="1")
    database.execute(
        "INSERT INTO project_data_generations VALUES ('g2','p','t','{}','{}','2026-09-13')"
    )
    add_record(database, key="1", generation="g2")
    database.execute(
        "UPDATE project_data_records SET content_revision=content_revision+1 WHERE dataset_generation='g2'"
    )
    assert database.execute(
        "SELECT content_revision,status_revision,link_revision FROM project_data_records WHERE dataset_generation='g2'"
    ).fetchone() == (2, 1, 1)
    with pytest.raises(sqlite3.IntegrityError):
        database.execute("UPDATE project_data_records SET status_revision=0")


def test_generation_and_status_cannot_cross_project_or_table(database):
    seed_project(database, "other")
    seed_table(database, "other-table", "other-gen", "other")
    database.execute(
        "INSERT INTO project_data_statuses (id,project_id,table_id,name,name_key,color,position,status_revision) VALUES ('status','other','other-table','done','done','#AABBCC',0,1)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        add_record(database, status="status")
    with pytest.raises(sqlite3.IntegrityError):
        add_record(database, generation="other-gen")
    with pytest.raises(sqlite3.IntegrityError):
        add_record(database, project="other")


def test_status_references_in_historical_generation_prevent_delete(database):
    database.execute(
        "INSERT INTO project_data_statuses (id,project_id,table_id,name,name_key,color,position,status_revision) VALUES ('status','p','t','done','done','#AABBCC',0,1)"
    )
    add_record(database, status="status")
    database.execute(
        "INSERT INTO project_data_generations VALUES ('g2','p','t','{}','{}','2026-09-13')"
    )
    database.execute(
        "UPDATE project_data_tables SET current_generation='g2' WHERE id='t'"
    )
    with pytest.raises(sqlite3.IntegrityError):
        database.execute("DELETE FROM project_data_statuses WHERE id='status'")
    assert database.execute("SELECT count(*) FROM project_data_records").fetchone() == (
        1,
    )


def test_field_key_is_literal_and_unique_per_generation(database):
    def field(field_id, key):
        database.execute(
            """INSERT INTO project_data_fields
            VALUES (?,?,?,?,?,?,'string',0,1,0,'{}',1,0)""",
            (field_id, "p", "t", "g", key, key),
        )

    field("f1", "user.name")
    field("f2", "User.name")
    with pytest.raises(sqlite3.IntegrityError):
        field("f3", "user.name")
    assert database.execute(
        "SELECT key FROM project_data_fields ORDER BY key"
    ).fetchall() == [("User.name",), ("user.name",)]


def test_pm2_orm_metadata_matches_shipped_migration(tmp_path):
    from importlib import import_module

    from sqlalchemy import create_engine, inspect

    from autoflow.infrastructure.database.models import Base

    import_module("autoflow.infrastructure.database.project_data_models")
    path = tmp_path / "metadata.sqlite3"
    database_session.migrate_database(path)
    engine = create_engine(f"sqlite:///{path}")
    inspector = inspect(engine)
    for name, table in Base.metadata.tables.items():
        if not name.startswith("project_data_"):
            continue
        assert {column.name for column in table.columns} == {
            column["name"] for column in inspector.get_columns(name)
        }
        assert set(table.primary_key.columns.keys()) == set(
            inspector.get_pk_constraint(name)["constrained_columns"]
        )
        assert {
            tuple(c.columns.keys())
            for c in table.constraints
            if c.__class__.__name__ == "UniqueConstraint"
        } == {tuple(c["column_names"]) for c in inspector.get_unique_constraints(name)}
        assert {tuple(c.column_keys) for c in table.foreign_key_constraints} == {
            tuple(c["constrained_columns"]) for c in inspector.get_foreign_keys(name)
        }
    engine.dispose()


def test_current_generation_must_belong_to_table_at_commit(database):
    seed_project(database, "other")
    seed_table(database, "other-table", "other-generation", "other")
    database.commit()
    database.execute(
        "UPDATE project_data_tables SET current_generation='other-generation' WHERE id='t'"
    )
    with pytest.raises(sqlite3.IntegrityError):
        database.commit()
    database.rollback()
    assert database.execute(
        "SELECT current_generation FROM project_data_tables WHERE id='t'"
    ).fetchone() == ("g",)


def test_change_operation_cannot_cross_project(database):
    seed_project(database, "other")
    database.execute("""INSERT INTO project_operations VALUES
        ('op','other','key','createProject','digest','succeeded',1,'{}','{}',NULL,
        '2026-09-13','2026-09-13','2026-09-13')""")
    with pytest.raises(sqlite3.IntegrityError):
        database.execute("""INSERT INTO project_data_changes VALUES
            ('change','p','op',0,'{}','manual',NULL,'{}','2026-09-13')""")


def test_impact_confirmation_ids_are_not_reused_after_restart(tmp_path):
    path = tmp_path / "impact.sqlite3"
    database_session.migrate_database(path)
    sql = """INSERT INTO project_data_impacts
        (project_id,action,target,change_digest,expected_revisions,facts_digest,report,expires_at)
        VALUES ('p','deleteRecord','{}','digest','{}','facts','{}','2026-09-13')"""
    with sqlite3.connect(path) as c:
        seed_project(c)
        first = c.execute(sql).lastrowid
        c.execute("DELETE FROM project_data_impacts")
    with sqlite3.connect(path) as c:
        second = c.execute(sql).lastrowid
    assert second > first


def test_downgrade_then_upgrade_preserves_pm1_projects(tmp_path):
    path = tmp_path / "rollback.sqlite3"
    config = config_for(path)
    database_session.migrate_database(path)
    with sqlite3.connect(path) as c:
        seed_project(c)
        seed_table(c)
        add_record(c)
    command.downgrade(config, "pm01_projects")
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT id FROM projects").fetchall() == [("p",)]
        assert set(c.execute("SELECT version_num FROM alembic_version").fetchall()) == {
            ("pm01_projects",),

            ("0010_android_fleet",),

        }
    database_session.migrate_database(path)
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT id FROM projects").fetchall() == [("p",)]
        assert c.execute("SELECT * FROM project_data_tables").fetchall() == []
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("starting_revision", ["pm01_projects", "base"])
def test_failed_upgrade_rolls_back_ddl_and_can_restart(tmp_path, starting_revision):
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    path = tmp_path / "interrupted.sqlite3"
    config = config_for(path)
    command.upgrade(config, starting_revision)

    def fail_mid_migration(
        connection, cursor, statement, parameters, context, executemany
    ):
        if "CREATE TABLE project_data_generations" in statement:
            raise RuntimeError("synthetic migration interruption")

    event.listen(Engine, "before_cursor_execute", fail_mid_migration)
    try:
        with pytest.raises(RuntimeError, match="synthetic migration interruption"):
            database_session.migrate_database(path)
    finally:
        event.remove(Engine, "before_cursor_execute", fail_mid_migration)
    with sqlite3.connect(path) as connection:
        partial = connection.execute(
            "SELECT name FROM sqlite_master WHERE name LIKE 'project_data_%' OR name='uq_project_operations_scope'"
        ).fetchall()
        assert partial == []
    database_session.migrate_database(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"

        ).fetchone() == ("0015_workflow_mcp",)

        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
