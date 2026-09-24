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


def start_real(bound, profile, url, label, status_id=None, *, input_key="title", record_title=None, retain_environment=False, link_input=False):
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
        node("end", "project_end", {"retainEnvironment": {"enabled": True, "mode": "saveAs", "name": label, "recordTargets": [{"recordRef": "{frozen[0]['recordRef']}", "expectedLinkRevision": "{frozen[0]['linkRevision']}", "replaceAllowed": False}] if link_input else []} if retain_environment else {"enabled": False}}),
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
    from dataclasses import replace
    from pathlib import Path

    from autoflow.providers.data.google_sheets import SheetsApiError
    from tests.fixtures.model_management import FakeCredentialStore
    from tests.fixtures.sheets import new_project
    from tests.integration.test_project_sheets_recovery import reconnect, restarted
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
    credentials = FakeCredentialStore()
    with open_sheets_table(tmp_path, transport, [('code', '编号', 'string'), ('title', '标题', 'string')], credentials=credentials) as bound:
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

        original_tasks = client.get(prefix + '/tasks').json()['items']
        run_ids = [item['runId'] for item in original_tasks]
        artifact_dirs = [app.state.project_workflow_worker_manager._artifact_root / identity for identity in run_ids]
        # Known owned file fixtures exercise content removal, not only empty dirs.
        for directory in artifact_dirs:
            (directory / 'owned-evidence.txt').write_text('owned artifact fixture', encoding='utf-8')
        unowned_artifact = artifact_dirs[0].parent / uid() / 'unowned-evidence.txt'
        unowned_artifact.parent.mkdir()
        unowned_artifact.write_text('unowned artifact fixture', encoding='utf-8')
        saved_root = app.state.environment_service.store.generation_dir(saved_environment, 1).parents[1]
        assert saved_root.is_dir()
        external = tmp_path / 'external-source.txt'
        external.write_text('unowned source must survive', encoding='utf-8')
        other_project = new_project(client, name='Unrelated project')

    # Keep the injected cleanup failure active until the second app has stopped.
    with monkeypatch.context() as cleanup_patch, restarted(reconnect(tmp_path, transport, credentials)) as client:
        bound = replace(bound, client=client)
        app = client.app
        archived = client.get(prefix).json()
        assert archived['lifecycleState'] == 'archived'
        assert bound.records() == before_rows
        assert sync_operations(bound, 'pending') == [pending]
        assert client.get(prefix + '/tasks').json()['items'] == original_tasks
        assert saved_root.is_dir()
        restored = client.post(prefix + '/restore', headers=new_key(), json={'expectedManagementRevision': archived['managementRevision']})
        assert restored.status_code in {200, 202}, restored.text
        assert client.get(prefix).json()['lifecycleState'] == 'active'
        # Explicit scheduler progress must not revive old batches or flush old intents.
        client.portal.call(app.state.project_run_scheduler.tick)
        assert client.get(prefix + '/tasks').json()['items'] == original_tasks
        assert sync_operations(bound, 'pending') == [pending]
        assert bound.records() == before_rows
        assert transport.changes() == writes and requests.count('/fixture') == 2
        preview = client.get(prefix + '/lifecycle-impact', params={'action': 'archive'}).json()
        archived_again = client.post(prefix + '/archive', headers=new_key(), json={
            'expectedManagementRevision': client.get(prefix).json()['managementRevision'], 'impactRevision': preview['impactRevision'],
        })
        assert archived_again.status_code in {200, 202}, archived_again.text
        app.state.project_lifecycle.repository.advance(bound.project)
        assert client.get(prefix).json()['lifecycleState'] == 'archived'
        preview = client.get(prefix + '/lifecycle-impact', params={'action': 'delete'}).json()
        assert preview['blockers'] == [] and preview['unsyncedCount'] == 1
        deletion_body = {'confirmationName': archived['name'], 'expectedManagementRevision': client.get(prefix).json()['managementRevision'], 'impactRevision': preview['impactRevision']}
        deletion_key = new_key()
        original_remove = shutil.rmtree

        def deny_owned_environment(path, *args, **kwargs):
            if Path(path) == saved_root:
                raise PermissionError('injected known owned directory cleanup failure')
            return original_remove(path, *args, **kwargs)

        cleanup_patch.setattr(shutil, 'rmtree', deny_owned_environment)
        deletion = client.request('DELETE', prefix, headers=deletion_key, json=deletion_body)
        assert deletion.status_code in {200, 202}, deletion.text
        deletion_id = deletion.json()['operation']['operationId']
        app.state.project_lifecycle.repository.advance(bound.project)
        assert client.get(prefix).json()['lifecycleState'] == 'deleting'
        failed = client.get(prefix + f'/operations/{deletion_id}').json()
        assert failed['status'] == 'failed' and failed['error']['code'] == 'DELETE_CLEANUP_FAILED'
        assert str(saved_root) in failed['error']['details']['cleanup']['residue']
        assert sync_operations(bound, 'pending') == [pending]
        assert saved_root.is_dir()

    with restarted(reconnect(tmp_path, transport, credentials)) as client:
        app = client.app
        wait_for(lambda: client.get(prefix).status_code == 404, 'startup coordinator resumes original delete')
        completed = client.get('/api/v1/workspace/operations/by-idempotency-key/' + deletion_key['Idempotency-Key'])
        assert completed.status_code == 200 and completed.json()['status'] == 'succeeded', completed.text
        assert completed.json()['operationId'] == deletion_id
        assert not saved_root.exists()
        assert all(not directory.exists() for directory in artifact_dirs)
        assert unowned_artifact.read_text(encoding='utf-8') == 'unowned artifact fixture'
        assert client.get(f'/api/v1/projects/{other_project}').status_code == 200
        assert app.state.profile_service.get(profile.id).id == profile.id
        assert external.read_text(encoding='utf-8') == 'unowned source must survive'
        assert transport.changes() == writes and requests.count('/fixture') == 2
        assert transport.grid('数据')[3] == ['C', 'save-before']
        assert app.state.project_run_scheduler.blockers() == []
        assert app.state.project_lifecycle_coordinator.blockers() == []


