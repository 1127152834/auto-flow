"""Excel generation replacement must respect real scheduler record leases."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.application.project_runs.coordinator import ProjectRunCoordinator
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.application.workflows.service import WorkflowService
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.project_run_models import ProjectRecordLeaseRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.contract.test_pm2_excel_imports import import_first, request_for
from tests.contract.test_settings_dashboard import _app
from tests.fixtures.workflows import workflow_payload
from tests.integration.test_project_run_data_start import _input, uid


@pytest.fixture
def imported(tmp_path):
    app = _app(tmp_path)
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        project, proof, inspection, table = import_first(client, tmp_path)
        base = f"/api/v1/projects/{project}/tables/{table['tableId']}"
        field = client.get(base + "/fields").json()["items"][0]
        factory = app.state.session_factory
        workflows = SqlAlchemyWorkflowRepository(factory)
        workflow = WorkflowService(workflows).create(workflow_payload(), uid())
        automation = ProjectAutomationService(
            SqlAlchemyProjects(factory), SqlAlchemyProjectAutomations(factory)
        ).create(
            project,
            uid(),
            {
                "name": "Excel lease owner",
                "description": "",
                "workflowId": workflow.workflow_id,
                "inputPlan": {"inputs": [_input(project, table, field, "Excel")]},
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
        )[0]
        coordinator = ProjectRunCoordinator(
            factory,
            WorkflowRuntimeService(factory, workflows),
            resolve_resources=lambda *_: {"browser": "none", "modelProviderId": None},
            available_capabilities=["browser.cloakbrowser", "project.data"],
        )
        batch, _, _ = coordinator.start(
            project,
            automation.automation_id,
            uid(),
            {
                "expectedAutomationRevision": automation.management_revision,
                "parameters": {},
                "maxTasks": 1,
                "concurrency": 1,
            },
        )
        request = {k: v for k, v in request_for(inspection).items() if k != "name"}
        request["mapping"] = [
            {
                "columnIndex": 0,
                "target": {"kind": "existing", "fieldId": field["ref"]["fieldId"]},
            }
        ]
        yield app, client, project, proof, table, base, request, batch.batch_id


def _claim(imported, state):
    app, _, project, _, _, _, _, batch = imported
    assert (
        ProjectBatchScheduler.claim_data_task(app.state.session_factory, project, batch)
        == "ready"
    )
    with app.state.session_factory() as session:
        lease = session.scalar(select(ProjectRecordLeaseRow))
        assert lease is not None and lease.state == "held"
        lease.state = state
        lease.updated_at = datetime.now(UTC)
        lease.released_at = lease.updated_at if state == "released" else None
        session.commit()


def _confirmed_request(imported):
    _, client, _, _, table, base, request, _ = imported
    impact = client.post(base + "/imports/excel/impact").json()
    return impact, {
        **request,
        "expectedDatasetGeneration": table["datasetGeneration"],
        "expectedTableRevision": table["tableRevision"],
        "impactRevision": impact["impactRevision"],
    }


def _assert_old_data_usable(imported):
    _, client, _, _, table, base, _, _ = imported
    assert client.get(base).json()["datasetGeneration"] == table["datasetGeneration"]
    records = client.get(
        base + "/records", params={"datasetGeneration": table["datasetGeneration"]}
    )
    assert records.status_code == 200, records.text
    record = records.json()["items"][0]
    assert record["ref"]["recordKey"] == {"type": "text", "value": "001"}
    assert record["values"][0]["value"] == "001"


@pytest.mark.parametrize("state", ["held", "reconciling"])
def test_excel_replace_preview_reports_active_lease_and_rejects_submit(imported, state):
    _, client, _, proof, _, base, _, _ = imported
    _claim(imported, state)
    impact, request = _confirmed_request(imported)

    assert impact["blockers"]
    response = client.post(
        base + "/imports/excel",
        json=request,
        headers={**proof, "Idempotency-Key": uid()},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "REVISION_CONFLICT"
    _assert_old_data_usable(imported)


@pytest.mark.parametrize("state", ["held", "reconciling"])
def test_excel_replace_submit_rechecks_lease_claimed_after_preview(imported, state):
    _, client, _, proof, _, base, _, _ = imported
    impact, request = _confirmed_request(imported)
    assert impact["blockers"] == []
    _claim(imported, state)

    response = client.post(
        base + "/imports/excel",
        json=request,
        headers={**proof, "Idempotency-Key": uid()},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "REVISION_CONFLICT"
    _assert_old_data_usable(imported)


@pytest.mark.parametrize("state", ["held", "reconciling"])
def test_excel_replace_publish_rechecks_lease_claimed_during_staging(
    imported, state, monkeypatch
):
    app, client, project, proof, _, base, _, _ = imported
    impact, request = _confirmed_request(imported)
    assert impact["blockers"] == []
    original = app.state.excel_imports.repository.append

    def claim_after_staging(job, rows):
        original(job, rows)
        _claim(imported, state)

    monkeypatch.setattr(
        app.state.excel_imports.repository, "append", claim_after_staging
    )
    headers = {**proof, "Idempotency-Key": uid()}
    response = client.post(base + "/imports/excel", json=request, headers=headers)
    assert response.status_code == 202, response.text
    operation_path = (
        f"/api/v1/projects/{project}/operations/by-idempotency-key/"
        f"{headers['Idempotency-Key']}"
    )
    result = client.get(operation_path).json()
    assert result["status"] == "failed", result
    assert result["error"]["code"] == "REVISION_CONFLICT"
    _assert_old_data_usable(imported)
    assert app.state.excel_imports.pending_operations() == []

    replay = client.post(base + "/imports/excel", json=request, headers=headers)
    assert replay.json()["operation"] == result
    app.state.excel_imports.startup()
    assert client.get(operation_path).json() == result


def test_excel_replace_released_lease_allows_new_generation_and_idempotent_replay(
    imported,
):
    app, client, project, proof, table, base, _, _ = imported
    _claim(imported, "released")
    impact, request = _confirmed_request(imported)
    assert impact["blockers"] == []
    headers = {**proof, "Idempotency-Key": uid()}
    response = client.post(base + "/imports/excel", json=request, headers=headers)
    assert response.status_code == 202, response.text
    result = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/"
        f"{headers['Idempotency-Key']}"
    ).json()
    assert result["status"] == "succeeded", result
    generation = result["result"]["table"]["datasetGeneration"]
    assert generation != table["datasetGeneration"]
    record = client.get(
        base + "/records", params={"datasetGeneration": generation}
    ).json()["items"][0]
    assert record["statusId"] is None
    assert record["ref"]["recordKey"] == {"type": "text", "value": "001"}
    replay = client.post(base + "/imports/excel", json=request, headers=headers)
    assert replay.json()["operation"] == result
    assert app.state.excel_imports.pending_operations() == []
