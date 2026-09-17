from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from autoflow.infrastructure.database import session as database_session

EXPECTED_HEAD = "0013_merge_project_runtime"


def _config(path: Path) -> Config:
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path}")
    return config


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def _seed_shared_rows(connection: sqlite3.Connection) -> dict[str, list[tuple]]:
    connection.execute("PRAGMA defer_foreign_keys=ON")
    connection.execute(
        "INSERT INTO profiles VALUES (?,?,?,?,?,?)",
        (
            "profile-retained",
            "浏览器",
            "{}",
            123,
            "2026-09-13",
            "2026-09-13",
        ),
    )
    connection.execute(
        "INSERT INTO proxies VALUES (?,?,?)", ("proxy-retained", "代理", 1)
    )
    connection.execute(
        """INSERT INTO model_providers
        (id,name,provider_kind,enabled,description,connection_status,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (
            "provider-retained",
            "模型供应商",
            "custom",
            1,
            "",
            "untested",
            "2026-09-13",
            "2026-09-13",
        ),
    )
    connection.execute(
        """INSERT INTO projects
        (id,name,name_key,description,search_text,default_resources,
         management_revision,lifecycle_state,created_at,updated_at,last_opened_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "project-retained",
            "保留项目",
            "保留项目",
            "",
            "保留项目",
            "{}",
            1,
            "active",
            "2026-09-13",
            "2026-09-13",
            None,
        ),
    )
    connection.execute(
        """INSERT INTO project_data_tables
        (id,project_id,name,name_key,search_text,description,source_kind,
         current_generation,table_revision,identity,slot_definitions,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "table-retained",
            "project-retained",
            "保留数据",
            "保留数据",
            "保留数据",
            "",
            "local",
            "generation-retained",
            1,
            '{"mode":"system"}',
            "[]",
            "2026-09-13",
            "2026-09-13",
        ),
    )
    connection.execute(
        """INSERT INTO project_data_generations
        (id,project_id,table_id,identity,source,created_at)
        VALUES (?,?,?,?,?,?)""",
        (
            "generation-retained",
            "project-retained",
            "table-retained",
            '{"mode":"system"}',
            '{"kind":"local"}',
            "2026-09-13",
        ),
    )
    connection.execute(
        """INSERT INTO project_data_records
        (project_id,table_id,dataset_generation,key_type,key_value,values_json,
         record_slots,status_id,current_environment_id,content_revision,status_revision,
         link_revision,deleted,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "project-retained",
            "table-retained",
            "generation-retained",
            "text",
            "001",
            '{"title":"保留记录"}',
            "[]",
            None,
            None,
            1,
            1,
            1,
            0,
            "2026-09-13",
            "2026-09-13",
        ),
    )
    tables = (
        "profiles",
        "proxies",
        "model_providers",
        "projects",
        "project_data_tables",
        "project_data_generations",
        "project_data_records",
    )
    return {
        table: connection.execute(f"SELECT * FROM {table}").fetchall()
        for table in tables
    }


