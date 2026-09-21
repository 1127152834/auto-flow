"""Real HTTP/SQLite/worker handoff; only Google transport and credentials are fixtures."""

import base64
import json
import shutil
import time
from itertools import pairwise

import pytest
from sqlalchemy import select

from autoflow.domain.profiles.models import ProfileSpec
from autoflow.infrastructure.database.project_run_models import (
    ProjectRecordLeaseRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.fixtures.sheets import new_key
from tests.fixtures.workflows import workflow_payload
from tests.integration.test_project_run_data_start import uid
from tests.integration.test_project_sheets_claims import plan_for, shared_tables
from tests.integration.test_workflow_real_cloakbrowser import (
    real_cloak_page as cloak_fixture,
)

real_cloak_page = cloak_fixture


def wait_for(check, label, timeout=90):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = check()
        if last:
            return last
        time.sleep(.1)
    raise AssertionError(f"Timeout waiting for {label}: {last}")


def start_real(bound, profile, url, label, status_id=None):
    def node(identity, kind, data):
        return {"id": identity, "type": kind, "position": {"x": 0, "y": 0}, "data": {"moduleType": kind, **data}}
    nodes = [
        node("inputs", "project_data", {"operation": "inputs", "variableName": "frozen", "arguments": {}}),
        node("open", "open_page", {"url": url, "timeout": 30}),
        node("manual", "project_manual", {"reason": "共享领取现场", "timeoutSeconds": 120}),
        node("write", "project_data", {"operation": "updateRecord", "variableName": "updated",
             "tableGrant": {"tableId": bound.table, "datasetGeneration": bound.dataset_generation(),
                            "operations": ["updateRecord"], "fieldIds": [bound.field_id("title")], "readPurposes": ["workflow"]},
             "arguments": {"recordRef": "{frozen[0]['recordRef']}",
                           "changes": {bound.field_id("title"): label}, "expectedContentRevision": "{frozen[0]['contentRevision']}"}}),
        node("end", "project_end", {"retainEnvironment": {"enabled": False}}),
    ]
    document = workflow_payload(uid())
    document["content"]["nodes"] = nodes
    document["content"]["edges"] = [{"id": uid(), "source": a["id"], "target": b["id"]} for a, b in pairwise(nodes)]
    saved = bound.client.post("/api/workflows", json={**document["content"], "id": document["id"], "clientRequestId": uid()})
    assert saved.status_code == 201, saved.text
    prefix = f"/api/v1/projects/{bound.project}"
    input_plan = plan_for(bound)
    input_plan["inputs"][0]["filter"] = {"type": "status", "operator": "eq", "statusId": status_id} if status_id else {"type": "status", "operator": "isNull"}
    response = bound.client.post(prefix + "/automations", headers=new_key(), json={
        "name": label, "description": "", "workflowId": saved.json()["id"], "inputPlan": input_plan, "parameterSchema": [],
        "environmentPolicy": {"source": "newFromProfile", "profileId": profile.id, "proxyOverride": {"mode": "none"}, "modelProviderId": None},
        "runPolicy": {"maxTasks": 1, "concurrency": 1, "maxLiveInstances": 1, "continueAfterFailure": False, "automaticExecutionTimeoutSeconds": 60, "manualDeadlineSeconds": 180},
    })
    assert response.status_code == 201, response.text
    automation = response.json()
    validation = bound.client.get(prefix + f"/automations/{automation['automationId']}/validation")
    assert validation.status_code == 200 and validation.json()["runnable"], validation.text
    accepted = bound.client.post(prefix + f"/automations/{automation['automationId']}/batches", headers=new_key(), json={
        "expectedAutomationRevision": automation["managementRevision"], "parameters": {}, "maxTasks": 1, "concurrency": 1,
    })
    assert accepted.status_code == 202, accepted.text
    return accepted.json()["operation"]["result"]["batch"]["batchId"]


def manual_item(bound):
    response = bound.client.get(f"/api/v1/projects/{bound.project}/manual-items")
    assert response.status_code == 200, response.text
    return next((item for item in response.json()["items"] if item["status"] == "waiting"), None)


def batch_detail(bound, batch):
    response = bound.client.get(f"/api/v1/projects/{bound.project}/batches/{batch}")
    assert response.status_code == 200, response.text
    return response.json()


def resume(bound, item):
    response = bound.client.post(f"/api/v1/projects/{bound.project}/manual-items/{item['manualItemId']}/resume", headers=new_key(), json={
        "checkpointRevision": item["checkpointRevision"], "expectedStatusRevision": item["statusRevision"],
    })
    assert response.status_code == 202, response.text


@pytest.mark.parametrize("handoff", ["resume", "stop", "loss"])
def test_real_shared_sheet_owner_handoff(tmp_path, valid_profile_values, real_cloak_page, handoff):
    executable, url, requests = real_cloak_page
    source = next(parent for parent in executable.parents if parent.name.startswith("chromium-"))
    shutil.copytree(source, tmp_path / "data" / "kernels" / source.name, symlinks=True)
    with shared_tables(tmp_path) as (first, second):
        app = first.client.app
        assert app.state.project_workflow_dispatcher.capacity == 2
        profile = app.state.profile_service.create(ProfileSpec.from_values({
            **valid_profile_values, "headless": True, "browser_version": source.name.removeprefix("chromium-"),
        }))
        status = first.client.post(first.url("/statuses"), headers=new_key(), json={
            "name": "P 已核验", "color": "#123456", "order": 1, "expectedTableRevision": first.table_revision(),
        })
        assert status.status_code == 201, status.text
        status_id = status.json()["statusId"]
        row = first.records()[0]
        encoded = base64.urlsafe_b64encode(row["ref"]["recordKey"]["value"].encode()).decode().rstrip("=")
        changed = first.client.put(first.url(f"/records/{encoded}/status"), headers=new_key(), json={
            "datasetGeneration": first.dataset_generation(), "recordKeyType": "text", "statusId": status_id, "expectedStatusRevision": 1,
        })
        assert changed.status_code == 200, changed.text
        first_batch = start_real(first, profile, url, "P committed", status_id)
        first_manual = wait_for(lambda: manual_item(first), "first real worker manual checkpoint")
        second_batch = start_real(second, profile, url, "Q committed")
        wait_for(lambda: batch_detail(second, second_batch)["batch"]["status"] == "blocked", "second batch blocked by shared lease")
        blocked = batch_detail(second, second_batch)
        assert blocked["batch"]["selectionOutcome"]["status"] == "temporarilyBusy", blocked
        assert blocked["taskCount"] == 0
        with app.state.session_factory() as session:
            leases = session.scalars(select(ProjectRecordLeaseRow)).all()
            assert len(leases) == 1 and leases[0].state == "held"
            assert json.loads(leases[0].lease_key)["source"] == "sheets"
            assert len(session.scalars(select(ProjectTaskRow)).all()) == 1
        if handoff == "resume":
            resume(first, first_manual)
        elif handoff == "loss":
            # Kill only the exact child owned by this isolated test Run.
            app.state.project_workflow_worker_manager._workers[first_manual["runId"]].process.kill()
        else:
            current = batch_detail(first, first_batch)["batch"]
            stopped = first.client.post(f"/api/v1/projects/{first.project}/batches/{first_batch}/stop", headers=new_key(), json={
                "expectedStatusRevision": current["statusRevision"], "reason": "shared-source owner cancellation",
            })
            assert stopped.status_code == 202, stopped.text
        second_manual = wait_for(lambda: manual_item(second), "second real worker after confirmed owner release")
        captured = second.client.get(f"/api/v1/projects/{second.project}/tasks/{second_manual['taskId']}").json()["inputSnapshot"]["inputs"][0]
        assert captured["statusId"] is None and captured["statusRevision"] == 1
        first_done = batch_detail(first, first_batch)
        assert not app.state.project_workflow_worker_manager.busy(first_manual["runId"])
        terminal = {"resume": "succeeded", "stop": "cancelled", "loss": "interrupted"}[handoff]
        assert first_done["statusCounts"].get(terminal) == 1, first_done
        with app.state.session_factory() as session:
            leases = session.scalars(select(ProjectRecordLeaseRow)).all()
            assert len(leases) == 2 and leases[0].lease_key == leases[1].lease_key
            assert sum(lease.state in {"held", "reconciling"} for lease in leases) == 1
            assert session.get(WorkflowRunRow, first_manual["runId"]).status == terminal
        if handoff != "resume":
            rejected = first.client.post(f"/api/v1/projects/{first.project}/manual-items/{first_manual['manualItemId']}/resume", headers=new_key(), json={
                "checkpointRevision": first_manual["checkpointRevision"], "expectedStatusRevision": first_manual["statusRevision"],
            })
            assert rejected.status_code == 409, rejected.text
        resume(second, second_manual)
        wait_for(lambda: batch_detail(second, second_batch)["batch"]["status"] == "completed", "second worker completion")
        assert batch_detail(second, second_batch)["statusCounts"]["succeeded"] == 1
        assert first.records()[0]["contentRevision"] == (2 if handoff == "resume" else 1)
        assert second.records()[0]["contentRevision"] == 2
        assert first.records()[0]["statusId"] == status_id
        assert second.records()[0]["statusId"] is None
        with app.state.session_factory() as session:
            assert not session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.state.in_(("held", "reconciling")))).all()
            assert len(session.scalars(select(ProjectTaskRow)).all()) == 2
        assert requests.count("/fixture") == 2
        assert first.transport.changes() == 0