@pytest.mark.parametrize("outcome", ["pending", "unknown"])
def test_real_archive_restore_disposition_rebind_isolates_history(
    tmp_path, valid_profile_values, real_cloak_page, outcome,
):
    from dataclasses import replace

    from autoflow.providers.data.google_sheets import SheetsApiError
    from tests.fixtures.model_management import FakeCredentialStore
    from tests.fixtures.sheets import binding_impact
    from tests.integration.test_project_sheets_recovery import reconnect, restarted
    from tests.integration.test_project_sheets_sync import push, sync_operations

    executable, url, requests = real_cloak_page
    source = next(parent for parent in executable.parents if parent.name.startswith('chromium-'))
    shutil.copytree(source, tmp_path / 'data' / 'kernels' / source.name, symlinks=True)
    transport = FakeSheetsTransport({
        '数据': [['编号', '标题'], ['A', 'old source']],
        '新来源': [['编号', '标题'], ['A', 'new source']],
    })
    credentials = FakeCredentialStore()
    with open_sheets_table(tmp_path, transport, [('code', '编号', 'string'), ('title', '标题', 'string')], credentials=credentials) as bound:
        pull(bound)
        client, app = bound.client, bound.client.app
        prefix = f'/api/v1/projects/{bound.project}'
        status = client.post(bound.url('/statuses'), headers=new_key(), json={
            'name': 'old state', 'color': '#123456', 'order': 1, 'expectedTableRevision': bound.table_revision(),
        })
        assert status.status_code == 201, status.text
        status_id = status.json()['statusId']
        changed = client.put(bound.url('/records/QQ/status'), headers=new_key(), json={
            'datasetGeneration': bound.dataset_generation(), 'recordKeyType': 'text',
            'statusId': status_id, 'expectedStatusRevision': 1,
        })
        assert changed.status_code == 200, changed.text
        profile = app.state.profile_service.create(ProfileSpec.from_values({
            **valid_profile_values, 'headless': True, 'browser_version': source.name.removeprefix('chromium-'),
        }))
        batch = start_real(bound, profile, url, 'local committed', status_id, retain_environment=True, link_input=True)
        item = wait_for(lambda: manual_item(bound), 'archive/rebind worker checkpoint')
        resume(bound, item)
        wait_for(lambda: batch_detail(bound, batch)['batch']['status'] == 'completed', 'archive/rebind worker completion')
        assert batch_detail(bound, batch)['statusCounts']['succeeded'] == 1
        old, = bound.records()
        assert old['statusId'] == status_id and old['currentEnvironmentId']
        generation, epoch = bound.dataset_generation(), bound.binding['bindingEpoch']
        if outcome == 'unknown':
            transport.fail_writes.append(SheetsApiError(0, 'timeout', 'injected unknown send'))
            sent = push(bound)
            assert sent.status_code == 202, sent.text
        intent, = sync_operations(bound, outcome)
        snapshot = client.get(prefix + f"/tasks/{item['taskId']}").json()['inputSnapshot']
        tasks = client.get(prefix + '/tasks').json()['items']
        writes = transport.changes()
        impact = client.get(prefix + '/lifecycle-impact', params={'action': 'archive'}).json()
        archived = client.post(prefix + '/archive', headers=new_key(), json={
            'expectedManagementRevision': client.get(prefix).json()['managementRevision'], 'impactRevision': impact['impactRevision'],
        })
        assert archived.status_code == 202, archived.text
        if outcome == 'unknown':
            assert client.get(prefix).json()['lifecycleState'] == 'closing'
            reconciled = client.post(bound.url(f"/sync-operations/{intent['syncOperationId']}/reconcile"), headers=new_key(), json={'expectedStatusRevision': intent['statusRevision']})
            assert reconciled.status_code == 202, reconciled.text
            assert reconciled.json()['operation']['result']['evidence']['outcome'] == 'notMatched'
        app.state.project_lifecycle.repository.advance(bound.project)
        wait_for(lambda: client.get(prefix).json()['lifecycleState'] == 'archived', 'archive after explicit reconciliation')

    with restarted(reconnect(tmp_path, transport, credentials)) as client:
        bound = replace(bound, client=client)
        restored = client.post(prefix + '/restore', headers=new_key(), json={'expectedManagementRevision': client.get(prefix).json()['managementRevision']})
        assert restored.status_code in {200, 202}, restored.text
        client.portal.call(client.app.state.project_run_scheduler.tick)
        assert bound.records() == [old]
        assert client.get(prefix + '/tasks').json()['items'] == tasks
        if outcome == 'pending':
            assert sync_operations(bound, 'pending') == [intent]
            abandoned = client.post(bound.url(f"/sync-operations/{intent['syncOperationId']}/abandon"), headers=new_key(), json={'expectedStatusRevision': intent['statusRevision'], 'reason': 'explicit source replacement'})
            assert abandoned.status_code == 200, abandoned.text
            assert abandoned.json()['error']['code'] == 'SYNC_ABANDONED'
        settled = sync_operations(bound)
        assert not sync_operations(bound, 'pending') and not sync_operations(bound, 'unknown')
        body = {
            'connectionId': bound.connection, 'spreadsheetId': transport.spreadsheet_id,
            'sheetId': transport.ids['新来源'], 'identityStrategy': {'kind': 'column', 'columnId': 'A'},
            'mapping': bound.binding['mapping'], 'expectedTableRevision': bound.table_revision(), 'expectedBindingEpoch': epoch,
        }
        rebound = client.put(bound.url('/sheets/binding'), headers=new_key(), json=binding_impact(client, bound.project, bound.table, body))
        assert rebound.status_code == 202, rebound.text
        bound.binding = rebound.json()['operation']['result']
        assert bound.binding['bindingEpoch'] == epoch + 1 and bound.dataset_generation() != generation
        assert bound.records() == []
        assert push(bound, epoch=epoch).status_code == 412
        assert push(bound, mode='allPending').status_code == 202
        pull(bound)
        fresh, = bound.records()
        assert fresh['ref']['recordKey'] == old['ref']['recordKey']
        assert fresh['ref']['datasetGeneration'] != old['ref']['datasetGeneration']
        assert fresh['statusId'] is None and fresh['currentEnvironmentId'] is None
        assert next(cell['value'] for cell in fresh['values'] if cell['fieldId'] == bound.field_id('title')) == 'new source'
        assert sync_operations(bound) == settled
        assert client.get(prefix + '/tasks').json()['items'] == tasks
        assert client.get(prefix + f"/tasks/{item['taskId']}").json()['inputSnapshot'] == snapshot
        assert client.get(prefix + f"/environments/{old['currentEnvironmentId']}").status_code == 200
        assert requests.count('/fixture') == 1 and transport.changes() == writes
        assert transport.grid('数据')[1] == ['A', 'old source']
        assert transport.grid('新来源')[1] == ['A', 'new source']
        assert not client.app.state.project_workflow_worker_manager.busy()


