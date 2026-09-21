"""Opt-in real HTTP/SQLite/CloakBrowser batch chain; no Studio or synthetic Run facts."""

import asyncio
import shutil
import threading
from datetime import datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.profiles.models import ProfileSpec
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from tests.fixtures.workflows import workflow_payload
from tests.integration.test_workflow_real_cloakbrowser import (
    real_cloak_page as cloak_fixture,
)

real_cloak_page = cloak_fixture


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["success", "stop", "budget", "failure", "data", "data-response-loss", "data-link-race", "data-old-candidate", "manual-resume", "manual-finish", "manual-expire", "manual-expire-race", "manual-stop", "manual-restart", "manual-loss", "manual-double", "manual-race", "manual-race-intent"])
async def test_real_project_batch_http(
    tmp_path, valid_profile_values, real_cloak_page, scenario, monkeypatch
):
    executable, url, requests = real_cloak_page
    source = next(
        parent for parent in executable.parents if parent.name.startswith("chromium-")
    )
    workspace = tmp_path / "pm3-real-batch-workspace"
    await asyncio.to_thread(
        shutil.copytree,
        source,
        workspace / "data" / "kernels" / source.name,
        symlinks=True,
    )
    settings = Settings(
        data_dir=str(workspace),
        instance_id="pm3-batch-real",
        instance_token="isolated-test-token",
    )
    app = create_app(settings)
    lost_command = None
    link_race_injected = False
    race_commands = []
    late_resume = None
    if scenario == 'manual-expire-race':
        repository = app.state.environment_service.environments
        accept, transition = repository.accept_operation, repository.transition_manual
        expired = threading.Event()

        def pending_resume_until_expiry(operation):
            result = accept(operation)
            if operation.kind == 'resumeManual':
                assert expired.wait(8), 'expiry must win while the HTTP command is in flight'
            return result

        def mark_expiry(*args, **kwargs):
            result = transition(*args, **kwargs)
            if result['status'] == 'expired':
                expired.set()
            return result

        monkeypatch.setattr(repository, 'accept_operation', pending_resume_until_expiry)
        monkeypatch.setattr(repository, 'transition_manual', mark_expiry)
    if scenario == 'data-link-race':
        repository = app.state.environment_service.environments
        original_bind = repository.bind_records

        def advance_link_after_preflight(project_id, environment_id, results):
            nonlocal link_race_injected
            if not link_race_injected:
                from autoflow.infrastructure.database.project_data_models import (
                    DataRecordRow,
                )
                ref = results[1].record_ref
                with app.state.session_factory.begin() as session:
                    row = session.get(DataRecordRow, (ref['datasetGeneration'], ref['recordKey']['type'], ref['recordKey']['value']))
                    row.link_revision += 1
                link_race_injected = True
            return original_bind(project_id, environment_id, results)

        monkeypatch.setattr(repository, 'bind_records', advance_link_after_preflight)
    if scenario == 'data-response-loss':
        manager = app.state.project_workflow_worker_manager
        original_send = manager._send

        async def drop_committed_reply(worker, message):
            nonlocal lost_command
            if message.get('type') == 'capability_result' and isinstance(message.get('result'), dict) and 'ref' in message['result']:
                lost_command = message['commandId']
                raise OSError('injected loss after committed create')
            await original_send(worker, message)

        monkeypatch.setattr(manager, '_send', drop_committed_reply)
    if scenario in {'manual-race', 'manual-race-intent'}:
        import autoflow.application.project_runs.manual_runtime as manual_module

        class Clock(datetime):
            shift = timedelta()

            @classmethod
            def now(cls, tz=None):
                return datetime.now(tz) + cls.shift

        runtime = app.state.environment_service.manual_runtime
        original_intent = runtime._intent

        def accept_after_empty_intent_read(identity):
            result = original_intent(identity)
            if result is None and identity not in race_commands:
                Clock.shift = timedelta()
                with runtime.sessions() as session:
                    from autoflow.infrastructure.database.environment_models import (
                        ProjectManualItemRow,
                    )
                    row = session.get(ProjectManualItemRow, identity)
                    project = row.project_id
                item = runtime.environments.get_manual(project, identity)
                runtime.command(project, str(uuid4()), item, {'checkpointRevision': item['checkpointRevision'], 'expectedStatusRevision': item['statusRevision']}, 'resume')
                race_commands.append(identity)
                Clock.shift = timedelta(seconds=31)
            return original_intent(identity) if scenario == 'manual-race-intent' else result

        monkeypatch.setattr(manual_module, 'datetime', Clock)
        monkeypatch.setattr(runtime, '_intent', accept_after_empty_intent_read)
    try:
        # Fixture preparation only. Project, automation and batch are created through real HTTP.
        profile = app.state.profile_service.create(
            ProfileSpec.from_values(
                {
                    **valid_profile_values,
                    "headless": True,
                    "browser_version": source.name.removeprefix("chromium-"),
                }
            )
        )
        parameter_id = str(uuid4())
        document = workflow_payload(str(uuid4()))
        nodes = document["content"]["nodes"]
        nodes[0]["data"]["url"] = url.replace("/fixture", "/login") if scenario.startswith("data") else url
        nodes[1]["data"].update(
            selector="#field", text="{" + parameter_id + "}", clearBefore=False
        )
        nodes[2]["data"]["selector"] = "#button"
        if scenario == "failure":
            nodes[2]["data"].update(selector="#missing-button", timeout=1)
        nodes[3]["data"].update(selector="#button", attribute="data-clicked")
        nodes.append(
            {
                "id": "read-input",
                "type": "get_element_info",
                "position": {"x": 100, "y": 560},
                "data": {
                    "moduleType": "get_element_info",
                    "selector": "#field",
                    "attribute": "value",
                    "variableName": "实际输入",
                },
            }
        )
        document["content"]["edges"].append(
            {"id": "edge-input-read", "source": "read", "target": "read-input"}
        )
        await app.state.project_workflow_dispatcher.startup()
        await app.state.project_run_scheduler.startup()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://test",
            headers={"x-autoflow-token": settings.instance_token},
        ) as client:
            created = await client.post(
                "/api/v1/projects",
                headers={"Idempotency-Key": str(uuid4())},
                json={"name": "真实批次验收", "description": ""},
            )
            assert created.status_code == 201, created.text
            project_id = created.json()["projectId"]
            prefix = f"/api/v1/projects/{project_id}"
            if scenario.startswith("data"):
                table_response = await client.post(prefix + "/tables", headers={"Idempotency-Key": str(uuid4())}, json={"name": "真实写入", "sourceKind": "local"})
                assert table_response.status_code == 201, table_response.text
                table = table_response.json()
                table_path = prefix + f"/tables/{table['tableId']}"
                field_response = await client.post(table_path + "/fields", headers={"Idempotency-Key": str(uuid4())}, json={"definition": {"key": "result", "name": "结果", "type": "string", "required": False, "validation": {}}, "sourceColumnPolicy": "localOnly", "expectedTableRevision": table['tableRevision']})
                assert field_response.status_code == 200, field_response.text
                field_id = field_response.json()['field']['ref']['fieldId']
                nodes.append({'id': 'write', 'type': 'project_data', 'position': {'x': 100, 'y': 680}, 'data': {
                    'moduleType': 'project_data', 'operation': 'createRecord', 'variableName': 'saved',
                    'arguments': {'tableId': table['tableId'], 'datasetGeneration': table['datasetGeneration'], 'values': {field_id: '{实际输入}'}},
                    'tableGrant': {'tableId': table['tableId'], 'datasetGeneration': table['datasetGeneration'], 'operations': ['createRecord'], 'fieldIds': [field_id], 'readPurposes': []},
                }})
                source_table_response = await client.post(prefix + '/tables', headers={'Idempotency-Key': str(uuid4())}, json={'name': '来源数据', 'sourceKind': 'local'})
                source_table = source_table_response.json()
                source_path = prefix + f"/tables/{source_table['tableId']}"
                source_field_response = await client.post(source_path + '/fields', headers={'Idempotency-Key': str(uuid4())}, json={'definition': {'key': 'code', 'name': '代码', 'type': 'string', 'required': False, 'validation': {}}, 'sourceColumnPolicy': 'localOnly', 'expectedTableRevision': source_table['tableRevision']})
                source_field = source_field_response.json()['field']['ref']['fieldId']
                source_record = await client.post(source_path + '/records', headers={'Idempotency-Key': str(uuid4())}, json={'datasetGeneration': source_table['datasetGeneration'], 'values': [{'fieldId': source_field, 'value': '001'}]})
                assert source_record.status_code == 201, source_record.text
                nodes.extend([
                    {'id': 'query', 'type': 'project_data', 'position': {'x': 100, 'y': 700}, 'data': {
                        'moduleType': 'project_data', 'operation': 'queryRecords', 'variableName': 'source_rows',
                        'arguments': {'tableId': source_table['tableId'], 'datasetGeneration': source_table['datasetGeneration'], 'fieldIds': [source_field], 'readPurpose': 'condition', 'filter': None, 'orderBy': [], 'cursor': None, 'limit': 20},
                        'tableGrant': {'tableId': source_table['tableId'], 'datasetGeneration': source_table['datasetGeneration'], 'operations': ['queryRecords'], 'fieldIds': [source_field], 'readPurposes': ['condition']},
                    }},
                    {'id': 'check', 'type': 'condition', 'position': {'x': 100, 'y': 800}, 'data': {'moduleType': 'condition', 'leftValue': "{source_rows['items'][0]['values'][0]['value']}", 'rightValue': '001'}},
                ])
                next(node for node in nodes if node['id'] == 'write')['data']['arguments']['values'][field_id] = "{实际输入}-{source_rows['items'][0]['values'][0]['value']}"
                document['content']['edges'].extend([
                    {'id': 'query-data', 'source': 'read-input', 'target': 'query'},
                    {'id': 'check-data', 'source': 'query', 'target': 'check'},
                    {'id': 'save', 'source': 'check', 'target': 'write', 'sourceHandle': 'true'},
                ])
                nodes.append({'id': 'end', 'type': 'project_end', 'position': {'x': 100, 'y': 900}, 'data': {'moduleType': 'project_end', 'retainEnvironment': {'enabled': True, 'mode': 'saveAs',  'name': "{saved['ref']['recordKey']['value']}", 'recordTargets': [{'recordRef': "{saved['ref']}", 'expectedLinkRevision': "{saved['linkRevision']}", 'replaceAllowed': False}]}}})
                document['content']['edges'].append({'id': 'end-task', 'source': 'write', 'target': 'end'})
                if scenario == 'data-link-race':
                    from copy import deepcopy
                    second = deepcopy(next(node for node in nodes if node['id'] == 'write'))
                    second['id'] = 'second-write'
                    second['data']['variableName'] = 'second_saved'
                    nodes.append(second)
                    document['content']['edges'][-1]['target'] = 'second-write'
                    document['content']['edges'].append({'id': 'second-end', 'source': 'second-write', 'target': 'end'})
                    next(node for node in nodes if node['id'] == 'end')['data']['retainEnvironment']['recordTargets'].append({'recordRef': "{second_saved['ref']}", 'expectedLinkRevision': "{second_saved['linkRevision']}", 'replaceAllowed': False})
            if scenario.startswith('manual-'):
                nodes.append({'id': 'manual', 'type': 'project_manual', 'position': {'x': 100, 'y': 900}, 'data': {'moduleType': 'project_manual', 'reason': '确认登录', 'timeoutSeconds': .3 if scenario == 'manual-expire' else 3 if scenario == 'manual-expire-race' else 30}})
                document['content']['edges'].append({'id': 'manual-task', 'source': 'read-input', 'target': 'manual'})
                nodes.append({'id': 'after-manual', 'type': 'set_variable', 'position': {'x': 100, 'y': 950}, 'data': {'moduleType': 'set_variable', 'variableName': 'continued', 'variableValue': 'once'}})
                document['content']['edges'].append({'id': 'continue-task', 'source': 'manual', 'target': 'after-manual'})
                if scenario == 'manual-double':
                    nodes.append({'id': 'second-manual', 'type': 'project_manual', 'position': {'x': 100, 'y': 1000}, 'data': {'moduleType': 'project_manual', 'reason': '第二次确认', 'timeoutSeconds': 30}})
                    document['content']['edges'].append({'id': 'second-checkpoint', 'source': 'after-manual', 'target': 'second-manual'})
            saved_workflow = await client.post('/api/workflows', json={**document['content'], 'id': document['id'], 'clientRequestId': str(uuid4())})
            assert saved_workflow.status_code == 201, saved_workflow.text
            workflow_id = saved_workflow.json()['id']
            response = await client.post(
                prefix + "/automations",
                headers={"Idempotency-Key": str(uuid4())},
                json={
                    "name": "真实浏览器批次",
                    "description": "",
                    "workflowId": workflow_id,
                    "inputPlan": {"inputs": []},
                    "parameterSchema": [
                        {
                            "parameterId": parameter_id,
                            "name": "追加文本",
                            "type": "string",
                            "required": True,
                        }
                    ],
                    "environmentPolicy": {
                        "source": "newFromProfile",
                        "profileId": profile.id,
                        "proxyOverride": {"mode": "none"},
                        "modelProviderId": None,
                    },
                    "runPolicy": {
                        "maxTasks": 2,
                        "concurrency": 1,
                        "maxLiveInstances": 1,
                        "continueAfterFailure": False,
                        "automaticExecutionTimeoutSeconds": 0.1
                        if scenario == "budget"
                        else 60,
                        "manualDeadlineSeconds": 300,
                    },
                },
            )
            assert response.status_code == 201, response.text
            automation = response.json()
            validation = await client.get(prefix + f"/automations/{automation['automationId']}/validation")
            assert validation.status_code == 200, validation.text
            assert validation.json()["runnable"] is True, validation.json()
            key = str(uuid4())
            payload = {
                "expectedAutomationRevision": automation["managementRevision"],
                "parameters": {parameter_id: "-真实参数"},
                "maxTasks": 2,
                "concurrency": 1,
            }
            response = await client.post(
                prefix + f"/automations/{automation['automationId']}/batches",
                headers={"Idempotency-Key": key},
                json=payload,
            )
            assert response.status_code == 202, response.text
            accepted = response.json()["operation"]
            batch_id = accepted["result"]["batch"]["batchId"]
            found_operation = await client.get(prefix+f"/operations/by-idempotency-key/{key}")
            assert found_operation.status_code == 200, found_operation.text
            assert found_operation.json()["operationId"] == accepted["operationId"]
            handled_manual = set()
            manual_receipts = {}
            replayed_manual = set()
            manual_interrupted = False
            for _ in range(300):
                if scenario == 'manual-expire-race' and late_resume is None:
                    manual = (await client.get(prefix + '/manual-items')).json()['items']
                    waiting = next((item for item in manual if item['status'] == 'waiting'), None)
                    if waiting:
                        late_resume = asyncio.create_task(client.post(prefix + f"/manual-items/{waiting['manualItemId']}/resume", headers={'Idempotency-Key': str(uuid4())}, json={'checkpointRevision': waiting['checkpointRevision'], 'expectedStatusRevision': waiting['statusRevision']}))
                if scenario in {'manual-resume', 'manual-finish', 'manual-double'}:
                    manual = await client.get(prefix + '/manual-items')
                    assert manual.status_code == 200, manual.text
                    for item in manual.json()['items']:
                        if item['status'] != 'waiting' or item['manualItemId'] in handled_manual:
                            continue
                        manual_id = item['manualItemId']
                        if scenario in {'manual-resume', 'manual-double'}:
                            body = {'checkpointRevision': item['checkpointRevision'], 'expectedStatusRevision': item['statusRevision']}
                            action = 'resume'
                        else:
                            body = {'expectedCheckpointRevision': item['checkpointRevision'], 'expectedStatusRevision': item['statusRevision'], 'outcome': 'succeeded', 'reason': '已核验', 'retainEnvironment': {'enabled': False}}
                            action = 'finish'
                        manual_key = str(uuid4())
                        if scenario == 'manual-double' and item['runId'] in manual_receipts:
                            previous_id, previous_key, previous_body, operation_id = manual_receipts[item['runId']]
                            replay = await client.post(prefix + f'/manual-items/{previous_id}/resume', headers={'Idempotency-Key': previous_key}, json=previous_body)
                            assert replay.status_code == 202, replay.text
                            assert replay.json()['operation']['operationId'] == operation_id
                            replayed_manual.add(previous_id)
                        command = await client.post(prefix + f'/manual-items/{manual_id}/{action}', headers={'Idempotency-Key': manual_key}, json=body)
                        assert command.status_code == 202, command.text
                        handled_manual.add(manual_id)
                        manual_receipts[item['runId']] = (manual_id, manual_key, body, command.json()['operation']['operationId'])

                if scenario in {'manual-stop', 'manual-restart', 'manual-loss'} and not manual_interrupted:
                    items = (await client.get(prefix + '/manual-items')).json()['items']
                    waiting = next((item for item in items if item['status'] == 'waiting'), None)
                    if waiting:
                        manual_interrupted = True
                        if scenario == 'manual-loss':
                            app.state.project_workflow_worker_manager._worker.process.kill()
                        elif scenario == 'manual-restart':
                            await app.router.on_shutdown[-1]()
                            app = create_app(settings)
                            await app.state.project_workflow_dispatcher.startup()
                            await app.state.project_run_scheduler.startup()
                            await client.aclose()
                            client = httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test', headers={'x-autoflow-token': settings.instance_token})
                            rejected = await client.post(prefix + f"/manual-items/{waiting['manualItemId']}/resume", headers={'Idempotency-Key': str(uuid4())}, json={'checkpointRevision': waiting['checkpointRevision'], 'expectedStatusRevision': waiting['statusRevision']})
                            assert rejected.status_code == 409, rejected.text
                        else:
                            current = (await client.get(prefix + f'/batches/{batch_id}')).json()
                            stopped = await client.post(prefix + f'/batches/{batch_id}/stop', headers={'Idempotency-Key': str(uuid4())}, json={'expectedStatusRevision': current['batch']['statusRevision'], 'reason': '人工等待时停止'})
                            assert stopped.status_code == 202, stopped.text
                response = await client.get(prefix + f"/batches/{batch_id}")
                assert response.status_code == 200, response.text
                detail = response.json()
                if scenario == "stop" and detail["batch"]["status"] == "running":
                    stopped = await client.post(
                        prefix + f"/batches/{batch_id}/stop",
                        headers={"Idempotency-Key": str(uuid4())},
                        json={
                            "expectedStatusRevision": detail["batch"]["statusRevision"],
                            "reason": "真实浏览器停止验收",
                        },
                    )
                    assert stopped.status_code == 202, stopped.text
                    scenario_stopped = True
                if detail["batch"]["status"] in {
                    "completed",
                    "failed",
                    "stopped",
                    "interrupted",
                }:
                    break
                await asyncio.sleep(0.2)
            else:
                pytest.fail(f"Batch did not complete: {detail}")
            tasks = (
                await client.get(prefix + "/tasks", params={"batchId": batch_id})
            ).json()["items"]
            assert len(tasks) == 2
            for task in tasks:
                viewed = await client.get(prefix + f"/tasks/{task['taskId']}")
                assert viewed.status_code == 200, viewed.text
                assert viewed.json()["inputSnapshot"]["parameters"] == {
                    parameter_id: "-真实参数"
                }
                assert (
                    "frozenConfiguration" not in viewed.json()["run"]["resourceRequest"]
                )
            replay = await client.post(
                prefix + f"/automations/{automation['automationId']}/batches",
                headers={"Idempotency-Key": key},
                json=payload,
            )
            assert replay.status_code == 202 and replay.json()["operation"] == accepted
            if scenario == "success":
                assert detail["statusCounts"]["succeeded"] == 2 and requests, {
                    "batch": detail,
                    "tasks": [(await client.get(prefix + f"/tasks/{task['taskId']}")).json() for task in tasks],
                }
                for task in tasks:
                    task_path = prefix+f"/tasks/{task['taskId']}"
                    logs = await client.get(task_path+"/logs")
                    attempts = await client.get(task_path+"/node-attempts")
                    outputs = await client.get(task_path+"/outputs")
                    assert logs.status_code == attempts.status_code == outputs.status_code == 200
                    assert len(logs.json()["items"]) == 10
                    assert attempts.json()["total"] == 5
                    assert {item["status"] for item in attempts.json()["items"]} == {"succeeded"}
                    assert [item["value"] for item in outputs.json()["items"]] == ["yes", "before-真实参数"]
                    with app.state.session_factory() as session:
                        events = SqlAlchemyWorkflowRuntimeRepository(
                            session
                        ).list_events(task["runId"], after_sequence=0, limit=200)
                    assert [
                        event.payload["value"]
                        for event in events
                        if event.kind == "output"
                    ] == ["yes", "before-真实参数"]
                    assert [event.sequence for event in events] == list(
                        range(1, len(events) + 1)
                    )
            elif scenario.startswith('manual-'):
                if scenario in {'manual-race', 'manual-race-intent'}:
                    assert detail['statusCounts']['succeeded'] == 2, detail
                    assert len(race_commands) == 2
                    for task in tasks:
                        attempts = (await client.get(prefix + f"/tasks/{task['taskId']}/node-attempts")).json()['items']
                        assert sum(attempt['nodeId'] == 'after-manual' for attempt in attempts) == 1
                elif scenario in {'manual-stop', 'manual-restart', 'manual-loss'}:
                    assert manual_interrupted
                    assert detail['statusCounts']['interrupted' if scenario in {'manual-restart', 'manual-loss'} else 'cancelled'] >= 1, detail
                    manual_items = (await client.get(prefix + '/manual-items')).json()['items']
                    assert all(item['status'] == 'cancelled' for item in manual_items)
                elif scenario not in {'manual-expire', 'manual-expire-race'}:
                    assert detail['statusCounts']['succeeded'] == 2, detail
                    assert len(handled_manual) == (4 if scenario == 'manual-double' else 2)
                    if scenario == 'manual-double':
                        assert len(replayed_manual) == 2
                    for task in tasks:
                        attempts = (await client.get(prefix + f"/tasks/{task['taskId']}/node-attempts")).json()['items']
                        assert len([a for a in attempts if a['nodeId'] == 'read-input']) == 1
                        assert any(a['nodeId'] == 'after-manual' for a in attempts) == (scenario in {'manual-resume', 'manual-double'})
                else:
                    assert detail['statusCounts']['timed_out'] == 1, detail
                    if scenario == 'manual-expire-race':
                        assert late_resume is not None
                        rejected = await late_resume
                        assert rejected.status_code == 409, rejected.text
                        assert rejected.json()['error']['code'] == 'MANUAL_TRANSITION_LOST'
                        items = (await client.get(prefix + '/manual-items')).json()['items']
                        assert len(items) == 1 and items[0]['status'] == 'expired'
            elif scenario == 'data-link-race':
                assert link_race_injected
                assert detail['statusCounts']['failed'] == 1, detail
                failed = next(task for task in tasks if task['status'] == 'failed')
                rows = (await client.get(table_path + '/records', params={'datasetGeneration': table['datasetGeneration']})).json()['items']
                assert len(rows) == 2
                assert all(row['currentEnvironmentId'] is None for row in rows), 'the complete association group must roll back'
                assert sorted(row['linkRevision'] for row in rows) == [1, 2]
                operations = (await client.get(prefix + '/operations', params={'pageSize': 200})).json()['items']
                saved = next(operation for operation in operations if operation['idempotencyKey'].startswith('end-save:'))
                assert saved['result']['phase'] == 'saved_unlinked'
                assert saved['result']['conflicts'][0]['currentLinkRevision'] == 2
                environments = (await client.get(prefix + '/environments')).json()
                assert environments['total'] == 1
                attempts_path = prefix + f"/tasks/{failed['taskId']}/node-attempts"
                attempts = (await client.get(attempts_path)).json()
                repaired = await client.post(prefix + f"/environment-operations/{saved['operationId']}/repair", headers={'Idempotency-Key': str(uuid4())}, json={'recordTargets': [{'recordRef': row['ref'], 'expectedLinkRevision': row['linkRevision'], 'replaceAllowed': False} for row in rows]})
                assert repaired.status_code == 202, repaired.text
                assert repaired.json()['outcome']['phase'] == 'completed'
                after_repair = (await client.get(prefix + '/environments')).json()
                assert after_repair['total'] == 1
                assert after_repair['items'][0]['ref'] == environments['items'][0]['ref']
                linked = (await client.get(table_path + '/records', params={'datasetGeneration': table['datasetGeneration']})).json()['items']
                assert {row['currentEnvironmentId'] for row in linked} == {saved['result']['saved']['environmentId']}
                assert (await client.get(attempts_path)).json() == attempts
                assert (await client.get(prefix + f"/tasks/{failed['taskId']}")).json()['run']['status'] == 'failed'
            elif scenario == 'data-response-loss':
                assert lost_command is not None
                assert detail['statusCounts']['interrupted'] == 1, detail
                operation = await client.get(prefix + f'/operations/by-idempotency-key/{lost_command}')
                assert operation.status_code == 200, operation.text
                assert operation.json()['status'] == 'succeeded'
                original = operation.json()
                assert (await client.get(prefix + f'/operations/by-idempotency-key/{lost_command}')).json() == original
                rows = (await client.get(table_path + '/records', params={'datasetGeneration': table['datasetGeneration']})).json()
                assert rows['total'] == 1
                assert rows['items'][0]['ref'] == original['result']['ref']
                assert rows['items'][0]['values'][0]['value'] == 'before-真实参数-001'
            elif scenario in {"data", "data-old-candidate"}:
                assert detail['statusCounts']['succeeded'] == 2, {
                    'batch': detail,
                    'tasks': [(await client.get(prefix + f"/tasks/{task['taskId']}")).json() for task in tasks],
                    'attempts': [(await client.get(prefix + f"/tasks/{task['taskId']}/node-attempts")).json() for task in tasks],
                }
                records = (await client.get(table_path + '/records', params={'datasetGeneration': table['datasetGeneration']})).json()
                assert records['total'] == 2
                assert [row['values'][0]['value'] for row in records['items']] == ['before-真实参数-001'] * 2
                assert all(row['currentEnvironmentId'] for row in records['items'])
                restored_document = workflow_payload(str(uuid4()))
                restored_document['content']['nodes'] = [
                    {'id': 'open', 'type': 'open_page', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'open_page', 'url': url.replace('/fixture', '/account')}},
                    {'id': 'read', 'type': 'get_element_info', 'position': {'x': 0, 'y': 100}, 'data': {'moduleType': 'get_element_info', 'selector': '#auth', 'attribute': 'text', 'variableName': 'login'}},
                    {'id': 'end', 'type': 'project_end', 'position': {'x': 0, 'y': 200}, 'data': {'moduleType': 'project_end', 'retainEnvironment': {'enabled': False}}},
                ]
                restored_document['content']['edges'] = [{'id': 'read', 'source': 'open', 'target': 'read'}, {'id': 'end', 'source': 'read', 'target': 'end'}]
                saved_restore = await client.post('/api/workflows', json={**restored_document['content'], 'id': restored_document['id'], 'clientRequestId': str(uuid4())})
                assert saved_restore.status_code == 201, saved_restore.text
                restored_workflow_id = saved_restore.json()['id']
                restore_config = {name: automation[name] for name in ['description', 'inputPlan', 'runPolicy']}
                restore_config.update(name='复用已登录环境', workflowId=restored_workflow_id, parameterSchema=[], environmentPolicy={'source': 'fixedEnvironment', 'environmentId': records['items'][0]['currentEnvironmentId'], 'proxyOverride': {'mode': 'none'}, 'modelProviderId': None})
                restored = await client.post(prefix + '/automations', headers={'Idempotency-Key': str(uuid4())}, json=restore_config)
                assert restored.status_code == 201, restored.text
                restored = restored.json()
                started = await client.post(prefix + f"/automations/{restored['automationId']}/batches", headers={'Idempotency-Key': str(uuid4())}, json={'expectedAutomationRevision': restored['managementRevision'], 'parameters': {}, 'maxTasks': 1, 'concurrency': 1})
                assert started.status_code == 202, started.text
                restore_batch = started.json()['operation']['result']['batch']['batchId']
                for _ in range(200):
                    state = (await client.get(prefix + f'/batches/{restore_batch}')).json()
                    if state['batch']['status'] in {'completed', 'failed', 'interrupted'}:
                        break
                    await asyncio.sleep(.1)
                assert state['statusCounts']['succeeded'] == 1, state
                restored_tasks = (await client.get(prefix + '/tasks', params={'batchId': restore_batch})).json()['items']
                outputs = (await client.get(prefix + f"/tasks/{restored_tasks[0]['taskId']}/outputs")).json()['items']
                assert [output['value'] for output in outputs] == ['signed-in']

                if scenario == 'data-old-candidate':
                    # Only publication gets an injected disk fault: preparation,
                    # browser, staging, successor Run and recovery use production.
                    service = app.state.environment_service
                    publish = service.store.publish
                    failed_save = None

                    def fail_first_publish(environment_id, generation, save_id):
                        nonlocal failed_save
                        if failed_save is None:
                            import errno
                            failed_save = save_id
                            assert (service.store.root / 'candidates' / save_id).is_dir()
                            raise OSError(errno.ENOSPC, 'injected disk publication failure')
                        return publish(environment_id, generation, save_id)

                    update_content = restored_document['content']
                    update_content['nodes'][-1]['data']['retainEnvironment'] = {'enabled': True, 'mode': 'update', 'expectedContentGeneration': 1}
                    update_workflow = await client.post('/api/workflows', json={**update_content, 'id': str(uuid4()), 'clientRequestId': str(uuid4())})
                    assert update_workflow.status_code == 201, update_workflow.text
                    update_config = {**restore_config, 'name': '旧候选发布竞争', 'workflowId': update_workflow.json()['id']}
                    update_automation = await client.post(prefix + '/automations', headers={'Idempotency-Key': str(uuid4())}, json=update_config)
                    assert update_automation.status_code == 201, update_automation.text
                    update_automation = update_automation.json()

                    async def run_update(expected):
                        accepted = await client.post(prefix + f"/automations/{update_automation['automationId']}/batches", headers={'Idempotency-Key': str(uuid4())}, json={'expectedAutomationRevision': update_automation['managementRevision'], 'parameters': {}, 'maxTasks': 1, 'concurrency': 1})
                        assert accepted.status_code == 202, accepted.text
                        identity = accepted.json()['operation']['result']['batch']['batchId']
                        for _ in range(300):
                            batch = (await client.get(prefix + f'/batches/{identity}')).json()
                            if batch['batch']['status'] in {'completed', 'failed', 'interrupted'}:
                                break
                            await asyncio.sleep(.1)
                        assert batch['statusCounts'][expected] == 1, batch
                        return (await client.get(prefix + '/tasks', params={'batchId': identity})).json()['items'][0]

                    monkeypatch.setattr(service.store, 'publish', fail_first_publish)
                    t1 = await run_update('failed')
                    assert failed_save is not None
                    instance = (await client.get(prefix + '/environment-instances', params={'taskId': t1['taskId']})).json()['items'][0]
                    assert instance['state'] == 'retained_unsaved'
                    candidate = service.store.root / 'candidates' / failed_save
                    assert candidate.is_dir()
                    assert (service.store.root / 'instances' / instance['instanceId']).is_dir()
                    await run_update('succeeded')
                    environment_id = records['items'][0]['currentEnvironmentId']
                    published = (await client.get(prefix + f'/environments/{environment_id}')).json()['environment']
                    assert published['ref']['contentGeneration'] == 2
                    attempts_path = prefix + f"/tasks/{t1['taskId']}/node-attempts"
                    attempts_before = (await client.get(attempts_path)).json()
                    current_run = (await client.get(prefix + f"/tasks/{t1['taskId']}")).json()['run']
                    body = {'taskId': t1['taskId'], 'runId': t1['runId'], 'instanceId': instance['instanceId'], 'expectedUseGeneration': instance['instanceUseGeneration'], 'executionGeneration': current_run['executionGeneration'], 'retainEnvironment': {'enabled': True, 'mode': 'update', 'expectedContentGeneration': 1}}
                    rejected = await client.post(prefix + f"/tasks/{t1['taskId']}/end", headers={'Idempotency-Key': str(uuid4())}, json=body)
                    assert rejected.status_code == 409, rejected.text
                    assert rejected.json()['error']['code'] == 'SAVE_GENERATION_CONFLICT'
                    assert (await client.get(prefix + f'/environments/{environment_id}')).json()['environment'] == published
                    assert candidate.is_dir()
                    body['retainEnvironment'] = {'enabled': True, 'mode': 'saveAs', 'name': '保留 T1 旧候选'}
                    saved_as = await client.post(prefix + f"/tasks/{t1['taskId']}/end", headers={'Idempotency-Key': str(uuid4())}, json=body)
                    assert saved_as.status_code == 202, saved_as.text
                    alternate = saved_as.json()['outcome']['saved']
                    assert alternate['environmentId'] != environment_id
                    assert alternate['contentGeneration'] == 1
                    assert (await client.get(prefix + f'/environments/{environment_id}')).json()['environment'] == published
                    assert (await client.get(attempts_path)).json() == attempts_before
                    assert (await client.get(prefix + f"/tasks/{t1['taskId']}")).json()['run']['status'] == 'failed'

            elif scenario == "stop":
                assert scenario_stopped and detail["batch"]["status"] == "stopped"
                assert detail["statusCounts"]["cancelled"] == 2
            elif scenario == "budget":
                assert detail["statusCounts"]["timed_out"] == 1
                assert detail["statusCounts"]["cancelled"] == 1
            else:
                assert detail["statusCounts"]["failed"] == 1
                assert detail["statusCounts"]["cancelled"] == 1
                failed_task = next(task for task in tasks if task["status"] == "failed")
                artifact_path = prefix + f"/tasks/{failed_task['taskId']}/artifacts"
                artifacts = await client.get(artifact_path)
                assert artifacts.status_code == 200, artifacts.text
                assert artifacts.json()["total"] == 1
                artifact = artifacts.json()["items"][0]
                assert artifact["availability"] == "available"
                screenshot = await client.get(artifact_path + f"/{artifact['artifactId']}/content")
                assert screenshot.status_code == 200
                assert screenshot.headers["content-type"] == "image/png"
                assert screenshot.content.startswith(b"\x89PNG\r\n\x1a\n")
            await client.aclose()
            assert not app.state.project_workflow_worker_manager.busy()
            assert app.state.project_workflow_dispatcher.blockers() == []
            assert app.state.project_run_scheduler.blockers() == []
            assert (workspace / "tmp").is_dir()
            assert not list((workspace / "tmp").glob("**/generation-*"))
    finally:
        await app.router.on_shutdown[-1]()