def _seed_legacy_runtime(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        INSERT INTO workflow_documents VALUES
          ('workflow-active','旧工作流','{"editedAfterStart":true}','{}',7,
           '2026-09-13T10:00:00+00:00','2026-09-13T10:00:00+00:00');
        INSERT INTO workflow_documents VALUES
          ('workflow-done','旧完成工作流','{"editedAfterStart":true}','{}',4,
           '2026-09-13T10:00:00+00:00','2026-09-13T10:00:00+00:00');
        """
    )
    common = {
        "profileId": "profile-retained",
        "profileName": "浏览器",
        "profileSnapshot": {"language": "zh-CN"},
        "nodeOrder": ["open"],
        "artifacts": [],
        "warnings": [],
    }
    active_payload = {
        **common,
        "runId": "run-active",
        "workflowId": "workflow-active",
        "name": "启动快照",
        "state": "running",
        "document": {
            "schemaVersion": 2,
            "name": "启动快照",
            "nodes": [
                {
                    "id": "open",
                    "type": "open_page",
                    "config": {"url": "https://snapshot.test"},
                }
            ],
        },
        "layout": {"breakpoints": ["open"]},
        "currentNodeId": "open",
        "startedAt": "2026-09-13T10:01:00+00:00",
        "finishedAt": None,
        "latestSeq": 3,
        "completedNodeIds": [],
        "error": None,
    }
    done_payload = {
        **common,
        "runId": "run-done",
        "workflowId": "workflow-done",
        "name": "完成快照",
        "state": "succeeded",
        "document": {
            "schemaVersion": 2,
            "name": "完成快照",
            "nodes": [
                {
                    "id": "open",
                    "type": "open_page",
                    "config": {"url": "https://done.test"},
                }
            ],
        },
        "layout": {"breakpoints": []},
        "currentNodeId": None,
        "startedAt": "2026-09-13T10:02:00+00:00",
        "finishedAt": "2026-09-13T10:03:00+00:00",
        "latestSeq": 1,
        "completedNodeIds": ["open"],
        "error": {"code": "historical-warning"},
    }
    connection.execute(
        "INSERT INTO workflow_runs VALUES (?,?,?,?,?,?)",
        (
            "run-active",
            "workflow-active",
            "a" * 64,
            "2026-09-13T10:01:00+00:00",
            1,
            json.dumps(active_payload, ensure_ascii=False),
        ),
    )
    connection.execute(
        "INSERT INTO workflow_runs VALUES (?,?,?,?,?,?)",
        (
            "run-done",
            "workflow-done",
            "b" * 64,
            "2026-09-13T10:02:00+00:00",
            None,
            json.dumps(done_payload, ensure_ascii=False),
        ),
    )
    connection.executescript(
        """
        INSERT INTO workflow_run_events VALUES
          ('run-active',1,
           '{"type":"node_started","nodeId":"open","timestamp":"2026-09-13T10:01:01+00:00"}');
        INSERT INTO workflow_run_events VALUES
          ('run-done',1,
           '{"type":"completed","timestamp":"2026-09-13T10:02:01+00:00"}');
        INSERT INTO workflow_run_artifacts
          (run_id,id,ordinal,node_id,execution_id,payload,purpose,event_seq)
          VALUES
          ('run-done','artifact-retained',1,'open','execution-1',
           '{"relativePath":"artifacts/result.json"}','result',1);
        INSERT INTO workflow_debug_commands VALUES
          ('run-done','command-retained','cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
           '{"status":"applied"}');
        """
    )


def test_empty_database_upgrades_to_one_runtime_head_with_complete_v2_schema(tmp_path):
    database = tmp_path / "empty.sqlite3"
    config = _config(database)
    assert ScriptDirectory.from_config(config).get_heads() == [EXPECTED_HEAD]

    database_session.migrate_database(database)
    database_session.migrate_database(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchall() == [(EXPECTED_HEAD,)]
        assert {
            "id",
            "prepare_operation_id",
            "request_digest",
            "workflow_id",
            "source_revision",
            "checksum",
            "document",
            "execution_plan",
            "adapter_version",
            "capability_requirements",
            "provenance",
            "created_at",
        } <= _table_columns(connection, "project_workflow_prepared_contents")
        assert {
            "id",
            "run_request_id",
            "request_digest",
            "prepared_content_id",
            "parameters",
            "input_snapshot_ref",
            "resource_request",
            "capability_bindings",
            "status",
            "status_revision",
            "execution_generation",
            "last_sequence",
            "created_at",
            "updated_at",
            "started_at",
            "completed_at",
            "error",
        } <= _table_columns(connection, "project_workflow_runs")
        assert {
            "run_id",
            "sequence",
            "event_id",
            "execution_generation",
            "kind",
            "node_id",
            "node_visit_id",
            "attempt",
            "occurred_at",
            "payload",
        } <= _table_columns(connection, "project_workflow_run_events")
        assert "active_slot" not in _table_columns(connection, "project_workflow_runs")
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
    "start_revision", ["0005_workflow_documents", "0008_workflow_debug"]
)
def test_upgrade_from_legacy_studio_reaches_v2_without_replaying_unknown_work(
    tmp_path, start_revision
):
    database = tmp_path / f"legacy-{start_revision}.sqlite3"
    config = _config(database)
    command.upgrade(config, start_revision)
    if start_revision == "0008_workflow_debug":
        with sqlite3.connect(database) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            _seed_legacy_runtime(connection)

    command.upgrade(config, "head")

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == (EXPECTED_HEAD,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        if start_revision == "0008_workflow_debug":
            active = connection.execute(
                "SELECT status, status_revision, completed_at, last_sequence "
                "FROM project_workflow_runs WHERE id='run-active'"
            ).fetchone()
            assert active is not None
            assert active[0] == "interrupted"
            assert active[1] >= 1
            assert active[2] is not None
            assert active[3] == 3
            assert active[0] not in {"queued", "running", "reconciling"}

            done = connection.execute(
                "SELECT status, completed_at, error, resource_request "
                "FROM project_workflow_runs WHERE id='run-done'"
            ).fetchone()
            assert done[0] == "succeeded"
            assert done[1] == "2026-09-13T10:03:00+00:00"
            assert json.loads(done[2]) == {"code": "historical-warning"}
            assert json.loads(done[3])["profileId"] == "profile-retained"


def test_0009_upgrade_preserves_shared_facts_and_maps_legacy_provenance(tmp_path):
    database = tmp_path / "preserved.sqlite3"
    config = _config(database)
    command.upgrade(config, "0009_merge_project_data")
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        preserved = _seed_shared_rows(connection)
        _seed_legacy_runtime(connection)
        artifact_before = connection.execute(
            "SELECT * FROM workflow_run_artifacts"
        ).fetchall()
        debug_before = connection.execute(
            "SELECT * FROM workflow_debug_commands"
        ).fetchall()

    command.upgrade(config, "head")

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        for table, rows in preserved.items():
            assert connection.execute(f"SELECT * FROM {table}").fetchall() == rows
        assert (
            connection.execute("SELECT * FROM workflow_run_artifacts").fetchall()
            == artifact_before
        )
        assert (
            connection.execute("SELECT * FROM workflow_debug_commands").fetchall()
            == debug_before
        )

        rows = connection.execute(
            "SELECT source_revision, provenance, document, execution_plan, adapter_version "
            "FROM project_workflow_prepared_contents ORDER BY workflow_id"
        ).fetchall()
        assert len(rows) == 2
        for (
            source_revision,
            provenance_raw,
            document_raw,
            execution_plan_raw,
            adapter_version,
        ) in rows:
            provenance = json.loads(provenance_raw)
            document = json.loads(document_raw)
            execution_plan = json.loads(execution_plan_raw)
            assert source_revision is None
            assert provenance.get("legacy") is True
            assert provenance.get("legacyRunId") in {"run-active", "run-done"}
            assert provenance.get("adapterVersion") == adapter_version
            assert adapter_version.startswith("legacy-")
            assert document
            assert execution_plan
            assert document.get("editedAfterStart") is None
            assert execution_plan["orderedNodeIds"] == ["open"]
            assert execution_plan["nodes"][0]["snapshot"]["id"] == "open"

        events = connection.execute(
            "SELECT run_id, sequence, event_id, execution_generation, kind, "
            "node_id, node_visit_id, attempt, occurred_at, payload "
            "FROM project_workflow_run_events ORDER BY run_id, sequence"
        ).fetchall()
        assert len(events) == 2
        assert all(row[2] for row in events)
        assert all(row[3] >= 0 for row in events)
        assert all(row[4] for row in events)
        assert all(row[8] for row in events)


def test_missing_source_keeps_run_document_snapshot(tmp_path):
    database = tmp_path / "missing-source.sqlite3"
    config = _config(database)
    command.upgrade(config, "0010_workflow_document_commands")
    snapshot = {"nodes": [{"id": "original"}], "name": "frozen"}
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO workflow_runs VALUES (?,?,?,?,?,?)",
            (
                "orphan",
                "missing",
                "digest",
                "2026-09-13",
                None,
                json.dumps(
                    {
                        "state": "failed",
                        "document": snapshot,
                        "error": {"code": "ORIGINAL_FAILURE"},
                    }
                ),
            ),
        )
    command.upgrade(config, "head")
    with sqlite3.connect(database) as connection:
        document, provenance = connection.execute(
            "SELECT document, provenance FROM project_workflow_prepared_contents"
        ).fetchone()
        assert json.loads(document) == snapshot
        assert json.loads(provenance)["documentSource"] == "runSnapshot"
        assert json.loads(
            connection.execute("SELECT error FROM project_workflow_runs").fetchone()[0]
        ) == {"code": "ORIGINAL_FAILURE"}
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_downgrade_refuses_persisted_evidence_before_schema_changes(tmp_path):
    database = tmp_path / "downgrade-evidence.sqlite3"
    config = _config(database)
    command.upgrade(config, "0008_workflow_debug")
    with sqlite3.connect(database) as connection:
        _seed_legacy_runtime(connection)
    command.upgrade(config, "head")
    with sqlite3.connect(database) as connection:
        before = list(connection.iterdump())
    with pytest.raises(RuntimeError, match="WORKFLOW_RUNTIME_DOWNGRADE_UNSAFE"):
        command.downgrade(config, "0010_workflow_document_commands")
    with sqlite3.connect(database) as connection:
        assert list(connection.iterdump()) == before


def test_empty_runtime_can_downgrade_and_upgrade_again(tmp_path):
    database = tmp_path / "empty-roundtrip.sqlite3"
    config = _config(database)
    command.upgrade(config, "head")
    command.downgrade(config, "0010_workflow_document_commands")
    command.upgrade(config, "head")
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == (EXPECTED_HEAD,)


def test_0006_embedded_artifact_survives_full_upgrade(tmp_path):
    database = tmp_path / "embedded-artifact.sqlite3"
    config = _config(database)
    command.upgrade(config, "0006_workflow_runs")
    artifact = {
        "id": "result",
        "nodeId": "read",
        "executionId": "visit",
        "relativePath": "artifacts/result.json",
        "value": "原始证据",
    }
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO workflow_documents VALUES (?,?,?,?,?,?,?)",
            ("workflow", "旧文档", "{}", "{}", 1, "2026-09-13", "2026-09-13"),
        )
        connection.execute(
            "INSERT INTO workflow_runs VALUES (?,?,?,?,?,?)",
            (
                "run",
                "workflow",
                "digest",
                "2026-09-13",
                None,
                json.dumps({"state": "succeeded", "artifacts": [artifact]}),
            ),
        )
    command.upgrade(config, "head")
    with sqlite3.connect(database) as connection:
        assert (
            json.loads(
                connection.execute(
                    "SELECT payload FROM workflow_run_artifacts"
                ).fetchone()[0]
            )
            == artifact
        )
        assert (
            json.loads(
                connection.execute(
                    "SELECT provenance FROM project_workflow_prepared_contents"
                ).fetchone()[0]
            )["legacyPayload"]["artifactCount"]
            == 1
        )


def test_previous_interrupted_terminal_keeps_error_and_finished_at(tmp_path):
    database = tmp_path / "previous-interrupted.sqlite3"
    config = _config(database)
    command.upgrade(config, "0008_workflow_debug")
    original_error = {"code": "WORKFLOW_RUN_INTERRUPTED", "message": "已中断"}
    with sqlite3.connect(database) as connection:
        _seed_legacy_runtime(connection)
        payload = json.loads(
            connection.execute(
                "SELECT payload FROM workflow_runs WHERE id='run-active'"
            ).fetchone()[0]
        )
        payload.update(
            state="interrupted",
            finishedAt="2026-09-13T10:05:00+00:00",
            error=original_error,
        )
        connection.execute(
            "UPDATE workflow_runs SET payload=?, active_slot=NULL WHERE id='run-active'",
            (json.dumps(payload),),
        )
    command.upgrade(config, "head")
    with sqlite3.connect(database) as connection:
        status, error, finished_at = connection.execute(
            "SELECT status, error, completed_at FROM project_workflow_runs WHERE id='run-active'"
        ).fetchone()
        assert status == "interrupted"
        assert json.loads(error) == original_error
        assert finished_at == "2026-09-13T10:05:00+00:00"


def test_failed_upgrade_rolls_back_schema_and_original_evidence(tmp_path):
    database = tmp_path / "failed-upgrade.sqlite3"
    config = _config(database)
    command.upgrade(config, "0010_workflow_document_commands")
    with sqlite3.connect(database) as connection:
        _seed_legacy_runtime(connection)
        payload = json.loads(
            connection.execute(
                "SELECT payload FROM workflow_runs WHERE id='run-active'"
            ).fetchone()[0]
        )
        payload["latestSeq"] = "invalid-persisted-sequence"
        connection.execute(
            "UPDATE workflow_runs SET payload=? WHERE id='run-active'",
            (json.dumps(payload),),
        )
    with sqlite3.connect(database) as connection:
        before = list(connection.iterdump())
    with pytest.raises(ValueError, match="invalid literal"):
        command.upgrade(config, "head")
    with sqlite3.connect(database) as connection:
        assert list(connection.iterdump()) == before