def test_real_loop_keeps_two_sheet_intents_when_third_write_fails(
    tmp_path, valid_profile_values, real_cloak_page,
):
    from autoflow.infrastructure.database.project_data_models import DataFieldRow
    from tests.fixtures.sheets import new_field, new_table
    from tests.integration.test_project_run_data_start import _input
    from tests.integration.test_project_sheets_sync import sync_operations

    executable, url, requests = real_cloak_page
    source = next(parent for parent in executable.parents if parent.name.startswith('chromium-'))
    shutil.copytree(source, tmp_path / 'data' / 'kernels' / source.name, symlinks=True)
    transport = FakeSheetsTransport({'数据': [['编号', '标题'], ['A', 'orig-0'], ['B', 'orig-1'], ['C', 'orig-2']]})
    with open_sheets_table(tmp_path, transport, [('code', '编号', 'string'), ('title', '标题', 'string')]) as bound:
        client, app = bound.client, bound.client.app
        prefix = f'/api/v1/projects/{bound.project}'
        trigger = new_table(client, bound.project, '批次入口')
        trigger_field = new_field(client, bound.project, trigger['tableId'], 'token', '令牌', expectedTableRevision=trigger['tableRevision'])
        created = client.post(prefix + f"/tables/{trigger['tableId']}/records", headers=new_key(), json={
            'datasetGeneration': trigger['datasetGeneration'],
            'values': [{'fieldId': trigger_field['ref']['fieldId'], 'value': 'once'}],
        })
        assert created.status_code == 201, created.text
        with app.state.session_factory.begin() as session:
            session.get(DataFieldRow, (bound.field_id('title'), bound.dataset_generation())).validation = {'pattern': '^row-[01]$'}
        pull(bound)
        before = bound.records()
        profile = app.state.profile_service.create(ProfileSpec.from_values({
            **valid_profile_values, 'headless': True, 'browser_version': source.name.removeprefix('chromium-'),
        }))
        def node(identity, kind, data):
            return {'id': identity, 'type': kind, 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': kind, **data}}
        nodes = [
            node('inputs', 'project_data', {'operation': 'inputs', 'variableName': 'trigger', 'arguments': {}}),
            node('open', 'open_page', {'url': url, 'timeout': 30}),
            node('query', 'project_data', {'operation': 'queryRecords', 'variableName': 'rows',
                'arguments': {'tableId': bound.table, 'datasetGeneration': bound.dataset_generation(), 'fieldIds': [bound.field_id('title')], 'readPurpose': 'condition', 'filter': None, 'orderBy': [], 'cursor': None, 'limit': 3},
                'tableGrant': {'tableId': bound.table, 'datasetGeneration': bound.dataset_generation(), 'operations': ['queryRecords'], 'fieldIds': [bound.field_id('title')], 'readPurposes': ['condition']}}),
            node('loop', 'loop', {'count': 3, 'indexVariable': 'index'}),
            node('write', 'project_data', {'operation': 'updateRecord', 'variableName': 'saved',
                'arguments': {'recordRef': "{rows['items'][{index}]['ref']}", 'changes': {bound.field_id('title'): 'row-{index}'},
                              'expectedContentRevision': "{rows['items'][{index}]['contentRevision']}"},
                'tableGrant': {'tableId': bound.table, 'datasetGeneration': bound.dataset_generation(), 'operations': ['updateRecord'], 'fieldIds': [bound.field_id('title')], 'readPurposes': ['condition']}}),
            node('end', 'project_end', {'retainEnvironment': {'enabled': False}}),
        ]
        document = workflow_payload(uid())
        document['content']['nodes'] = nodes
        document['content']['edges'] = [
            {'id': uid(), 'source': a, 'target': b} for a, b in [('inputs', 'open'), ('open', 'query'), ('query', 'loop')]
        ] + [
            {'id': uid(), 'source': 'loop', 'target': 'write', 'sourceHandle': 'loop'},
            {'id': uid(), 'source': 'loop', 'target': 'end', 'sourceHandle': 'done'},
        ]
        saved = client.post('/api/workflows', json={**document['content'], 'id': document['id'], 'clientRequestId': uid()})
        assert saved.status_code == 201, saved.text
        automation = client.post(prefix + '/automations', headers=new_key(), json={
            'name': 'Sheets 两次成功第三次失败', 'description': '', 'workflowId': saved.json()['id'],
            'inputPlan': {'inputs': [_input(bound.project, trigger, trigger_field, 'trigger')]}, 'parameterSchema': [],
            'environmentPolicy': {'source': 'newFromProfile', 'profileId': profile.id, 'proxyOverride': {'mode': 'none'}, 'modelProviderId': None},
            'runPolicy': {'maxTasks': 1, 'concurrency': 1, 'maxLiveInstances': 1, 'continueAfterFailure': False, 'automaticExecutionTimeoutSeconds': 60, 'manualDeadlineSeconds': 180},
        })
        assert automation.status_code == 201, automation.text
        config = automation.json()
        validation = client.get(prefix + f"/automations/{config['automationId']}/validation")
        assert validation.status_code == 200 and validation.json()['runnable'], validation.text
        accepted = client.post(prefix + f"/automations/{config['automationId']}/batches", headers=new_key(), json={
            'expectedAutomationRevision': config['managementRevision'], 'parameters': {}, 'maxTasks': 1, 'concurrency': 1,
        })
        assert accepted.status_code == 202, accepted.text
        batch = accepted.json()['operation']['result']['batch']['batchId']
        wait_for(lambda: batch_detail(bound, batch)['batch']['status'] == 'failed', 'third Sheets write fails after two commits')
        detail = batch_detail(bound, batch)
        assert detail['statusCounts']['failed'] == 1, detail
        task, = client.get(prefix + '/tasks', params={'batchId': batch}).json()['items']
        attempts = client.get(prefix + f"/tasks/{task['taskId']}/node-attempts").json()['items']
        writes = [attempt for attempt in attempts if attempt['nodeId'] == 'write']
        assert [attempt['status'] for attempt in writes] == ['succeeded', 'succeeded', 'failed'], attempts
        assert writes[-1]['error']['code'] == 'INVALID_PROJECT_DATA'
        assert not any(attempt['nodeId'] == 'end' for attempt in attempts)
        after = bound.records()
        title = bound.field_id('title')
        assert [next(cell['value'] for cell in row['values'] if cell['fieldId'] == title) for row in after] == ['row-0', 'row-1', 'orig-2']
        assert [row['contentRevision'] for row in after] == [2, 2, 1]
        assert [(row['statusRevision'], row['linkRevision']) for row in after] == [(row['statusRevision'], row['linkRevision']) for row in before]
        pending = sync_operations(bound, 'pending')
        assert len(pending) == 2 and {item['record']['recordKey']['value'] for item in pending} == {'A', 'B'}
        assert {item['targetContentRevision'] for item in pending} == {2}
        assert not sync_operations(bound, 'unknown')
        assert transport.changes() == 0 and transport.grid('数据')[1:] == [['A', 'orig-0'], ['B', 'orig-1'], ['C', 'orig-2']]
        assert requests.count('/fixture') == 1
        with app.state.session_factory() as session:
            leases = session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.task_id == task['taskId'])).all()
            assert all(lease.state == 'released' for lease in leases)
        assert not app.state.project_workflow_worker_manager.busy()


