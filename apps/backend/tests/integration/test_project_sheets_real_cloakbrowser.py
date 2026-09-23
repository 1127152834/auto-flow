"""Real HTTP/SQLite/worker handoff; only Google transport and credentials are fixtures."""

import base64
import json
import shutil
import threading
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
from tests.fixtures.sheets import FakeSheetsTransport, new_key, open_sheets_table
from tests.fixtures.workflows import workflow_payload
from tests.integration.test_project_run_data_start import uid
from tests.integration.test_project_sheets_claims import plan_for, shared_tables
from tests.integration.test_project_sheets_sync import pull
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


def start_real(bound, profile, url, label, status_id=None, *, input_key="title", record_title=None, retain_environment=False):
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
        node("end", "project_end", {"retainEnvironment": {"enabled": True, "mode": "saveAs", "name": label, "recordTargets": []} if retain_environment else {"enabled": False}}),
    ]
    document = workflow_payload(uid())
    document["content"]["nodes"] = nodes
    document["content"]["edges"] = [{"id": uid(), "source": a["id"], "target": b["id"]} for a, b in pairwise(nodes)]
    saved = bound.client.post("/api/workflows", json={**document["content"], "id": document["id"], "clientRequestId": uid()})
    assert saved.status_code == 201, saved.text
    prefix = f"/api/v1/projects/{bound.project}"
    input_plan = plan_for(bound)
    input_plan["inputs"][0]["fieldBindings"][0]["fieldRef"]["fieldId"] = bound.field_id(input_key)
    input_plan["inputs"][0]["filter"] = {"type": "status", "operator": "eq", "statusId": status_id} if status_id else {"type": "status", "operator": "isNull"}
    if record_title is not None:
        input_plan["inputs"][0]["filter"] = {"type": "compare", "fieldId": bound.field_id("title"), "operator": "eq", "value": record_title}
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


def test_real_worker_uses_valid_input_while_bad_source_field_remains_diagnosed(
    tmp_path, valid_profile_values, real_cloak_page,
):
    executable, url, requests = real_cloak_page
    source = next(parent for parent in executable.parents if parent.name.startswith("chromium-"))
    shutil.copytree(source, tmp_path / "data" / "kernels" / source.name, symlinks=True)
    transport = FakeSheetsTransport({"数据": [["编号", "标题", "金额"], ["A-1", "valid", "not-a-number"]]})
    with open_sheets_table(tmp_path, transport, [
        ("code", "编号", "string"), ("title", "标题", "string"), ("amount", "金额", "number"),
    ]) as bound:
        pull(bound)
        before = bound.records()[0]
        amount = bound.field_id("amount")
        assert next(cell["value"] for cell in before["values"] if cell["fieldId"] == amount) == "not-a-number"
        assert [issue["fieldId"] for issue in before["validationIssues"]] == [amount]
        app = bound.client.app
        profile = app.state.profile_service.create(ProfileSpec.from_values({
            **valid_profile_values, "headless": True, "browser_version": source.name.removeprefix("chromium-"),
        }))
        batch = start_real(bound, profile, url, "valid field committed")
        item = wait_for(lambda: manual_item(bound), "D1 real worker checkpoint")
        detail = bound.client.get(f"/api/v1/projects/{bound.project}/tasks/{item['taskId']}").json()
        snapshot = detail["inputSnapshot"]
        captured = snapshot["inputs"][0]
        assert [mapping["fieldRef"]["fieldId"] for mapping in captured["fieldMappings"]] == [bound.field_id("title")]
        captured_values = {value["fieldId"]: value["value"] for value in captured["values"]}
        assert captured_values[bound.field_id("title")] == "valid"
        assert captured_values[amount] == "not-a-number"
        resume(bound, item)
        wait_for(lambda: batch_detail(bound, batch)["batch"]["status"] == "completed", "D1 worker completion")
        assert batch_detail(bound, batch)["statusCounts"]["succeeded"] == 1
        after = bound.records()[0]
        values = {cell["fieldId"]: cell["value"] for cell in after["values"]}
        assert values[bound.field_id("title")] == "valid field committed"
        assert values[amount] == "not-a-number"
        assert after["validationIssues"] == before["validationIssues"]
        assert after["ref"] == before["ref"]
        assert after["contentRevision"] == before["contentRevision"] + 1
        assert (after["statusRevision"], after["linkRevision"]) == (before["statusRevision"], before["linkRevision"])
        assert bound.client.get(f"/api/v1/projects/{bound.project}/tasks/{item['taskId']}").json()["inputSnapshot"] == snapshot

        # The same source row must fail selection when the bad field is required.
        rejected_batch = start_real(bound, profile, url, "invalid input", input_key="amount")
        wait_for(lambda: batch_detail(bound, rejected_batch)["batch"]["status"] == "failed", "D1 invalid input selection")
        rejected = batch_detail(bound, rejected_batch)
        assert rejected["taskCount"] == 0
        assert rejected["batch"]["selectionOutcome"]["status"] == "configurationError"
        assert bound.records()[0] == after
        with app.state.session_factory() as session:
            assert len(session.scalars(select(ProjectTaskRow)).all()) == 1
            assert not session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.state.in_(("held", "reconciling")))).all()
        assert not app.state.project_workflow_worker_manager.busy()
        assert requests.count("/fixture") == 1
        assert transport.changes() == 0


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
        from tests.integration.test_project_sheets_sync import sync_operations
        pending, = sync_operations(second, 'pending')
        assert pending['targetContentRevision'] == 2
        assert pending['status'] == 'pending'
        assert first.records()[0]["statusId"] == status_id
        assert second.records()[0]["statusId"] is None
        with app.state.session_factory() as session:
            assert not session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.state.in_(("held", "reconciling")))).all()
            assert len(session.scalars(select(ProjectTaskRow)).all()) == 2
        assert requests.count("/fixture") == 2
        assert first.transport.changes() == 0


