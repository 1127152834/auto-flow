import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.application.projects.service import ProjectService
from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.application.workflows.service import WorkflowService
from autoflow.infrastructure.database import session as database_session
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.project_run_models import ProjectBatchRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import create_session_factory
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.fixtures.workflows import workflow_payload


def config_for(database: Path) -> Config:
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    return config


def test_empty_database_upgrades_to_the_single_project_run_head(tmp_path):
    database = tmp_path / "empty.sqlite3"
    config = config_for(database)

    assert ScriptDirectory.from_config(config).get_heads() == ["pm06_project_capability_reads"]
    database_session.migrate_database(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("pm06_project_capability_reads",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        } >= {
            "project_batches",
            "project_tasks",
            "project_task_input_snapshots",
        }


def test_pm03_upgrade_preserves_real_project_automation_and_workflow_rows(tmp_path):
    database = tmp_path / "existing.sqlite3"
    config = config_for(database)
    command.upgrade(config, "pm03_project_automations")
    document = workflow_payload("00000000-0000-0000-0000-000000000020")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO workflow_documents VALUES (?,?,?,?,?,?,?)",
            (
                document["id"],
                "既有流程",
                json.dumps(document),
                "{}",
                7,
                "2026-09-15",
                "2026-09-15",
            ),
        )
        connection.execute(
            "INSERT INTO projects (id,name,name_key,description,search_text,default_resources,management_revision,lifecycle_state,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                "00000000-0000-0000-0000-000000000010",
                "既有项目",
                "既有项目",
                "说明",
                "既有项目 说明",
                json.dumps(
                    {
                        "profileId": None,
                        "proxy": {"mode": "none"},
                        "modelProviderId": None,
                    }
                ),
                3,
                "active",
                "2026-09-15",
                "2026-09-15",
            ),
        )
        connection.execute(
            "INSERT INTO project_automations (id,project_id,workflow_id,name,name_key,search_text,description,management_revision,input_plan,parameter_schema,environment_policy,run_policy,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "00000000-0000-0000-0000-000000000030",
                "00000000-0000-0000-0000-000000000010",
                document["id"],
                "既有自动化",
                "既有自动化",
                "既有自动化",
                "",
                2,
                '{"inputs":[]}',
                "[]",
                '{"source":"newFromProfile"}',
                '{"maxTasks":1,"concurrency":1}',
                "2026-09-15",
                "2026-09-15",
            ),
        )
        before = {
            table: connection.execute(f"SELECT * FROM {table}").fetchall()
            for table in ("workflow_documents", "projects", "project_automations")
        }

    database_session.migrate_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("pm06_project_capability_reads",)
        for table, rows in before.items():
            assert connection.execute(f"SELECT * FROM {table}").fetchall() == rows
        assert connection.execute(
            "SELECT COUNT(*) FROM project_batches"
        ).fetchone() == (0,)


def test_project_run_foreign_keys_are_restrictive_and_complete(tmp_path):
    database = tmp_path / "foreign-keys.sqlite3"
    database_session.migrate_database(database)
    expected = {
        "project_batches": {
            ("projects", "project_id"),
            ("project_automations", "automation_id"),
            ("project_operations", "start_operation_id"),
            ("workflow_prepared_contents", "prepared_content_id"),
        },
        "project_tasks": {
            ("projects", "project_id"),
            ("project_batches", "batch_id"),
            ("workflow_runs", "run_id"),
        },
        "project_task_input_snapshots": {
            ("project_tasks", "task_id"),
            ("project_batches", "batch_id"),
        },
    }
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        for table, references in expected.items():
            rows = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
            assert {(row[2], row[3]) for row in rows} == references
            assert {row[6] for row in rows} == {"RESTRICT"}


def test_empty_project_run_tables_can_downgrade_and_upgrade(tmp_path):
    database = tmp_path / "roundtrip.sqlite3"
    config = config_for(database)
    command.upgrade(config, "head")

    command.downgrade(config, "pm03_project_automations")
    with create_session_factory(database)() as session:
        assert not {
            "project_batches",
            "project_tasks",
            "project_task_input_snapshots",
        } & set(inspect(session.bind).get_table_names())
    command.upgrade(config, "head")
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("pm06_project_capability_reads",)


def test_nonempty_project_run_evidence_refuses_downgrade_without_data_loss(tmp_path):
    database = tmp_path / "evidence.sqlite3"
    config = config_for(database)
    database_session.migrate_database(database)
    factory = create_session_factory(database)
    projects = ProjectService(SqlAlchemyProjects(factory))
    project, _, _ = projects.create(
        str(uuid4()), {"name": "证据项目", "description": ""}
    )
    workflow_repository = SqlAlchemyWorkflowRepository(factory)
    workflow = WorkflowService(workflow_repository).create(
        workflow_payload(), str(uuid4())
    )
    automations = ProjectAutomationService(
        SqlAlchemyProjects(factory), SqlAlchemyProjectAutomations(factory)
    )
    automation, _, _ = automations.create(
        project.project_id,
        str(uuid4()),
        {
            "name": "证据自动化",
            "description": "",
            "workflowId": workflow.workflow_id,
            "inputPlan": {"inputs": []},
            "parameterSchema": [],
            "environmentPolicy": {"source": "newFromProfile"},
            "runPolicy": {
                "maxTasks": 1,
                "concurrency": 1,
                "maxLiveInstances": 1,
                "continueAfterFailure": False,
                "automaticExecutionTimeoutSeconds": 60,
                "manualDeadlineSeconds": 300,
            },
        },
    )
    runtime = WorkflowRuntimeService(factory, workflow_repository)
    prepared = runtime.prepare_content(
        prepare_operation_id=str(uuid4()),
        workflow_id=workflow.workflow_id,
        source_revision=workflow.revision,
        available_capabilities=["browser.cloakbrowser"],
    )
    now = datetime.now(UTC)
    batch_id, operation_id = str(uuid4()), str(uuid4())
    with factory() as session:
        session.add(
            ProjectOperationRow(
                id=operation_id,
                project_id=project.project_id,
                idempotency_key=str(uuid4()),
                kind="startBatch",
                request_digest="a" * 64,
                status="succeeded",
                status_revision=2,
                resource={
                    "type": "batch",
                    "projectId": project.project_id,
                    "batchId": batch_id,
                },
                result={"batch": {"batchId": batch_id}},
                error=None,
                created_at=now,
                updated_at=now,
                completed_at=now,
            )
        )
        session.add(
            ProjectBatchRow(
                id=batch_id,
                project_id=project.project_id,
                automation_id=automation.automation_id,
                start_operation_id=operation_id,
                prepared_content_id=prepared.prepared_content_id,
                automation_revision=automation.management_revision,
                workflow_revision=workflow.revision,
                status="accepted",
                status_revision=1,
                frozen_request={
                    "maxTasks": 1,
                    "parameters": {},
                    "resourceRequest": {"browser": "none"},
                },
                created_at=now,
                completed_at=None,
            )
        )
        session.commit()
    with sqlite3.connect(database) as connection:
        before = connection.execute(
            "SELECT * FROM project_batches WHERE id=?", (batch_id,)
        ).fetchall()
    factory.dispose()

    with pytest.raises(RuntimeError, match="Project run evidence exists"):
        command.downgrade(config, "pm03_project_automations")

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("pm06_project_capability_reads",)
        assert (
            connection.execute(
                "SELECT * FROM project_batches WHERE id=?", (batch_id,)
            ).fetchall()
            == before
        )