def test_real_worker_uses_reliable_cache_during_source_outage_but_rejects_invalid_identity(
    tmp_path, valid_profile_values, real_cloak_page,
):
    from autoflow.infrastructure.database.project_sync_models import SheetsBindingRow
    from autoflow.providers.data.google_sheets import SheetsApiError
    from tests.integration.test_project_sheets_sync import sync_operations

    class OutageTransport(FakeSheetsTransport):
        offline = False

        def send(self, *args, **kwargs):
            if self.offline:
                self.fail_next = SheetsApiError(-1, "offline", "controlled source outage")
            return super().send(*args, **kwargs)

    executable, url, requests = real_cloak_page
    source = next(parent for parent in executable.parents if parent.name.startswith("chromium-"))
    shutil.copytree(source, tmp_path / "data" / "kernels" / source.name, symlinks=True)
    transport = OutageTransport({"数据": [["编号", "标题"], ["A-1", "cached input"]]})
    with open_sheets_table(tmp_path, transport, [("code", "编号", "string"), ("title", "标题", "string")]) as bound:
        app = bound.client.app

        def proof():
            with app.state.session_factory() as session:
                return session.get(SheetsBindingRow, bound.table).identity_verification

        def fail_pull():
            transport.offline = True
            failed = bound.client.post(bound.url("/sync/pull"), headers=new_key(), json={
                "expectedTableRevision": bound.table_revision(),
            })
            assert failed.status_code == 502, failed.text
            assert failed.json()["error"]["code"] == "SHEETS_API_FAILED"

        profile = app.state.profile_service.create(ProfileSpec.from_values({
            **valid_profile_values, "headless": True, "browser_version": source.name.removeprefix("chromium-"),
        }))
        fail_pull()
        initial_batch = start_real(bound, profile, url, "incomplete cache must block")
        wait_for(lambda: batch_detail(bound, initial_batch)["batch"]["status"] == "failed", "initial source outage blocks input")
        initial = batch_detail(bound, initial_batch)
        assert initial["taskCount"] == 0
        assert initial["batch"]["selectionOutcome"]["status"] == "configurationError"
        assert bound.records() == [] and requests.count("/fixture") == 0
        with app.state.session_factory() as session:
            assert not session.scalars(select(ProjectTaskRow)).all()
            assert not session.scalars(select(ProjectRecordLeaseRow)).all()
        assert not app.state.project_workflow_worker_manager.busy()
        transport.offline = False
        pull(bound)
        before = bound.records()[0]
        verified = proof()
        assert verified["valid"] is True
        fail_pull()
        assert proof() == verified and bound.records()[0] == before
        calls = len(transport.calls)
        batch = start_real(bound, profile, url, "committed while offline")
        item = wait_for(lambda: manual_item(bound), "offline cached input checkpoint")
        task = bound.client.get(f"/api/v1/projects/{bound.project}/tasks/{item['taskId']}").json()
        captured = task["inputSnapshot"]["inputs"][0]
        assert captured["recordRef"] == before["ref"]
        assert captured["contentRevision"] == before["contentRevision"]
        assert {cell["fieldId"]: cell["value"] for cell in captured["values"]}[bound.field_id("title")] == "cached input"
        resume(bound, item)
        wait_for(lambda: batch_detail(bound, batch)["batch"]["status"] == "completed", "offline cached input completion")
        assert batch_detail(bound, batch)["statusCounts"]["succeeded"] == 1
        after = bound.records()[0]
        assert {cell["fieldId"]: cell["value"] for cell in after["values"]}[bound.field_id("title")] == "committed while offline"
        assert after["contentRevision"] == before["contentRevision"] + 1
        assert after["ref"] == before["ref"]
        assert any(op["kind"] == "push" and op["status"] == "pending" for op in sync_operations(bound))
        assert len(transport.calls) == calls and transport.changes() == 0

        # A completed scan can revoke identity trust; a later outage cannot restore it.
        transport.offline = False
        transport.grid("数据").append(["A-1", "duplicate identity"])
        pull(bound)
        invalid = proof()
        assert invalid["valid"] is False
        fail_pull()
        assert proof() == invalid
        calls = len(transport.calls)
        rejected_batch = start_real(bound, profile, url, "must not run")
        wait_for(lambda: batch_detail(bound, rejected_batch)["batch"]["status"] == "failed", "invalid cached identity rejection")
        rejected = batch_detail(bound, rejected_batch)
        assert rejected["taskCount"] == 0
        assert rejected["batch"]["selectionOutcome"]["status"] == "configurationError"
        assert bound.records()[0] == after
        with app.state.session_factory() as session:
            assert len(session.scalars(select(ProjectTaskRow)).all()) == 1
            assert not session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.state.in_(("held", "reconciling")))).all()
        assert not app.state.project_workflow_worker_manager.busy()
        assert requests.count("/fixture") == 1
        assert len(transport.calls) == calls and transport.changes() == 0



