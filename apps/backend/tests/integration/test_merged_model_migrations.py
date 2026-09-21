import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from autoflow.infrastructure.database import session as database_session


@pytest.mark.parametrize(
    "revision",
    [None, "0001_browser_resources", "0002_proxy_management", "0002_model_management", "0008_workflow_debug", "pm01_projects", "pm02_schema_drafts"],
)
def test_merge_upgrade_preserves_each_branch_database(
    tmp_path: Path, revision: str | None
):
    database = tmp_path / "merged.sqlite3"
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    assert ScriptDirectory.from_config(config).get_heads() == ["0019_recording_commands"]
    if revision:
        command.upgrade(config, revision)
        with sqlite3.connect(database) as connection:
            connection.execute(
                "INSERT INTO proxy_pools (id,name) VALUES ('existing','Retained group')"
            )
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
            ("0019_recording_commands",)
        ]
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"profiles", "proxy_projections", "proxy_group_details", "model_providers", "models", "kernel_operations", "workflow_documents"} <= tables
        assert {"workflow_runs", "workflow_run_events", "workflow_run_artifacts", "workflow_debug_commands"} <= tables
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        if revision:
            assert connection.execute(
                "SELECT name FROM proxy_pools WHERE id='existing'"
            ).fetchone() == ("Retained group",)
        if revision == "0002_proxy_management":
            assert connection.execute(
                "SELECT proxy_pool_id FROM proxy_group_details"
            ).fetchall() == [("existing",)]
        if revision == "0002_model_management":
            assert connection.execute("SELECT secret_ref FROM model_credential_cleanup").fetchall() == [("synthetic-ref",)]


def test_retired_studio_data_survives_application_startup(tmp_path: Path):
    from fastapi.testclient import TestClient

    from autoflow.bootstrap.app import create_app
    from autoflow.bootstrap.config import Settings
    from autoflow.infrastructure.filesystem.paths import AppPaths
    from tests.fixtures.model_management import FakeCredentialStore, FakeModelGateway

    paths = AppPaths.from_data_dir(tmp_path)
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{paths.database}")
    paths.database.parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(config, "0008_workflow_debug")
    statements = {
        "workflow_documents": (
            "INSERT INTO workflow_documents VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("document", "Archived Studio", '{"schemaVersion":2}', '{"breakpoints":["node"]}', 7, "2026-09-13", "2026-09-13"),
        ),
        "workflow_runs": (
            "INSERT INTO workflow_runs VALUES (?, ?, ?, ?, ?, ?)",
            ("run", "document", "request-hash", "2026-09-13", 1, '{"state":"paused"}'),
        ),
        "workflow_run_events": (
            "INSERT INTO workflow_run_events VALUES (?, ?, ?)",
            ("run", 1, '{"type":"paused"}'),
        ),
        "workflow_run_artifacts": (
            "INSERT INTO workflow_run_artifacts (run_id,id,ordinal,node_id,execution_id,payload,purpose,event_seq) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("run", "artifact", 1, "node", "execution", '{"relativePath":"artifacts/result.json"}', "result", 1),
        ),
        "workflow_debug_commands": (
            "INSERT INTO workflow_debug_commands VALUES (?, ?, ?, ?)",
            ("run", "command", "command-hash", '{"status":"applied"}'),
        ),
    }
    artifact = paths.workspace / "runs" / "run" / "artifacts" / "result.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b'{"saved":"evidence"}')
    with sqlite3.connect(paths.database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        for statement, values in statements.values():
            connection.execute(statement, values)
        before = {
            table: connection.execute(f"SELECT * FROM {table}").fetchall()
            for table in statements
        }

    app = create_app(
        Settings(data_dir=str(tmp_path), instance_id="retired-studio"),
        credential_store=FakeCredentialStore(), model_gateway=FakeModelGateway(),
    )
    with TestClient(app):
        pass

    with sqlite3.connect(paths.database) as connection:
        after = {
            table: connection.execute(f"SELECT * FROM {table}").fetchall()
            for table in statements
        }
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("0019_recording_commands",)
        status, sequence, completed_at = connection.execute(
            "SELECT status, last_sequence, completed_at "
            "FROM project_workflow_runs WHERE id='run'"
        ).fetchone()
        assert (status, sequence) == ("interrupted", 1)
        assert completed_at is not None and completed_at != "2026-09-13"
        source_revision, provenance = connection.execute(
            "SELECT source_revision, provenance "
            "FROM project_workflow_prepared_contents "
            "WHERE workflow_id='document'"
        ).fetchone()
        assert source_revision is None
        assert '"legacy":true' in provenance
        assert connection.execute(
            "SELECT kind, node_id, occurred_at "
            "FROM project_workflow_run_events "
            "WHERE run_id='run' AND sequence=1"
        ).fetchone() == ("checkpoint", None, "2026-09-13")
    assert after == before
    assert artifact.read_bytes() == b'{"saved":"evidence"}'