def test_real_archive_waits_for_run_save_and_unknown_sheet_outcome(
    tmp_path, valid_profile_values, real_cloak_page, monkeypatch,
):
    from autoflow.providers.data.google_sheets import SheetsApiError
    from tests.integration.test_project_sheets_sync import (
        edit_title,
        push,
        sync_operations,
    )

    class LostWriteReply(FakeSheetsTransport):
        lose_reply = True

        def send(self, method, url, **kwargs):
            result = super().send(method, url, **kwargs)
            if self.lose_reply and url.endswith('/values:batchUpdate'):
                self.lose_reply = False
                raise SheetsApiError(0, 'timeout', 'injected response loss after remote commit')
            return result

    executable, url, requests = real_cloak_page
    source = next(parent for parent in executable.parents if parent.name.startswith('chromium-'))
    shutil.copytree(source, tmp_path / 'data' / 'kernels' / source.name, symlinks=True)
    transport = LostWriteReply({'数据': [['编号', '标题'], ['A', 'active'], ['B', 'remote-before'], ['C', 'save-before']]})
    with open_sheets_table(tmp_path, transport, [('code', '编号', 'string'), ('title', '标题', 'string')]) as bound:
        pull(bound)
        app, client = bound.client.app, bound.client
        prefix = f'/api/v1/projects/{bound.project}'
        rows = {row['ref']['recordKey']['value']: row for row in bound.records()}
        edit_title(bound, rows['B'], 'remote-committed')
        sent = push(bound)
        assert sent.status_code == 202, sent.text
        unknown, = sync_operations(bound, 'unknown')
        assert transport.grid('数据')[2] == ['B', 'remote-committed']
        profile = app.state.profile_service.create(ProfileSpec.from_values({
            **valid_profile_values, 'headless': True, 'browser_version': source.name.removeprefix('chromium-'),
        }))
        active_batch = start_real(bound, profile, url, 'must-not-write', record_title='active')
        active_item = wait_for(lambda: manual_item(bound), 'active worker waiting')
        saving_batch = start_real(bound, profile, url, 'saved-before-archive', record_title='save-before', retain_environment=True)

        def second_manual():
            response = client.get(prefix + '/manual-items')
            assert response.status_code == 200, response.text
            return next((item for item in response.json()['items'] if item['status'] == 'waiting' and item['manualItemId'] != active_item['manualItemId']), None)

        saving_item = wait_for(second_manual, 'second worker waiting')
        entered, release = threading.Event(), threading.Event()
        saves = []
        original_stage = app.state.environment_service.store.stage_candidate

        def stage_after_archive(save_id, instance_id):
            saves.append((save_id, instance_id))
            entered.set()
            assert release.wait(60), 'test must release accepted save after archive starts'
            return original_stage(save_id, instance_id)

        monkeypatch.setattr(app.state.environment_service.store, 'stage_candidate', stage_after_archive)
        try:
            resume(bound, saving_item)
            assert entered.wait(30), 'real worker must reach accepted save'
            save_id, _saving_instance = saves[0]
            save_operation = client.get(prefix + f'/operations/{save_id}')
            assert save_operation.status_code == 200 and save_operation.json()['status'] == 'running', save_operation.text
            before_rows = bound.records()
            pending, = sync_operations(bound, 'pending')
            writes = transport.changes()
            project = client.get(prefix).json()
            preview = client.get(prefix + '/lifecycle-impact', params={'action': 'archive'})
            assert preview.status_code == 200, preview.text
            assert any(blocker['code'] == 'SYNC_UNCONFIRMED' for blocker in preview.json()['blockers']), preview.json()
            archive_key = new_key()
            body = {'expectedManagementRevision': project['managementRevision'], 'impactRevision': preview.json()['impactRevision']}
            accepted = client.post(prefix + '/archive', headers=archive_key, json=body)
            assert accepted.status_code == 202, accepted.text
            archive_id = accepted.json()['operation']['operationId']
            assert client.get(prefix).json()['lifecycleState'] == 'closing'
            assert client.get(prefix + f'/operations/{archive_id}').json()['status'] == 'running'
            # The accepted save may finish; new edits and new batches must not enter.
            refused = client.post(prefix + '/tables', headers=new_key(), json={'name': 'must-not-create', 'sourceKind': 'local'})
            assert refused.status_code in {409, 423}, refused.text
            batch = batch_detail(bound, active_batch)['batch']
            refused = client.post(prefix + f"/automations/{batch['automationId']}/batches", headers=new_key(), json={
                'expectedAutomationRevision': 1, 'parameters': {}, 'maxTasks': 1, 'concurrency': 1,
            })
            assert refused.status_code in {409, 423}, refused.text
            refused = push(bound, mode='allPending')
            assert refused.status_code in {409, 423}, refused.text
        finally:
            release.set()
        saved = wait_for(lambda: (value if (value := client.get(prefix + f'/operations/{save_id}').json())['status'] != 'running' else None), 'accepted save settlement')
        assert saved['status'] == 'succeeded', saved
        assert len(saves) == 1
        assert saved['result']['phase'] == 'completed'
        saved_environment = saved['result']['saved']['environmentId']
        assert client.get(prefix + f'/environments/{saved_environment}').status_code == 200
        wait_for(lambda: batch_detail(bound, active_batch)['batch']['status'] == 'stopped', 'archive cancels live worker')
        wait_for(lambda: batch_detail(bound, saving_batch)['batch']['status'] in {'stopped', 'completed'}, 'saving task settles')
        assert batch_detail(bound, active_batch)['statusCounts']['cancelled'] == 1
        assert client.get(prefix + f"/manual-items/{active_item['manualItemId']}").json()['status'] == 'cancelled'
        assert not app.state.project_workflow_worker_manager.busy()
        assert app.state.project_workflow_dispatcher.blockers() == []
        app.state.project_lifecycle.repository.advance(bound.project)
        assert client.get(prefix).json()['lifecycleState'] == 'closing'
        assert client.get(prefix + f'/operations/{archive_id}').json()['status'] == 'running'
        assert sync_operations(bound, 'unknown') == [unknown]
        assert sync_operations(bound, 'pending') == [pending]
        assert bound.records() == before_rows
        assert transport.changes() == writes
        reconciled = client.post(bound.url(f"/sync-operations/{unknown['syncOperationId']}/reconcile"), headers=new_key(), json={'expectedStatusRevision': unknown['statusRevision']})
        assert reconciled.status_code == 202, reconciled.text
        assert reconciled.json()['operation']['result']['evidence']['outcome'] == 'matched'
        app.state.project_lifecycle.repository.advance(bound.project)
        wait_for(lambda: client.get(prefix).json()['lifecycleState'] == 'archived', 'archive after confirmed outcome')
        assert client.get(prefix + f'/operations/{archive_id}').json()['status'] == 'succeeded'
        assert sync_operations(bound, 'pending') == [pending]
        assert bound.records() == before_rows
        assert transport.changes() == writes
        assert transport.grid('数据')[3] == ['C', 'save-before']
        assert client.post(prefix + '/archive', headers=archive_key, json=body).json()['operation']['operationId'] == archive_id
        with app.state.session_factory() as session:
            leases = session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.project_id == bound.project)).all()
            assert len(leases) == 2 and all(lease.state == 'released' for lease in leases)
        assert requests.count('/fixture') == 2
        assert app.state.project_run_scheduler.blockers() == []
        assert app.state.project_lifecycle_coordinator.blockers() == []
        assert not list((tmp_path / 'tmp').glob('**/generation-*'))