def test_real_shared_sheet_peer_removal_requires_fresh_proof_after_source_outage(
    tmp_path, valid_profile_values, real_cloak_page,
):
    from autoflow.infrastructure.database.project_sync_models import SheetsBindingRow
    from autoflow.providers.data.google_sheets import SheetsApiError
    from tests.fixtures.sheets import unbind_impact
    from tests.integration.test_project_sheets_sync import sync_operations

    executable, url, requests = real_cloak_page
    source = next(parent for parent in executable.parents if parent.name.startswith("chromium-"))
    shutil.copytree(source, tmp_path / "data" / "kernels" / source.name, symlinks=True)
    with shared_tables(tmp_path) as (first, second):
        app = first.client.app
        transport = first.transport
        before = first.records()[0]
        source_time = first.client.get(first.url("/sync")).json()["summary"]["lastPulledAt"]
        profile = app.state.profile_service.create(ProfileSpec.from_values({
            **valid_profile_values, "headless": True, "browser_version": source.name.removeprefix("chromium-"),
        }))
        transport.grid("数据").append(["A-1", "duplicate identity", "note"])
        pull(second)
        with app.state.session_factory() as session:
            assert session.get(SheetsBindingRow, second.table).identity_verification["valid"] is False
        removed = second.client.request("DELETE", second.url("/sheets/binding"), headers=new_key(), json={
            "expectedTableRevision": second.table_revision(),
            "impactRevision": unbind_impact(second.client, second.project, second.table),
        })
        assert removed.status_code == 202, removed.text
        assert second.client.get(second.url("/sheets/binding")).json() is None
        transport.fail_next = SheetsApiError(-1, "offline", "controlled source outage after peer removal")
        failed = first.client.post(first.url("/sync/pull"), headers=new_key(), json={
            "expectedTableRevision": first.table_revision(),
        })
        assert failed.status_code == 502, failed.text
        assert failed.json()["error"]["code"] == "SHEETS_API_FAILED"
        calls = len(transport.calls)
        blocked_batch = start_real(first, profile, url, "removed peer cannot erase failed identity")
        wait_for(lambda: batch_detail(first, blocked_batch)["batch"]["status"] == "failed", "stale peer proof blocks public batch")
        blocked = batch_detail(first, blocked_batch)
        assert blocked["taskCount"] == 0
        assert blocked["batch"]["selectionOutcome"]["status"] == "configurationError"
        assert first.records()[0] == before
        assert first.client.get(first.url("/sync")).json()["summary"]["lastPulledAt"] == source_time
        assert len(transport.calls) == calls and requests.count("/fixture") == 0
        with app.state.session_factory() as session:
            assert not session.scalars(select(ProjectTaskRow)).all()
            assert not session.scalars(select(ProjectRecordLeaseRow)).all()
        assert not app.state.project_workflow_worker_manager.busy()

        transport.grid("数据").pop()
        pull(first)
        with app.state.session_factory() as session:
            binding = session.get(SheetsBindingRow, first.table)
            assert binding.identity_verification["valid"] is True
            assert binding.identity_verification["bindingPeers"] == [[first.table, binding.binding_epoch]]
        assert first.records()[0] == before
        calls = len(transport.calls)
        recovered_batch = start_real(first, profile, url, "fresh proof permits local commit")
        item = wait_for(lambda: manual_item(first), "recovered shared proof reaches real worker")
        captured = first.client.get(f"/api/v1/projects/{first.project}/tasks/{item['taskId']}").json()["inputSnapshot"]["inputs"][0]
        assert captured["recordRef"] == before["ref"]
        assert captured["contentRevision"] == before["contentRevision"]
        assert {cell["fieldId"]: cell["value"] for cell in captured["values"]} == {
            cell["fieldId"]: cell["value"] for cell in before["values"]
        }
        resume(first, item)
        wait_for(lambda: batch_detail(first, recovered_batch)["batch"]["status"] == "completed", "recovered shared proof completes")
        assert batch_detail(first, recovered_batch)["statusCounts"]["succeeded"] == 1
        after = first.records()[0]
        assert after["ref"] == before["ref"]
        assert after["contentRevision"] == before["contentRevision"] + 1
        assert {cell["fieldId"]: cell["value"] for cell in after["values"]}[first.field_id("title")] == "fresh proof permits local commit"
        pending = sync_operations(first, "pending")
        assert len(pending) == 1 and pending[0]["targetContentRevision"] == after["contentRevision"]
        assert transport.changes() == 0 and len(transport.calls) == calls
        assert requests.count("/fixture") == 1
        assert batch_detail(first, blocked_batch)["taskCount"] == 0
        assert batch_detail(first, blocked_batch)["batch"]["status"] == "failed"
        with app.state.session_factory() as session:
            assert len(session.scalars(select(ProjectTaskRow)).all()) == 1
            assert not session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.state.in_(("held", "reconciling")))).all()
        assert not app.state.project_workflow_worker_manager.busy()


