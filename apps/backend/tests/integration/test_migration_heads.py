import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from autoflow.infrastructure.database import session as database_session


def _config(database: Path) -> Config:
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    return config


def test_studio_backend_history_has_one_merged_head(tmp_path: Path) -> None:
    scripts = ScriptDirectory.from_config(_config(tmp_path / "heads.sqlite3"))

    assert scripts.get_heads() == ["0024_environment_identity"]
    assert scripts.get_revision("0024_environment_identity").down_revision == "0023_merge_studio_android"
    assert scripts.get_revision("0023_merge_studio_android").down_revision == (
        "0022_merge_studio_pm10", "0020_merge_android_pm9",
    )
    assert scripts.get_revision("0022_merge_studio_pm10").down_revision == (
        "0021_assistant_project_scope", "pm10_shared_sheet_cursors",
    )
    assert scripts.get_revision("0021_assistant_project_scope").down_revision == "0020_recording_project_scope"
    assert scripts.get_revision("pm10_shared_sheet_cursors").down_revision == "pm09_shared_sheet_identity"
    assert scripts.get_revision("pm09_shared_sheet_identity").down_revision == "pm08_project_sync"

    assert scripts.get_revision("0020_recording_project_scope").down_revision == "0019_recording_commands"
    assert scripts.get_revision("0020_merge_android_pm9").down_revision == (
        "am01_management_operations", "pm10_shared_sheet_cursors"
    )
    assert scripts.get_revision("am01_management_operations").down_revision == (
        "0019_recording_commands"
    )
    assert scripts.get_revision("0019_recording_commands").down_revision == (
        "0018_scheduled_tasks"
    )
    assert scripts.get_revision("0018_scheduled_tasks").down_revision == (
        "0017_studio_credentials"
    )
    assert scripts.get_revision("pm08_project_sync").down_revision == (
        "pm07_environments"
    )
    assert scripts.get_revision("pm07_environments").down_revision == (
        "0013_merge_project_runtime"
    )
    assert scripts.get_revision("0013_merge_project_runtime").down_revision == (
        "0013_workflow_custom_modules",
        "pm06_project_capability_reads",
    )
    assert scripts.get_revision("0011_merge_android_project_data").down_revision == (
        "0010_android_fleet",
        "0009_merge_project_data",
    )
    assert scripts.get_revision("0012_workflow_document_requests").down_revision == (
        "0011_merge_android_project_data"
    )
    assert scripts.get_revision("0013_workflow_custom_modules").down_revision == (
        "0012_workflow_document_requests"
    )


def test_restored_android_revisions_match_the_recorded_source_bytes() -> None:
    versions = Path(database_session.__file__).with_name("migrations") / "versions"
    expected = {
        "0007_android_devices.py": "03b1c995f0cf542b1f7db29181efb39e3f9e585ffb9012e1298795a6c209ed2d",
        "0008_merge_android_m4.py": "743ef6ed9cf442377e5b8bc300e58db247ae95aea75eb8b0a8caf158b3754e01",
        "0009_merge_android_m5.py": "0d56f34fc9d647896d7dd1ece2c8ff81aca163582b27b692b318053864a0de32",
        "0010_android_fleet.py": "9e49465c1f0db103273ab7c6cbbf810307caca0f1c883d3c2add41fdafa6507c",
        "pm09_shared_sheet_identity.py": "1ef8e77cf081460e5e68cbc23514c673b064be811b909d85f9f8721f37431760",
        "pm10_shared_sheet_cursors.py": "d634201fd63942eb30b4afd6ae02bede9d234866b1961b2fe18c47c9fdffabca",
        "am01_management_operations.py": "353337c226805bee5297e5b78041453de854f33705ef8a5785ac4c8458464921",
        "0020_merge_android_pm9.py": "0c9fd992932e5d1c976030fdf62b9e8d4f0a4e075c4fec72630c1dcd5b3c9f54",
        "0022_merge_studio_pm10.py": "ae8be7c17972d900c3a94cfc2a3ea9df7303b0ed71d41987a5522e12718f6f10",
        "0023_merge_studio_android.py": "d4fdcaabcced30fe7d0eb9b7990251414ab9f269ef92338d91125b8f40accafb",
    }

    import hashlib

    assert {
        name: hashlib.sha256((versions / name).read_bytes()).hexdigest()
        for name in expected
    } == expected


@pytest.mark.parametrize("previous_head", ["am01_management_operations", "pm10_shared_sheet_cursors"])
def test_android_pm9_merge_upgrades_each_published_head_without_losing_data(tmp_path, previous_head):
    database = tmp_path / "published-head.sqlite3"
    command.upgrade(_config(database), previous_head)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO workflow_documents VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("kept", "Original workflow", '{"nodes": []}', '{}', 7, "2026-09-24", "2026-09-24"),
        )
        if previous_head == "am01_management_operations":
            connection.execute(
                """INSERT INTO android_operations
                (id, workspace_identity, request_id, target_id, action, request_digest,
                 payload, state, stage_code, stage_label, attempt, created_at)
                VALUES ('op-kept', 'workspace', 'request', 'device', 'start', 'digest',
                        '{"deviceId":"device"}', 'succeeded', 'complete', 'Complete', 1, '2026-09-24')"""
            )
        before = connection.execute("SELECT * FROM workflow_documents").fetchall()

    database_session.migrate_database(database)
    database_session.migrate_database(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            ("0024_environment_identity",)
        ]
        assert connection.execute("SELECT * FROM workflow_documents").fetchall() == before
        if previous_head == "am01_management_operations":
            assert connection.execute(
                "SELECT id, request_digest, payload, state FROM android_operations"
            ).fetchall() == [("op-kept", "digest", '{"deviceId":"device"}', "succeeded")]
        else:
            assert connection.execute("SELECT * FROM android_operations").fetchall() == []
        assert "identity_verification" in {
            row[1] for row in connection.execute("PRAGMA table_info(project_sheets_bindings)")
        }
        cursor_schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='project_task_record_cursors'"
        ).fetchone()[0]
        assert "uq_project_task_record_cursors_ref" in cursor_schema
        assert "uq_project_task_record_cursors_lease" not in cursor_schema
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

@pytest.mark.parametrize(
    "start_revision", ["0021_assistant_project_scope", "0023_merge_studio_android"]
)
def test_integrated_workspace_history_is_recognized_and_preserved(
    tmp_path: Path, start_revision: str
) -> None:
    database = tmp_path / "workspace.sqlite3"
    command.upgrade(_config(database), start_revision)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE preserved_workspace_data (value TEXT)")
        connection.execute("INSERT INTO preserved_workspace_data VALUES ('keep-me')")
    database_session.migrate_database(database)
    database_session.migrate_database(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchall() == [("0024_environment_identity",)]
        assert connection.execute(
            "SELECT value FROM preserved_workspace_data"
        ).fetchall() == [("keep-me",)]
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert "identity_verification" in {
            row[1]
            for row in connection.execute("PRAGMA table_info(project_sheets_bindings)")
        }
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='android_operations'"
        ).fetchone()
