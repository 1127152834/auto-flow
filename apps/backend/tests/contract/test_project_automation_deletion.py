"""PM8-A2: automation delete/unlink impact, guards and history ownership."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.project_automations import project_automations_router
from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.project_run_models import ProjectBatchRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowPreparedContentRow,
)

PROJECT = "00000000-0000-0000-0000-000000000010"
WORKFLOW = "00000000-0000-0000-0000-000000000020"
TABLE = "00000000-0000-0000-0000-000000000040"


def automation_body():
    return {
        "name": "注册",
        "description": "说明",
        "workflowId": WORKFLOW,
        "inputPlan": {
            "inputs": [
                {
                    "inputId": "00000000-0000-0000-0000-000000000041",
                    "alias": "资料",
                    "tableId": TABLE,
                    "datasetGeneration": "00000000-0000-0000-0000-000000000042",
                    "mode": "independent",
                    "required": True,
                    "fieldBindings": [
                        {
                            "inputFieldId": "00000000-0000-0000-0000-000000000046",
                            "inputFieldAlias": "标题",
                            "fieldRef": {
                                "projectId": PROJECT,
                                "tableId": TABLE,
                                "datasetGeneration": "00000000-0000-0000-0000-000000000042",
                                "fieldId": "00000000-0000-0000-0000-000000000043",
                            },
                        }
                    ],
                    "filter": {
                        "type": "compare",
                        "fieldId": "00000000-0000-0000-0000-000000000043",
                        "operator": "contains",
                        "value": "温室",
                    },
                    "orderBy": [],
                }
            ]
        },
        "parameterSchema": [
            {
                "parameterId": "00000000-0000-0000-0000-000000000044",
                "name": "开关",
                "type": "boolean",
                "required": False,
            },
            {
                "parameterId": "00000000-0000-0000-0000-000000000045",
                "name": "文本",
                "type": "string",
                "required": True,
            },
        ],
        "environmentPolicy": {"source": "newFromProfile"},
        "runPolicy": {
            "maxTasks": 1,
            "concurrency": 1,
            "maxLiveInstances": 1,
            "continueAfterFailure": False,
            "automaticExecutionTimeoutSeconds": 60,
            "manualDeadlineSeconds": 300,
        },
    }


def client(tmp_path):
    database = tmp_path / "automation-deletion.sqlite3"
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
        session.add(
            WorkflowDocumentRow(
                id=WORKFLOW,
                name="W",
                document={},
                layout={},
                revision=1,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    app = FastAPI()
    app.state.automation_factory = factory
    install_error_handlers(app)
    app.include_router(
        project_automations_router(
            ProjectAutomationService(
                SqlAlchemyProjects(factory), SqlAlchemyProjectAutomations(factory)
            )
        )
    )
    return TestClient(app), factory


def create_automation(api):
    response = api.post(
        f"/api/v1/projects/{PROJECT}/automations",
        headers={"Idempotency-Key": str(uuid4())},
        json=automation_body(),
    )
    assert response.status_code == 201, response.text
    return response.json()["automationId"]


def seed_batch(factory, automation_id, status="running"):
    now = datetime.now(UTC)
    batch_id, prepared_id, operation_id = str(uuid4()), str(uuid4()), str(uuid4())
    with factory() as session:
        session.add(
            ProjectOperationRow(
                id=operation_id,
                project_id=PROJECT,
                idempotency_key=str(uuid4()),
                kind="startBatch",
                request_digest="0" * 64,
                status="succeeded",
                status_revision=2,
                resource={},
                result={},
                error=None,
                created_at=now,
                updated_at=now,
                completed_at=now,
            )
        )
        session.flush()
        session.add(
            WorkflowPreparedContentRow(
                id=prepared_id,
                prepare_operation_id=str(uuid4()),
                request_digest="0" * 64,
                workflow_id=WORKFLOW,
                source_revision=1,
                checksum="0" * 64,
                document={},
                execution_plan={},
                adapter_version="test",
                capability_requirements=[],
                provenance={},
                created_at=now,
            )
        )
        session.flush()
        session.add(
            ProjectBatchRow(
                id=batch_id,
                project_id=PROJECT,
                automation_id=automation_id,
                start_operation_id=operation_id,
                prepared_content_id=prepared_id,
                automation_revision=1,
                workflow_revision=1,
                status=status,
                status_revision=1,
                frozen_request={},
                created_at=now,
                completed_at=None,
            )
        )
        session.commit()
    return batch_id


def count(factory, model, **where):
    with factory() as session:
        statement = select(func.count()).select_from(model)
        for column, value in where.items():
            statement = statement.where(getattr(model, column) == value)
        return session.scalar(statement)


def impact(api, automation_id, action="delete"):
    response = api.get(
        f"/api/v1/projects/{PROJECT}/automations/{automation_id}/impact",
        params={"action": action},
    )
    assert response.status_code == 200, response.text
    return response.json()


def delete(api, automation_id, key, body):
    return api.request(
        "DELETE",
        f"/api/v1/projects/{PROJECT}/automations/{automation_id}",
        headers={"Idempotency-Key": key},
        json=body,
    )


def test_impact_reports_real_references_and_does_not_mutate(tmp_path):
    api, factory = client(tmp_path)
    automation_id = create_automation(api)
    before = count(factory, ProjectAutomationRow)
    item = impact(api, automation_id)
    assert item["impactRevision"] >= 1
    assert item["blockers"] == []
    by_code = {entry["code"]: entry for entry in item["impacts"]}
    assert {
        "AUTOMATION_CONFIGURATION",
        "DATA_TABLE_USE",
        "AUTOMATION_PARAMETERS",
        "AUTOMATION_FILTERS",
        "RUN_PLANS",
    } <= set(by_code)
    assert by_code["DATA_TABLE_USE"]["message"].find("1") >= 0
    assert by_code["AUTOMATION_PARAMETERS"]["message"].find("2") >= 0
    assert by_code["AUTOMATION_FILTERS"]["message"].find("1") >= 0
    assert by_code["RUN_PLANS"]["message"].find("0") >= 0
    assert count(factory, ProjectAutomationRow) == before


def test_impact_is_blocked_by_a_live_batch_and_not_by_finished_history(tmp_path):
    api, factory = client(tmp_path)
    automation_id = create_automation(api)
    seed_batch(factory, automation_id, status="running")
    live = impact(api, automation_id)
    assert [entry["state"] for entry in live["blockers"]] == ["running"]
    assert live["blockers"][0]["resource"]["type"] == "batch"
    with factory() as session:
        row = session.scalar(select(ProjectBatchRow))
        row.status = "completed"
        session.commit()
    settled = impact(api, automation_id)
    assert settled["blockers"] == []
    assert settled["impactRevision"] != live["impactRevision"]


def test_impact_rejects_unknown_action_and_foreign_scope(tmp_path):
    api, _ = client(tmp_path)
    automation_id = create_automation(api)
    assert (
        api.get(
            f"/api/v1/projects/{PROJECT}/automations/{automation_id}/impact",
            params={"action": "purge"},
        ).status_code
        == 422
    )
    other = "00000000-0000-0000-0000-000000000099"
    assert (
        api.get(
            f"/api/v1/projects/{other}/automations/{automation_id}/impact",
            params={"action": "delete"},
        ).status_code
        == 404
    )


def test_delete_unlinks_workflow_and_removes_only_owned_run_history(tmp_path):
    api, factory = client(tmp_path)
    automation_id = create_automation(api)
    batch_id = seed_batch(factory, automation_id, status="completed")
    with factory() as session:
        prepared = session.scalars(select(WorkflowPreparedContentRow)).one()
        independent_id = str(uuid4())
        values = {
            column.name: getattr(prepared, column.name)
            for column in WorkflowPreparedContentRow.__table__.columns
        }
        values.update(id=independent_id, prepare_operation_id=str(uuid4()))
        session.add(WorkflowPreparedContentRow(**values))
        session.commit()
    current_impact = impact(api, automation_id)
    prepared_impact = next(
        item
        for item in current_impact["impacts"]
        if item["code"] == "PREPARED_CONTENTS"
    )
    assert prepared_impact["message"] == "配置升级恢复副本 1 个"
    revision = current_impact["impactRevision"]
    response = delete(
        api,
        automation_id,
        str(uuid4()),
        {
            "impactRevision": revision,
            "expectedManagementRevision": 1,
            "workflowDisposition": "unlink",
        },
    )
    assert response.status_code in {200, 202}, response.text
    operation = response.json()["operation"]
    assert operation["kind"] == "deleteAutomation"
    assert operation["status"] == "succeeded"
    assert count(factory, ProjectAutomationRow, id=automation_id) == 0
    # The workflow document and the project's other resources stay; only the
    # automation and the run facts it owns are removed.
    assert count(factory, WorkflowDocumentRow, id=WORKFLOW) == 1
    assert count(factory, ProjectBatchRow, id=batch_id) == 0
    assert count(factory, WorkflowPreparedContentRow) == 1
    assert count(factory, WorkflowPreparedContentRow, id=independent_id) == 1
    assert (
        api.get(f"/api/v1/projects/{PROJECT}/automations/{automation_id}").status_code
        == 404
    )


def test_delete_requires_live_impact_and_current_revision(tmp_path):
    api, factory = client(tmp_path)
    automation_id = create_automation(api)
    stale = impact(api, automation_id)["impactRevision"]
    # A committed change to the same automation invalidates the confirmation.
    updated = api.put(
        f"/api/v1/projects/{PROJECT}/automations/{automation_id}",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            **automation_body(),
            "description": "新版",
            "expectedManagementRevision": 1,
        },
    )
    assert updated.status_code == 200, updated.text
    body = {
        "impactRevision": stale,
        "expectedManagementRevision": 2,
        "workflowDisposition": "unlink",
    }
    assert delete(api, automation_id, str(uuid4()), body).status_code == 412
    fresh = impact(api, automation_id)["impactRevision"]
    mismatched = {
        "impactRevision": fresh,
        "expectedManagementRevision": 1,
        "workflowDisposition": "unlink",
    }
    assert delete(api, automation_id, str(uuid4()), mismatched).status_code == 409
    assert count(factory, ProjectAutomationRow, id=automation_id) == 1


def test_delete_refuses_owned_document_removal_and_live_batches(tmp_path):
    api, factory = client(tmp_path)
    automation_id = create_automation(api)
    revision = impact(api, automation_id)["impactRevision"]
    owned = delete(
        api,
        automation_id,
        str(uuid4()),
        {
            "impactRevision": revision,
            "expectedManagementRevision": 1,
            "workflowDisposition": "deleteOwned",
        },
    )
    assert owned.status_code == 409, owned.text
    assert (
        owned.json()["error"]["details"]["domainCode"] == "workflow_ownership_unknown"
    )
    seed_batch(factory, automation_id, status="running")
    live_revision = impact(api, automation_id)["impactRevision"]
    blocked = delete(
        api,
        automation_id,
        str(uuid4()),
        {
            "impactRevision": live_revision,
            "expectedManagementRevision": 1,
            "workflowDisposition": "unlink",
        },
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["details"]["domainCode"] == "automation_busy"
    assert count(factory, ProjectAutomationRow, id=automation_id) == 1
    assert count(factory, WorkflowDocumentRow, id=WORKFLOW) == 1


def test_delete_replays_the_same_key_without_a_second_fact(tmp_path):
    api, factory = client(tmp_path)
    automation_id = create_automation(api)
    revision = impact(api, automation_id)["impactRevision"]
    key = "00000000-0000-0000-0000-0000000000aa"
    body = {
        "impactRevision": revision,
        "expectedManagementRevision": 1,
        "workflowDisposition": "unlink",
    }
    first = delete(api, automation_id, key, body)
    second = delete(api, automation_id, key, body)
    assert first.status_code in {200, 202} and second.status_code == 200, second.text
    assert (
        first.json()["operation"]["operationId"]
        == second.json()["operation"]["operationId"]
    )
    assert count(factory, ProjectOperationRow, kind="deleteAutomation") == 1
