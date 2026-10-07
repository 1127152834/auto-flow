"""Remediation M5 5B-A4: batch progress (B7) and draft input matching (B4) through HTTP and SQLite."""

import copy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.project_run_progress import project_run_progress_router
from autoflow.application.project_runs.input_match import InputMatchService
from autoflow.application.project_runs.progress import BatchProgressService
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.infrastructure.database.project_data_models import DataTableRow
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.record_ledger_models import (
    AutomationRecordLedgerRow,
    ProjectBatchUnitRow,
)
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.integration.test_project_run_data_start import _setup, uid

NOW = datetime.now(UTC)


@pytest.fixture
def env(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    batch, _operation, _replayed = coordinator.start(
        project_id, automation.automation_id, uid(),
        {"expectedAutomationRevision": automation.management_revision, "parameters": {}, "maxTasks": 10, "concurrency": 1},
    )
    assert ProjectBatchScheduler.claim_data_task(factory, project_id, batch.batch_id) == "ready"
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(project_run_progress_router(BatchProgressService(factory), InputMatchService(factory)))
    yield TestClient(app), factory, project_id, automation, batch.batch_id
    factory.dispose()


def _add_unit(factory, project_id, automation, batch_id, state, outcome=None, error=None):
    plan = automation.input_plan
    first = plan["inputs"][0]
    with factory.begin() as session:
        task_id = session.scalar(select(ProjectTaskRow.id).where(ProjectTaskRow.batch_id == batch_id))
        ledger_id = str(uuid4())
        session.add(AutomationRecordLedgerRow(
            id=ledger_id, automation_id=automation.automation_id, processing_input_id=plan["processingInputId"],
            project_id=project_id, table_id=first["tableId"], dataset_generation=first["datasetGeneration"],
            key_type="text", key_value=str(uuid4()), identity_namespace="", state=state, attempts=1,
            processing_cycle=1, cycle_attempts=1, last_outcome=outcome, last_error=error, revision=1,
            created_at=NOW, updated_at=NOW,
        ))
        session.flush()
        session.add(ProjectBatchUnitRow(id=str(uuid4()), batch_id=batch_id, ledger_id=ledger_id, first_task_id=task_id, created_at=NOW))


def test_progress_counts_groups_and_masks_failures(env):
    client, factory, project_id, automation, batch_id = env
    add = lambda *args: _add_unit(factory, project_id, automation, batch_id, *args)
    for _ in range(2):
        add("succeeded")
    for index in range(5):
        add("failed_retryable", "page", {"code": "WORKFLOW_NODE_FAILED", "message": f"点击失败 password=hunter2 联系 a{index}@b.com"})
    add("quarantined", "business", {"code": "END_BUSINESS_FAILED", "message": "余额不足"})
    add("needs_review", "unknown", None)
    add("skipped")
    response = client.get(f"/api/v1/projects/{project_id}/batches/{batch_id}/progress")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ledger"] == {
        "total": 11, "pending": 0, "running": 1, "succeeded": 2, "failedRetryable": 5,
        "quarantined": 1, "needsReview": 1, "skipped": 1,
    }
    groups = {group["errorCode"]: group for group in body["failureGroups"]}
    assert body["failureGroups"][0]["errorCode"] == "page_error"
    assert groups["page_error"]["count"] == 5 and len(groups["page_error"]["sampleUnitIds"]) == 3
    assert groups["business_failed"]["count"] == 1 and groups["business_failed"]["sampleMessage"] == "余额不足"
    assert groups["outcome_unknown"]["count"] == 1 and groups["outcome_unknown"]["sampleMessage"] is None
    for leaked in ("hunter2", "@b.com"):
        assert leaked not in response.text
    assert body["throughput"]["windowMinutes"] == 5 and body["throughput"]["etaSeconds"] is None


def test_running_task_shows_row_display_name_and_elapsed_time(env):
    client, factory, project_id, automation, batch_id = env
    first = automation.input_plan["inputs"][0]
    field_id = first["fieldBindings"][0]["fieldRef"]["fieldId"]
    with factory.begin() as session:
        table = session.get(DataTableRow, first["tableId"])
        table.identity = {**table.identity, "mode": "field", "fieldId": field_id}
        run = session.scalar(select(WorkflowRunRow))
        run.status, run.started_at = "running", datetime.now(UTC) - timedelta(seconds=90)
    body = client.get(f"/api/v1/projects/{project_id}/batches/{batch_id}/progress").json()
    (task,) = body["runningTasks"]
    assert task["displayName"] == "张三"
    assert task["identityName"] is None
    assert 85 <= task["elapsedSeconds"] <= 200