def test_real_shared_sheet_rebinding_requires_current_peer_namespace_and_generation(
    tmp_path, valid_profile_values, real_cloak_page,
):
    from autoflow.infrastructure.database.project_sync_models import SheetsBindingRow
    from autoflow.providers.data.google_sheets import SheetsApiError
    from tests.fixtures.sheets import binding_impact
    from tests.integration.test_project_sheets_sync import sync_operations

    executable, url, requests = real_cloak_page
    source = next(parent for parent in executable.parents if parent.name.startswith("chromium-"))
    shutil.copytree(source, tmp_path / "data" / "kernels" / source.name, symlinks=True)
    with shared_tables(tmp_path) as (first, second):
        app, transport = first.client.app, first.transport
        originals = [bound.records()[0] for bound in (first, second)]
        profile = app.state.profile_service.create(ProfileSpec.from_values({
            **valid_profile_values, "headless": True, "browser_version": source.name.removeprefix("chromium-"),
        }))

        def rebind(column):
            body = {
                "connectionId": second.connection, "spreadsheetId": transport.spreadsheet_id, "sheetId": 1000,
                "identityStrategy": {"kind": "column", "columnId": column}, "mapping": second.binding["mapping"],
                "expectedTableRevision": second.table_revision(), "expectedBindingEpoch": second.binding["bindingEpoch"],
            }
            accepted = second.client.put(second.url("/sheets/binding"), headers=new_key(), json=binding_impact(
                second.client, second.project, second.table, body,
            ))
            assert accepted.status_code == 202, accepted.text
            second.binding = accepted.json()["operation"]["result"]
            assert second.records() == []

        rebind("B")
        incompatible_generation = second.dataset_generation()
        assert incompatible_generation != originals[1]["ref"]["datasetGeneration"]
        assert second.binding["bindingEpoch"] == 2
        pull(second)
        assert second.records()[0]["ref"]["recordKey"]["value"] == "original"
        transport.fail_next = SheetsApiError(-1, "offline", "controlled outage after peer rebind")
        failed = first.client.post(first.url("/sync/pull"), headers=new_key(), json={
            "expectedTableRevision": first.table_revision(),
        })
        assert failed.status_code == 502, failed.text
        assert failed.json()["error"]["code"] == "SHEETS_API_FAILED"

        blocked_batches = []
        # Even a new complete local scan cannot reconcile different identity columns.
        for refresh in (False, True):
            if refresh:
                pull(first)
            calls = len(transport.calls)
            batch = start_real(first, profile, url, f"incompatible peer namespace {refresh}")
            blocked_batches.append(batch)
            wait_for(lambda batch=batch: batch_detail(first, batch)["batch"]["status"] == "failed", "incompatible namespace blocks input")
            blocked = batch_detail(first, batch)
            assert blocked["taskCount"] == 0
            assert blocked["batch"]["selectionOutcome"]["status"] == "configurationError"
            assert first.records()[0] == originals[0]
            assert len(transport.calls) == calls and requests.count("/fixture") == 0
            with app.state.session_factory() as session:
                assert not session.scalars(select(ProjectTaskRow)).all()
                assert not session.scalars(select(ProjectRecordLeaseRow)).all()
            assert not app.state.project_workflow_worker_manager.busy()

        rebind("A")
        assert second.binding["bindingEpoch"] == 3
        assert second.dataset_generation() not in {incompatible_generation, originals[1]["ref"]["datasetGeneration"]}
        pull(second)
        pull(first)
        with app.state.session_factory() as session:
            bindings = [session.get(SheetsBindingRow, bound.table) for bound in (first, second)]
            assert all(binding.identity_verification["valid"] for binding in bindings)
            assert bindings[0].identity_verification["namespace"] == bindings[1].identity_verification["namespace"]
            assert bindings[0].identity_verification["bindingPeers"] == sorted([[binding.table_id, binding.binding_epoch] for binding in bindings])
        calls = len(transport.calls)
        for index, bound in enumerate((first, second)):
            before = bound.records()[0]
            assert before["ref"]["datasetGeneration"] == bound.dataset_generation()
            assert {cell["fieldId"]: cell["value"] for cell in before["values"]} == {
                cell["fieldId"]: cell["value"] for cell in originals[index]["values"]
            }
            label = f"current generation {index}"
            batch = start_real(bound, profile, url, label)
            item = wait_for(lambda bound=bound: manual_item(bound), "current namespace reaches real worker")
            captured = bound.client.get(f"/api/v1/projects/{bound.project}/tasks/{item['taskId']}").json()["inputSnapshot"]["inputs"][0]
            assert captured["recordRef"] == before["ref"]
            assert captured["contentRevision"] == before["contentRevision"]
            assert {cell["fieldId"]: cell["value"] for cell in captured["values"]} == {
                cell["fieldId"]: cell["value"] for cell in before["values"]
            }
            assert captured["sourceIdentity"]["bindingEpoch"] == (1 if index == 0 else 3)
            resume(bound, item)
            wait_for(lambda bound=bound, batch=batch: batch_detail(bound, batch)["batch"]["status"] == "completed", "current generation completes")
            assert batch_detail(bound, batch)["statusCounts"]["succeeded"] == 1
            after = bound.records()[0]
            assert after["ref"] == before["ref"]
            assert after["contentRevision"] == before["contentRevision"] + 1
            assert {cell["fieldId"]: cell["value"] for cell in after["values"]}[bound.field_id("title")] == label
            pending = sync_operations(bound, "pending")
            assert len(pending) == 1 and pending[0]["targetContentRevision"] == after["contentRevision"]
        assert len(transport.calls) == calls and transport.changes() == 0
        assert requests.count("/fixture") == 2
        for batch in blocked_batches:
            assert batch_detail(first, batch)["batch"]["status"] == "failed"
            assert batch_detail(first, batch)["taskCount"] == 0
        with app.state.session_factory() as session:
            assert len(session.scalars(select(ProjectTaskRow)).all()) == 2
            assert not session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.state.in_(("held", "reconciling")))).all()
        assert not app.state.project_workflow_worker_manager.busy()


