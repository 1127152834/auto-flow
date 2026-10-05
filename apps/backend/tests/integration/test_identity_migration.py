"""Remediation M4 S3 (R4-10; AC4-05, AC4-06): saved environments become identities without changing their seeds."""

from __future__ import annotations

import json
import sqlite3

from alembic import command

from autoflow.infrastructure.database.session import migrate_database
from tests.integration.test_project_data_migrations import (
    add_record,
    config_for,
    seed_project,
    seed_table,
)


def _package(seed: int, timezone: str | None = "Asia/Shanghai", locale: str | None = "zh-CN") -> str:
    return json.dumps({
        "schemaVersion": 1, "profileId": "profile-1", "kernelId": "public:146",
        "frozenConfiguration": {"fingerprintSeed": seed, "profileSpec": {"timezone": timezone, "locale": locale}},
    })


def _environment(connection, environment_id: str, name: str, package: str | None, state: str = "ready") -> None:
    connection.execute(
        """INSERT INTO project_environments
        (id,project_id,name,name_key,notes,state,profile_id,content_generation,metadata_revision,current_digest,
         identity_package,keep_browser_cache,created_from_source,created_from_task_id,unavailable_reason,created_at,updated_at)
        VALUES (?,?,?,?,'',?, 'profile-1',1,1,'d',?,0,'newFromProfile',NULL,NULL,'2026-09-13','2026-09-13')""",
        (environment_id, "p", name, name.casefold(), state, package),
    )


def _upgrade_with(tmp_path, seed_data):
    path = tmp_path / "identities.sqlite3"
    command.upgrade(config_for(path), "rm4_identities")
    with sqlite3.connect(path) as connection:
        seed_project(connection)
        seed_table(connection)
        seed_data(connection)
    migrate_database(path)
    return path


def test_each_saved_environment_becomes_an_identity_keeping_its_seed(tmp_path):
    def data(connection):
        _environment(connection, "e1", "店铺A", _package(42424))
        _environment(connection, "e2", "店铺B", _package(42424))  # an older duplicate seed
        _environment(connection, "e3", "店铺C", _package(55555, None, None))
        _environment(connection, "e4", "无身份包", None)
        _environment(connection, "e5", "已删除", _package(66666), state="deleted")
        add_record(connection, key="r1")
        connection.execute("UPDATE project_data_records SET current_environment_id='e1' WHERE key_value='r1'")

    path = _upgrade_with(tmp_path, data)
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            """SELECT i.environment_id, i.name, s.seed_value, s.legacy_shared, i.region, i.origin, i.template_profile_id
               FROM identities i JOIN seed_registry s ON s.id = i.seed_id ORDER BY i.environment_id"""
        ).fetchall()
        by_environment = {row[0]: row for row in rows}
        assert set(by_environment) == {"e1", "e2", "e3", "e4"}  # deleted environments are left alone
        assert by_environment["e1"][2] == by_environment["e2"][2] == 42424
        assert by_environment["e1"][3] == by_environment["e2"][3] == 1  # shared, reported, kept
        assert by_environment["e3"][2] == 55555 and by_environment["e3"][3] == 0
        assert json.loads(by_environment["e1"][4]) == {"timezone": "Asia/Shanghai", "locale": "zh-CN"}
        assert json.loads(by_environment["e3"][4]) == {}
        assert json.loads(by_environment["e4"][5]) == {"environmentId": "e4", "seedMissing": True}
        assert json.loads(by_environment["e1"][5]) == {"environmentId": "e1", "seedMissing": False}
        assert by_environment["e1"][6] == "profile-1" and by_environment["e1"][1] == "店铺A"
        linked = connection.execute("SELECT current_identity_id FROM project_data_records WHERE key_value='r1'").fetchone()[0]
        assert linked == connection.execute("SELECT id FROM identities WHERE environment_id='e1'").fetchone()[0]


def test_the_upgrade_backs_up_the_database_first(tmp_path):
    _upgrade_with(tmp_path, lambda connection: _environment(connection, "e1", "店铺A", _package(12345)))
    backups = sorted((tmp_path / "backups").glob("identities-*.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("rm4_identities",)
        assert connection.execute("SELECT count(*) FROM project_environments").fetchone() == (1,)


def test_an_up_to_date_database_is_not_backed_up_again(tmp_path):
    path = tmp_path / "fresh.sqlite3"
    migrate_database(path)
    migrate_database(path)
    assert not (tmp_path / "backups").exists()
