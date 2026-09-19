"""PM8-A2: environment delete impact, guards and residue-free removal."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.project_environments import project_environments_router
from autoflow.application.environments.service import EnvironmentService
from autoflow.infrastructure.database.environment_models import (
    ProjectEnvironmentInstanceRow,
    ProjectEnvironmentRow,
)
from autoflow.infrastructure.database.environments import SqlAlchemyEnvironments
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_data_models import (
    DataGenerationRow,
    DataRecordRow,
    DataTableRow,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)

PROJECT = "00000000-0000-0000-0000-000000000010"
ENVIRONMENT = "00000000-0000-0000-0000-000000000020"
INSTANCE = "00000000-0000-0000-0000-000000000030"
TABLE = "00000000-0000-0000-0000-000000000040"
GENERATION = "00000000-0000-0000-0000-000000000041"


def client(tmp_path, instance_state="active"):
    database = tmp_path / "environment-deletion.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    now = datetime.now(UTC)
    with factory() as session:
        session.add(
            ProjectRow(
                id=PROJECT,
                name="P",
                name_key="p",
                description="",
                search_text="p",
                default_resources={},
                management_revision=1,
                lifecycle_state="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()
        session.add(
            ProjectEnvironmentRow(
                id=ENVIRONMENT,
                project_id=PROJECT,
                name="登录环境",
                name_key="登录环境",
                notes="",
                state="ready",
                profile_id="00000000-0000-0000-0000-000000000050",
                content_generation=1,
                metadata_revision=1,
                current_digest="0" * 64,
                created_from_source="manual",
                created_from_task_id=None,
                unavailable_reason=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()
        session.add(
            ProjectEnvironmentInstanceRow(
                id=INSTANCE,
                project_id=PROJECT,
                environment_id=ENVIRONMENT,
                state=instance_state,
                source="persistent",
                source_content_generation=1,
                instance_use_generation=1,
                active_task_id=None,
                active_run_id=None,
                maintenance_operation_id=None,
                profile_id="00000000-0000-0000-0000-000000000050",
                identity_package={},
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(
        project_environments_router(
            EnvironmentService(
                SqlAlchemyProjects(factory), SqlAlchemyEnvironments(factory), store=None
            )
        )
    )
    return TestClient(app), factory


def count(factory, model, **where):
    with factory() as session:
        statement = select(func.count()).select_from(model)
        for column, value in where.items():
            statement = statement.where(getattr(model, column) == value)
        return session.scalar(statement)


def impact(api, action="delete"):
    response = api.get(
        f"/api/v1/projects/{PROJECT}/environments/{ENVIRONMENT}/impact",
        params={"action": action},
    )
    assert response.status_code == 200, response.text
    return response.json()


def delete(api, key, body):
    return api.request(
        "DELETE",
        f"/api/v1/projects/{PROJECT}/environments/{ENVIRONMENT}",
        headers={"Idempotency-Key": key},
        json=body,
    )


def test_impact_reports_real_references_and_blocks_live_instances(tmp_path):
    api, factory = client(tmp_path, instance_state="active")
    live = impact(api)
    assert [entry["code"] for entry in live["blockers"]] == ["ENVIRONMENT_BUSY"]
    assert live["blockers"][0]["state"] == "active"
    assert live["blockers"][0]["resource"]["type"] == "environment"
    with factory() as session:
        instance = session.get(ProjectEnvironmentInstanceRow, INSTANCE)
        instance.state = "closed"
        session.commit()
    settled = impact(api)
    assert settled["blockers"] == []
    codes = {entry["code"] for entry in settled["impacts"]}
    assert {"ENVIRONMENT_RECORDS", "AUTOMATION_FIXED_CHOICE"} <= codes
    assert settled["impactRevision"] != live["impactRevision"]
    assert count(factory, ProjectEnvironmentRow, id=ENVIRONMENT) == 1


def test_impact_rejects_unknown_action_and_foreign_scope(tmp_path):
    api, _ = client(tmp_path, instance_state="closed")
    assert (
        api.get(
            f"/api/v1/projects/{PROJECT}/environments/{ENVIRONMENT}/impact",
            params={"action": "archive"},
        ).status_code
        == 422
    )
    other = "00000000-0000-0000-0000-000000000099"
    assert (
        api.get(
            f"/api/v1/projects/{other}/environments/{ENVIRONMENT}/impact",
            params={"action": "delete"},
        ).status_code
        == 404
    )


def test_delete_requires_current_revisions_and_a_live_confirmation(tmp_path):
    api, factory = client(tmp_path, instance_state="closed")
    revision = impact(api)["impactRevision"]
    with factory() as session:
        row = session.get(ProjectEnvironmentRow, ENVIRONMENT)
        row.metadata_revision = 2
        session.commit()
    stale_revision = delete(
        api,
        str(uuid4()),
        {
            "impactRevision": revision,
            "expectedMetadataRevision": 1,
            "expectedContentGeneration": 1,
        },
    )
    assert stale_revision.status_code == 409, stale_revision.text
    assert (
        stale_revision.json()["error"]["details"]["domainCode"]
        == "environment_metadata_conflict"
    )
    fresh = impact(api)["impactRevision"]
    confirmed = delete(
        api,
        str(uuid4()),
        {
            "impactRevision": fresh,
            "expectedMetadataRevision": 2,
            "expectedContentGeneration": 2,
        },
    )
    assert confirmed.status_code == 409, confirmed.text
    assert (
        confirmed.json()["error"]["details"]["domainCode"]
        == "environment_content_conflict"
    )
    assert count(factory, ProjectEnvironmentRow, id=ENVIRONMENT) == 1


def test_delete_refuses_live_instances_and_stale_confirmations(tmp_path):
    api, factory = client(tmp_path, instance_state="active")
    revision = impact(api)["impactRevision"]
    blocked = delete(
        api,
        str(uuid4()),
        {
            "impactRevision": revision,
            "expectedMetadataRevision": 1,
            "expectedContentGeneration": 1,
        },
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["details"]["domainCode"] == "environment_busy"
    with factory() as session:
        instance = session.get(ProjectEnvironmentInstanceRow, INSTANCE)
        instance.state = "closed"
        session.commit()
    stale = delete(
        api,
        str(uuid4()),
        {
            "impactRevision": revision,
            "expectedMetadataRevision": 1,
            "expectedContentGeneration": 1,
        },
    )
    assert stale.status_code == 412, stale.text
    assert count(factory, ProjectEnvironmentRow, id=ENVIRONMENT) == 1


def test_delete_removes_the_environment_and_keeps_history(tmp_path):
    api, factory = client(tmp_path, instance_state="closed")
    now = datetime.now(UTC)
    with factory() as session:
        session.add(
            DataTableRow(
                id=TABLE,
                project_id=PROJECT,
                name="账号",
                name_key="账号",
                search_text="账号",
                description="",
                source_kind="local",
                current_generation=GENERATION,
                identity={},
                slot_definitions=[],
                table_revision=1,
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()
        session.add(
            DataGenerationRow(
                id=GENERATION,
                project_id=PROJECT,
                table_id=TABLE,
                identity={},
                source={},
                created_at=now,
            )
        )
        session.flush()
        session.add(
            DataRecordRow(
                project_id=PROJECT,
                table_id=TABLE,
                dataset_generation=GENERATION,
                key_type="text",
                key_value="001",
                values_json={},
                record_slots=[],
                content_revision=1,
                status_revision=1,
                link_revision=1,
                deleted=False,
                current_environment_id=ENVIRONMENT,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    revision = impact(api)["impactRevision"]
    response = delete(
        api,
        str(uuid4()),
        {
            "impactRevision": revision,
            "expectedMetadataRevision": 1,
            "expectedContentGeneration": 1,
        },
    )
    assert response.status_code == 202, response.text
    operation = response.json()["operation"]
    assert operation["kind"] == "deleteEnvironment"
    assert operation["status"] == "succeeded"
    assert count(factory, ProjectEnvironmentRow, id=ENVIRONMENT) == 0
    # History survives: the closed instance stays, only its link is detached.
    assert count(factory, ProjectEnvironmentInstanceRow, id=INSTANCE) == 1
    with factory() as session:
        instance = session.get(ProjectEnvironmentInstanceRow, INSTANCE)
        assert instance.environment_id is None
        record = session.scalar(select(DataRecordRow))
        assert record.current_environment_id is None
        assert record.link_revision == 2
        assert record.key_value == "001"


def test_delete_replays_the_same_key_without_a_second_fact(tmp_path):
    api, factory = client(tmp_path, instance_state="closed")
    revision = impact(api)["impactRevision"]
    key = "00000000-0000-0000-0000-0000000000bb"
    body = {
        "impactRevision": revision,
        "expectedMetadataRevision": 1,
        "expectedContentGeneration": 1,
    }
    first = delete(api, key, body)
    second = delete(api, key, body)
    assert first.status_code == 202 and second.status_code == 202, second.text
    assert (
        first.json()["operation"]["operationId"]
        == second.json()["operation"]["operationId"]
    )
    assert count(factory, ProjectOperationRow, kind="deleteEnvironment") == 1