def test_real_opposing_writes_enter_manual_branch_without_stealing_leases(
    tmp_path, valid_profile_values, real_cloak_page,
):
    from autoflow.infrastructure.database.project_run_models import (
        ProjectTaskRecordCursorRow,
    )
    from tests.integration.test_project_sheets_sync import sync_operations

    executable, url, requests = real_cloak_page
    source = next(parent for parent in executable.parents if parent.name.startswith("chromium-"))
    shutil.copytree(source, tmp_path / "data" / "kernels" / source.name, symlinks=True)
    transport = FakeSheetsTransport({"数据": [["编号", "标题"], ["A", "first"], ["B", "second"]]})
    with open_sheets_table(tmp_path, transport, [("code", "编号", "string"), ("title", "标题", "string")]) as bound:
        pull(bound)
        app, client = bound.client.app, bound.client
        prefix = f"/api/v1/projects/{bound.project}"
        assert app.state.project_workflow_dispatcher.capacity == 2
        profile = app.state.profile_service.create(ProfileSpec.from_values({
            **valid_profile_values, "headless": True, "browser_version": source.name.removeprefix("chromium-"),
        }))
        title, code = bound.field_id("title"), bound.field_id("code")
        generation = bound.dataset_generation()
        before = bound.records()

        def node(identity, kind, data):
            return {"id": identity, "type": kind, "position": {"x": 0, "y": 0}, "data": {"moduleType": kind, **data}}

        batches = []
        for own, other in (("A", "B"), ("B", "A")):
            grant = {"tableId": bound.table, "datasetGeneration": generation,
                     "operations": ["updateRecord"], "fieldIds": [title], "readPurposes": ["workflow"]}
            document = workflow_payload(uid())
            document["content"]["nodes"] = [
                node("inputs", "project_data", {"operation": "inputs", "variableName": "frozen", "arguments": {}}),
                node("open", "open_page", {"url": url, "timeout": 30}),
                node("own", "project_data", {"operation": "updateRecord", "variableName": "owned", "tableGrant": grant,
                     "arguments": {"recordRef": "{frozen[0]['recordRef']}", "changes": {title: "owned-" + own},
                                   "expectedContentRevision": "{frozen[0]['contentRevision']}"}}),
                node("barrier", "project_manual", {"reason": "owner barrier", "timeoutSeconds": 120}),
                node("query", "project_data", {"operation": "queryRecords", "variableName": "other",
                     "tableGrant": {**grant, "operations": ["queryRecords"], "fieldIds": [title, code]},
                     "arguments": {"tableId": bound.table, "datasetGeneration": generation, "fieldIds": [title, code],
                                   "readPurpose": "workflow", "filter": {"type": "compare", "fieldId": code, "operator": "eq", "value": other},
                                   "orderBy": [], "cursor": None, "limit": 1}}),
                node("cross", "project_data", {"operation": "updateRecord", "variableName": "crossed", "tableGrant": grant,
                     "arguments": {"recordRef": "{other['items'][0]['ref']}", "changes": {title: "must-not-write"},
                                   "expectedContentRevision": "{other['items'][0]['contentRevision']}"}}),
                node("conflict", "project_manual", {"reason": "cross conflict", "timeoutSeconds": 120}),
            ]
            document["content"]["edges"] = [
                {"id": uid(), "source": a, "target": b}
                for a, b in (("inputs", "open"), ("open", "own"), ("own", "barrier"), ("barrier", "query"), ("query", "cross"))
            ] + [{"id": uid(), "source": "cross", "target": "conflict", "sourceHandle": "error"}]
            saved = client.post("/api/workflows", json={**document["content"], "id": document["id"], "clientRequestId": uid()})
            assert saved.status_code == 201, saved.text
            plan = plan_for(bound)
            plan["inputs"][0].update(mode="fixedRecord", fixedRecord=next(
                row["ref"] for row in before if row["ref"]["recordKey"]["value"] == own
            ))
            configured = client.post(prefix + "/automations", headers=new_key(), json={
                "name": "cross-" + own, "description": "", "workflowId": saved.json()["id"], "inputPlan": plan, "parameterSchema": [],
                "environmentPolicy": {"source": "newFromProfile", "profileId": profile.id, "proxyOverride": {"mode": "none"}, "modelProviderId": None},
                "runPolicy": {"maxTasks": 1, "concurrency": 1, "maxLiveInstances": 1, "continueAfterFailure": False,
                              "automaticExecutionTimeoutSeconds": 60, "manualDeadlineSeconds": 180},
            })
            assert configured.status_code == 201, configured.text
            automation = configured.json()
            validation = client.get(prefix + f"/automations/{automation['automationId']}/validation")
            assert validation.status_code == 200 and validation.json()["runnable"], validation.text
            accepted = client.post(prefix + f"/automations/{automation['automationId']}/batches", headers=new_key(), json={
                "expectedAutomationRevision": automation["managementRevision"], "parameters": {}, "maxTasks": 1, "concurrency": 1,
            })
            assert accepted.status_code == 202, accepted.text
            batches.append(accepted.json()["operation"]["result"]["batch"]["batchId"])

        def waiting(reason):
            response = client.get(prefix + "/manual-items")
            assert response.status_code == 200, response.text
            return [item for item in response.json()["items"] if item["status"] == "waiting" and item["reason"] == reason]

        wait_for(lambda: len(waiting("owner barrier")) == 2, "both real workers own their input before cross writes")
        barriers = waiting("owner barrier")
        snapshots = {item["taskId"]: client.get(prefix + f"/tasks/{item['taskId']}").json()["inputSnapshot"] for item in barriers}
        for snapshot in snapshots.values():
            captured = snapshot["inputs"][0]
            original = next(row for row in before if row["ref"] == captured["recordRef"])
            assert captured["contentRevision"] == original["contentRevision"] == 1
            assert {cell["fieldId"]: cell["value"] for cell in captured["values"]} == {
                cell["fieldId"]: cell["value"] for cell in original["values"]
            }
        owned = bound.records()
        assert [row["contentRevision"] for row in owned] == [2, 2]
        assert {cell["value"] for row in owned for cell in row["values"] if cell["fieldId"] == title} == {"owned-A", "owned-B"}
        assert [row["ref"] for row in owned] == [row["ref"] for row in before]

        def ownership():
            with app.state.session_factory() as session:
                leases = [(row.id, row.task_id, row.record_ref, row.state, row.lease_generation)
                          for row in session.scalars(select(ProjectRecordLeaseRow).order_by(ProjectRecordLeaseRow.id))]
                cursors = [(row.id, row.task_id, row.record_ref, row.content_revision, row.status_revision, row.link_revision)
                           for row in session.scalars(select(ProjectTaskRecordCursorRow).order_by(ProjectTaskRecordCursorRow.id))]
                return leases, cursors

        held = ownership()
        assert len(held[0]) == len(held[1]) == 2
        assert {row[1] for row in held[0]} == set(snapshots) and all(row[3] == "held" for row in held[0])
        pending = sync_operations(bound, "pending")
        assert len(pending) == 2
        assert {item["record"]["recordKey"]["value"] for item in pending} == {"A", "B"}
        assert {item["targetContentRevision"] for item in pending} == {2}
        for item in barriers:
            resume(bound, item)
        # Error branches retain both leases until we explicitly stop; no timing race
        # allows one task to finish and release its record before the other tries it.
        wait_for(lambda: len(waiting("cross conflict")) == 2, "both conflicts reach declared manual branches")
        assert {item["taskId"] for item in waiting("cross conflict")} == set(snapshots)
        assert bound.records() == owned and ownership() == held
        assert sync_operations(bound, "pending") == pending
        for task_id, snapshot in snapshots.items():
            path = prefix + f"/tasks/{task_id}"
            assert client.get(path).json()["inputSnapshot"] == snapshot
            attempts = client.get(path + "/node-attempts").json()["items"]
            cross, = [attempt for attempt in attempts if attempt["nodeId"] == "cross"]
            assert cross["status"] == "failed" and cross["error"]["code"] == "LEASE_BUSY", attempts
            assert sum(attempt["nodeId"] == "own" and attempt["status"] == "succeeded" for attempt in attempts) == 1
        for batch in batches:
            current = batch_detail(bound, batch)["batch"]
            stopped = client.post(prefix + f"/batches/{batch}/stop", headers=new_key(), json={
                "expectedStatusRevision": current["statusRevision"], "reason": "end opposing write observation",
            })
            assert stopped.status_code == 202, stopped.text
        wait_for(lambda: all(batch_detail(bound, batch)["batch"]["status"] == "stopped" for batch in batches), "both owners stop and release")
        assert not waiting("cross conflict")
        assert bound.records() == owned and sync_operations(bound, "pending") == pending
        assert all(row[3] not in {"held", "reconciling"} for row in ownership()[0])
        assert not app.state.project_workflow_worker_manager.busy()
        assert requests.count("/fixture") == 2 and transport.changes() == 0