def test_throughput_and_eta_follow_finished_tasks(env):
    client, factory, project_id, _automation, batch_id = env
    with factory.begin() as session:
        batch = session.get(ProjectBatchRow, batch_id)
        batch.created_at = datetime.now(UTC) - timedelta(minutes=2)
        run = session.scalar(select(WorkflowRunRow))
        run.status, run.completed_at = "succeeded", datetime.now(UTC) - timedelta(seconds=30)
    body = client.get(f"/api/v1/projects/{project_id}/batches/{batch_id}/progress").json()
    assert body["runningTasks"] == [] and body["ledger"]["running"] == 0 and body["ledger"]["pending"] == 1
    assert body["throughput"]["recentPerMinute"] == pytest.approx(0.5, abs=0.05)
    # maxTasks 10 with one finished: 9 left at about half a task a minute.
    assert 1000 <= body["throughput"]["etaSeconds"] <= 1200


def test_other_projects_and_unknown_batches_are_not_found(env):
    client, _factory, project_id, _automation, batch_id = env
    assert client.get(f"/api/v1/projects/{uuid4()}/batches/{batch_id}/progress").status_code == 404
    assert client.get(f"/api/v1/projects/{project_id}/batches/{uuid4()}/progress").status_code == 404


def test_input_match_counts_unprocessed_and_hides_sensitive_values(env):
    client, factory, project_id, automation, _batch_id = env
    plan = copy.deepcopy(automation.input_plan)
    first = plan["inputs"][0]
    url = f"/api/v1/projects/{project_id}/automations/{automation.automation_id}/input-match"
    response = client.post(url, json={"inputPlan": plan})
    assert response.status_code == 200, response.text
    people, emails = response.json()["inputs"]
    assert people["outcome"] == "counted" and people["matchedCount"] == 1
    assert people["sample"] == [{"值": "张三"}]
    # The only matching row is held by the claimed task, so nothing is left to process.
    assert people["unprocessedCount"] == 0
    assert emails["unprocessedCount"] is None and emails["sample"] == [{"值": "pm4@example.test"}]

    first["signatureInput"] = "account"
    first["fieldBindings"][0]["signatureField"] = "name"
    with factory.begin() as session:
        row = session.get(WorkflowDocumentRow, automation.workflow_id)
        document = copy.deepcopy(row.document)
        document["content"]["signature"] = {
            "inputs": [{"key": "account", "name": "账号", "fields": [
                {"key": "name", "name": "姓名", "type": "string", "required": True, "sensitive": True}
            ]}],
            "outputs": [],
        }
        row.document = document
    masked = client.post(url, json={"inputPlan": plan}).json()["inputs"][0]
    assert masked["sample"] == [{"值": "已隐藏"}] and masked["matchedCount"] == 1
    assert "张三" not in str(masked)

    field_id = first["fieldBindings"][0]["fieldRef"]["fieldId"]
    first["filter"] = {"type": "compare", "fieldId": field_id, "operator": "eq", "value": "无此人"}
    none = client.post(url, json={"inputPlan": plan}).json()["inputs"][0]
    assert none["matchedCount"] == 0 and none["sample"] == []


def test_input_match_rejects_foreign_automation_and_invalid_plan(env):
    client, _factory, project_id, automation, _batch_id = env
    plan = automation.input_plan
    base = f"/api/v1/projects/{project_id}/automations"
    assert client.post(f"/api/v1/projects/{uuid4()}/automations/{automation.automation_id}/input-match", json={"inputPlan": plan}).status_code == 404
    assert client.post(f"{base}/{uuid4()}/input-match", json={"inputPlan": plan}).status_code == 404
    bad = copy.deepcopy(plan)
    bad["processingInputId"] = str(uuid4())
    assert client.post(f"{base}/{automation.automation_id}/input-match", json={"inputPlan": bad}).status_code == 422
