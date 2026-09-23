"""Opt-in real HTTP/SQLite/CloakBrowser batch chain; no Studio or synthetic Run facts."""

import asyncio
import hashlib
import json
import shutil
import socket
import threading
from datetime import datetime, timedelta
from uuid import uuid4

import httpx
import pytest
import uvicorn

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
async def test_optional_input_does_not_leak_between_real_tasks(
    tmp_path, valid_profile_values, real_cloak_page,
):
    from sqlalchemy import select

    from autoflow.domain.project_data.identity import RecordKey, encode_record_key
    from autoflow.infrastructure.database.project_run_models import (
        ProjectRecordLeaseRow,
    )
    from tests.integration.test_project_run_data_start import _input, _table

    executable, url, requests = real_cloak_page
    source = next(parent for parent in executable.parents if parent.name.startswith('chromium-'))
    await asyncio.to_thread(shutil.copytree, source, tmp_path / 'data' / 'kernels' / source.name, symlinks=True)
    app = create_app(Settings(data_dir=str(tmp_path), instance_id='optional-input-real', instance_token='isolated-test-token'))
    try:
        profile = app.state.profile_service.create(ProfileSpec.from_values({
            **valid_profile_values, 'headless': True, 'browser_version': source.name.removeprefix('chromium-'),
        }))
        await app.state.project_workflow_dispatcher.startup()
        await app.state.project_run_scheduler.startup()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers={'x-autoflow-token': 'isolated-test-token'}) as client:
            created = await client.post('/api/v1/projects', headers={'Idempotency-Key': str(uuid4())}, json={'name': '可选输入隔离'})
            assert created.status_code == 201, created.text
            project_id = created.json()['projectId']
            prefix = f'/api/v1/projects/{project_id}'
            # Existing service fixture creates a real local table/record, no Run or lease facts.
            table, field = _table(app.state.session_factory, project_id, '可选来源', 'first-only')
            definition = _input(project_id, table, field, '可选输入')
            definition.update(required=False, filter={'type': 'compare', 'fieldId': field['ref']['fieldId'], 'operator': 'eq', 'value': 'first-only'})
            document = workflow_payload(str(uuid4()))
            document['content']['nodes'] = [
                {'id': 'inputs', 'type': 'project_data', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'project_data', 'operation': 'inputs', 'variableName': 'frozen', 'arguments': {}}},
                {'id': 'open', 'type': 'open_page', 'position': {'x': 0, 'y': 100}, 'data': {'moduleType': 'open_page', 'url': url, 'timeout': 30}},
                {'id': 'read', 'type': 'project_data', 'position': {'x': 0, 'y': 200}, 'data': {'moduleType': 'project_data', 'operation': 'inputs', 'variableName': 'observed', 'arguments': {}}},
            ]
            document['content']['edges'] = [
                {'id': 'inputs-open', 'source': 'inputs', 'target': 'open'},
                {'id': 'open-read', 'source': 'open', 'target': 'read'},
            ]
            saved = await client.post('/api/workflows', json={**document['content'], 'id': document['id'], 'clientRequestId': str(uuid4())})
            assert saved.status_code == 201, saved.text
            configured = await client.post(prefix + '/automations', headers={'Idempotency-Key': str(uuid4())}, json={
                'name': '同一可选输入连续运行', 'description': '', 'workflowId': saved.json()['id'],
                'inputPlan': {'inputs': [definition]}, 'parameterSchema': [],
                'environmentPolicy': {'source': 'newFromProfile', 'profileId': profile.id, 'proxyOverride': {'mode': 'none'}, 'modelProviderId': None},
                'runPolicy': {'maxTasks': 1, 'concurrency': 1, 'maxLiveInstances': 1, 'continueAfterFailure': False, 'automaticExecutionTimeoutSeconds': 60, 'manualDeadlineSeconds': 120},
            })
            assert configured.status_code == 201, configured.text
            automation = configured.json()
            observed_tasks = []
            for present in (True, False):
                accepted = await client.post(prefix + f"/automations/{automation['automationId']}/batches", headers={'Idempotency-Key': str(uuid4())}, json={
                    'expectedAutomationRevision': automation['managementRevision'], 'parameters': {}, 'maxTasks': 1, 'concurrency': 1,
                })
                assert accepted.status_code == 202, accepted.text
                batch_id = accepted.json()['operation']['result']['batch']['batchId']
                for _ in range(300):
                    detail = (await client.get(prefix + f'/batches/{batch_id}')).json()
                    if detail['batch']['status'] == 'completed':
                        break
                    await asyncio.sleep(.1)
                assert detail['statusCounts']['succeeded'] == 1, detail
                listed = await client.get(prefix + '/tasks', params={'batchId': batch_id})
                assert listed.status_code == 200, listed.text
                tasks = listed.json()['items']
                assert len(tasks) == 1
                task = tasks[0]
                observed_tasks.append(task)
                task_path = prefix + f"/tasks/{task['taskId']}"
                snapshot = (await client.get(task_path)).json()['inputSnapshot']['inputs'][0]
                outputs = (await client.get(task_path + '/outputs')).json()['items']
                expected_values = [{'fieldId': field['ref']['fieldId'], 'fieldName': '值', 'value': 'first-only'}] if present else []
                assert snapshot['values'] == expected_values
                assert len(outputs) == 2
                assert all(output['value'][0]['values'] == expected_values for output in outputs), outputs
                assert all(output['value'][0]['recordRef'] == snapshot['recordRef'] for output in outputs)
                attempts = (await client.get(task_path + '/node-attempts')).json()['items']
                assert len(attempts) == 3 and all(attempt['status'] == 'succeeded' for attempt in attempts)
                with app.state.session_factory() as session:
                    leases = session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.task_id == task['taskId'])).all()
                    assert len(leases) == int(present)
                    assert all(lease.state == 'released' for lease in leases)
                if present:
                    first_snapshot = snapshot
                    assert snapshot['recordRef'] is not None
                    encoded = encode_record_key(RecordKey(**snapshot['recordRef']['recordKey']))
                    changed = await client.patch(prefix + f"/tables/{table['tableId']}/records/{encoded}", headers={'Idempotency-Key': str(uuid4())}, json={
                        'datasetGeneration': table['datasetGeneration'], 'recordKeyType': 'uuid', 'expectedContentRevision': 1,
                        'values': [{'fieldId': field['ref']['fieldId'], 'value': 'no-longer-matches'}],
                    })
                    assert changed.status_code == 200, changed.text
                    assert changed.json()['contentRevision'] == 2
                else:
                    assert snapshot['recordRef'] is None and snapshot['unavailableReason'] == 'no_match'
            assert len({task['taskId'] for task in observed_tasks}) == len({task['runId'] for task in observed_tasks}) == 2
            assert (await client.get(prefix + f"/tasks/{observed_tasks[0]['taskId']}")).json()['inputSnapshot']['inputs'][0] == first_snapshot
            assert requests.count('/fixture') == 2
            assert not app.state.project_workflow_worker_manager.busy()
            assert app.state.project_workflow_dispatcher.blockers() == []
            assert app.state.project_run_scheduler.blockers() == []
            assert not list((tmp_path / 'tmp').glob('**/generation-*'))
    finally:
        await app.router.on_shutdown[-1]()


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["success", "parameter-single", "parameter-isolation", "stop", "budget", "failure", "data", "data-schema", "data-delete-field", "data-delete-field-conflict", "data-response-loss", "data-subflow", "data-subflow-cancel", "data-loop-partial", "data-parallel", "data-parallel-failure", "data-link-race", "data-link-forged-end", "data-old-candidate", "manual-resume", "manual-evidence-reconnect", "manual-declared", "manual-parallel", "manual-parallel-finish", "manual-parallel-stop", "manual-finish", "manual-expire", "manual-expire-race", "manual-stop", "manual-force-stop", "manual-restart", "manual-loss", "manual-double", "manual-race", "manual-race-intent"])
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
    event_server = event_server_task = event_socket = None
    lost_command = None
    end_requests = []
    link_race_injected = False
    race_commands = []
    late_resume = None
    subflow_source_edited = False
    cancelled_child_writes = []
    force_worker = None
    force_receipt = None
    dropped_stops = []
    if scenario == 'manual-force-stop':
        manager = app.state.project_workflow_worker_manager
        original_send = manager._send

        async def drop_messages_after_stop(worker, message):
            # Simulate a broken parent-to-worker channel only after stop admission.
            # Dropping only `stop` is insufficient: manual cancellation also replies.
            if worker.stop_requested:
                dropped_stops.append((worker.run_id, message['type']))
                return
            await original_send(worker, message)
        monkeypatch.setattr(manager, '_send', drop_messages_after_stop)
    if scenario == 'data-link-forged-end':
        manager = app.state.project_workflow_worker_manager
        original_capability = manager._on_capability

        async def observe_end_request(run_id, generation, request):
            if request.get('operation') == 'end':
                end_requests.append(request)
            return await original_capability(run_id, generation, request)

        monkeypatch.setattr(manager, '_on_capability', observe_end_request)
    if scenario == 'manual-expire-race':
        repository = app.state.environment_service.environments
        accept, transition = repository.accept_operation, repository.transition_manual
        expired = threading.Event()

        def pending_resume_until_expiry(operation, **kwargs):
            result = accept(operation, **kwargs)
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
        parameter_value = "first" if scenario == "parameter-single" else "-真实参数"
        document = workflow_payload(str(uuid4()))
        nodes = document["content"]["nodes"]
        nodes[0]["data"]["url"] = url.replace("/fixture", "/login") if scenario.startswith("data") else url
        nodes[1]["data"].update(
            selector="#field", text="{" + parameter_id + "}", clearBefore=scenario == "parameter-single"
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
        if scenario == 'parameter-isolation':
            nodes.extend([
                {'id': 'prior-local', 'type': 'set_variable', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'set_variable', 'variableName': 'priorLocal', 'variableValue': '{taskLocal}'}},
                {'id': 'write-local', 'type': 'set_variable', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'set_variable', 'variableName': 'taskLocal', 'variableValue': 'must-not-leak'}},
            ])
            document['content']['edges'].extend([
                {'id': 'inspect-local', 'source': 'read-input', 'target': 'prior-local'},
                {'id': 'set-local', 'source': 'prior-local', 'target': 'write-local'},
            ])
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
            if scenario == 'parameter-isolation':
                result_table_response = await client.post(prefix + '/tables', headers={'Idempotency-Key': str(uuid4())}, json={'name': '同名结果列', 'sourceKind': 'local'})
                assert result_table_response.status_code == 201, result_table_response.text
                result_table = result_table_response.json()
                result_path = prefix + f"/tables/{result_table['tableId']}"
                result_field_response = await client.post(result_path + '/fields', headers={'Idempotency-Key': str(uuid4())}, json={'definition': {'key': '实际输入', 'name': '实际输入', 'type': 'string', 'required': False, 'validation': {}}, 'sourceColumnPolicy': 'localOnly', 'expectedTableRevision': 1})
                assert result_field_response.status_code == 200, result_field_response.text
                result_field = result_field_response.json()['field']['ref']['fieldId']
                original_response = await client.post(result_path + '/records', headers={'Idempotency-Key': str(uuid4())}, json={'datasetGeneration': result_table['datasetGeneration'], 'values': [{'fieldId': result_field, 'value': 'original'}]})
                assert original_response.status_code == 201, original_response.text
                original_result_rows = (await client.get(result_path + '/records', params={'datasetGeneration': result_table['datasetGeneration']})).json()['items']
            if scenario.startswith("data"):
                table_response = await client.post(prefix + "/tables", headers={"Idempotency-Key": str(uuid4())}, json={"name": "真实写入", "sourceKind": "local"})
                assert table_response.status_code == 201, table_response.text
                table = table_response.json()
                table_path = prefix + f"/tables/{table['tableId']}"
                field_response = await client.post(table_path + "/fields", headers={"Idempotency-Key": str(uuid4())}, json={"definition": {"key": "result", "name": "结果", "type": "string", "required": False, "validation": {"pattern": "^row-[01]$"} if scenario == 'data-loop-partial' else {}}, "sourceColumnPolicy": "localOnly", "expectedTableRevision": table['tableRevision']})
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
                if scenario.startswith('data-delete-field'):
                    old_field = await client.post(source_path + '/fields', headers={'Idempotency-Key': str(uuid4())}, json={'definition': {'key': 'obsolete', 'name': '旧字段', 'type': 'string', 'required': False, 'validation': {}}, 'sourceColumnPolicy': 'localOnly', 'expectedTableRevision': 2})
                    assert old_field.status_code == 200, old_field.text
                    removed_field = old_field.json()['field']['ref']['fieldId']
                source_record = await client.post(source_path + '/records', headers={'Idempotency-Key': str(uuid4())}, json={'datasetGeneration': source_table['datasetGeneration'], 'values': [{'fieldId': source_field, 'value': '001'}, *([{'fieldId': removed_field, 'value': 'obsolete'}] if scenario.startswith('data-delete-field') else [])]})
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
                if scenario in {'data-link-race', 'data-link-forged-end'}:
                    from copy import deepcopy
                    second = deepcopy(next(node for node in nodes if node['id'] == 'write'))
                    second['id'] = 'second-write'
                    second['data']['variableName'] = 'second_saved'
                    nodes.append(second)
                    document['content']['edges'][-1]['target'] = 'second-write'
                    document['content']['edges'].append({'id': 'second-end', 'source': 'second-write', 'target': 'end'})
                    next(node for node in nodes if node['id'] == 'end')['data']['retainEnvironment']['recordTargets'].append({'recordRef': "{second_saved['ref']}", 'expectedLinkRevision': "{second_saved['linkRevision']}", 'replaceAllowed': False})
                    if scenario == 'data-link-forged-end':
                        foreign = await client.post('/api/v1/projects', headers={'Idempotency-Key': str(uuid4())}, json={'name': '无权关联的外部项目'})
                        assert foreign.status_code == 201, foreign.text
                        foreign_project_id = foreign.json()['projectId']
                        next(node for node in nodes if node['id'] == 'end')['data']['retainEnvironment']['recordTargets'][1]['recordRef'] = {
                            'projectId': foreign_project_id, 'tableId': table['tableId'], 'datasetGeneration': table['datasetGeneration'],
                            'recordKey': "{second_saved['ref']['recordKey']}",
                        }
            if scenario.startswith('data-delete-field'):
                for identity, operation in [('preview-deletion', 'previewFieldDeletion'), ('delete-field', 'deleteField')]:
                    nodes.append({'id': identity, 'type': 'project_data', 'position': {'x': 100, 'y': 880}, 'data': {
                        'moduleType': 'project_data', 'operation': operation, 'variableName': 'field_deletion_preview' if operation == 'previewFieldDeletion' else 'removed',
                        'arguments': {'tableId': source_table['tableId'], 'datasetGeneration': source_table['datasetGeneration'], 'fieldId': removed_field,
                                      **({'expectedTableRevision': "{field_deletion_preview['tableRevision']}", 'impactRevision': "{field_deletion_preview['impactRevision']}"} if operation == 'deleteField' else {})},
                        'tableGrant': {'tableId': source_table['tableId'], 'datasetGeneration': source_table['datasetGeneration'], 'operations': ['deleteField'], 'fieldIds': [removed_field], 'readPurposes': []},
                    }})
                next(edge for edge in document['content']['edges'] if edge['id'] == 'end-task')['target'] = 'preview-deletion'
                document['content']['edges'].extend([{'id': 'commit-deletion', 'source': 'preview-deletion', 'target': 'delete-field'}, {'id': 'deletion-end', 'source': 'delete-field', 'target': 'end'}])
                if scenario.endswith('conflict'):
                    manager = app.state.project_workflow_worker_manager
                    original_capability = manager._on_capability
                    async def change_schema_after_preview(run_id, generation, request):
                        if request.get('operation') == 'deleteField':
                            current = (await client.get(source_path)).json()
                            changed = await client.post(source_path + '/fields', headers={'Idempotency-Key': str(uuid4())}, json={'definition': {'key': 'concurrent', 'name': '人工新字段', 'type': 'string', 'required': False, 'validation': {}}, 'sourceColumnPolicy': 'localOnly', 'expectedTableRevision': current['tableRevision']})
                            assert changed.status_code == 200, changed.text
                        return await original_capability(run_id, generation, request)
                    monkeypatch.setattr(manager, '_on_capability', change_schema_after_preview)
            if scenario == 'data-schema':
                nodes.extend([
                    {'id': 'schema', 'type': 'project_data', 'position': {'x': 100, 'y': 650}, 'data': {
                        'moduleType': 'project_data', 'operation': 'queryTableSchema', 'variableName': 'schema',
                        'arguments': {'tableId': source_table['tableId'], 'datasetGeneration': source_table['datasetGeneration'], 'fieldIds': [source_field]},
                        'tableGrant': {'tableId': source_table['tableId'], 'datasetGeneration': source_table['datasetGeneration'], 'operations': ['queryTableSchema'], 'fieldIds': [source_field], 'readPurposes': []},
                    }},
                    {'id': 'schema-check', 'type': 'condition', 'position': {'x': 100, 'y': 670}, 'data': {'moduleType': 'condition', 'leftValue': "{schema['fields'][0]['key']}", 'rightValue': 'code'}},
                ])
                next(edge for edge in document['content']['edges'] if edge['id'] == 'query-data')['target'] = 'schema'
                document['content']['edges'].extend([
                    {'id': 'schema-check', 'source': 'schema', 'target': 'schema-check'},
                    {'id': 'schema-query', 'source': 'schema-check', 'target': 'query', 'sourceHandle': 'true'},
                ])
            if scenario == 'data-loop-partial':
                nodes.append({'id': 'write-loop', 'type': 'loop', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'loop', 'count': 3, 'indexVariable': 'index'}})
                next(n for n in nodes if n['id'] == 'write')['data']['arguments']['values'][field_id] = 'row-{index}'
                next(e for e in document['content']['edges'] if e['id'] == 'save')['target'] = 'write-loop'
                document['content']['edges'][:] = [e for e in document['content']['edges'] if e['source'] != 'write']
                document['content']['edges'].extend([
                    {'id': 'iteration-write', 'source': 'write-loop', 'target': 'write', 'sourceHandle': 'loop'},
                    {'id': 'iteration-done', 'source': 'write-loop', 'target': 'end', 'sourceHandle': 'done'},
                ])
            if scenario in {'data-subflow', 'data-subflow-cancel'}:
                write = next(n for n in nodes if n['id'] == 'write')
                write['data']['arguments']['values'][field_id] = '{value}'
                nodes.extend([
                    {'id': 'child', 'type': 'subflow_header', 'position': {'x': 800, 'y': 0}, 'data': {'moduleType': 'subflow_header', 'subflowName': '冻结写入'}},
                    {'id': 'first-call', 'type': 'subflow', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'subflow', 'subflowGroupId': 'child', 'inputs': {'value': '{实际输入}-first'}, 'outputs': {'saved': 'saved'}}},
                    {'id': 'second-call', 'type': 'subflow', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'subflow', 'subflowGroupId': 'child', 'inputs': {'value': '{实际输入}-second'}, 'outputs': {'saved': 'secondSaved'}}},
                ])
                for edge in document['content']['edges']:
                    if edge['target'] == 'write': edge['target'] = 'first-call'
                    if edge['source'] == 'write': edge['source'] = 'second-call'
                document['content']['edges'].extend([{'id': 'child-body', 'source': 'child', 'target': 'write'}, {'id': 'next-call', 'source': 'first-call', 'target': 'second-call'}])
                next(n for n in nodes if n['id'] == 'end')['data']['retainEnvironment']['recordTargets'].append({'recordRef': "{secondSaved['ref']}", 'expectedLinkRevision': "{secondSaved['linkRevision']}", 'replaceAllowed': False})
            if scenario in {'data-parallel', 'data-parallel-failure'}:
                from copy import deepcopy
                write = next(n for n in nodes if n['id'] == 'write')
                other = deepcopy(write); other['id'] = 'other-write'
                write['data']['arguments']['values'][field_id] = 'A-{index}'
                other['data']['arguments']['values'][field_id] = 'B-{index}'
                if scenario == 'data-parallel-failure':
                    other.update(type='click_element', data={'moduleType': 'click_element', 'selector': '#missing-parallel', 'timeout': 1})
                nodes.extend([other,
                    {'id': 'fork', 'type': 'set_variable', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'set_variable', 'variableName': 'start', 'variableValue': 'yes', 'parallel': {'joinNodeId': 'end', 'outputs': {'left-loop': {'saved': 'saved'}, 'right-loop': {'saved': 'secondSaved'}}}}},
                    *[{'id': identity, 'type': 'loop', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'loop', 'count': count, 'indexVariable': 'index'}} for identity, count in [('left-loop', 2), ('right-loop', 3)]],
                ])
                for edge in document['content']['edges']:
                    if edge['target'] == 'write': edge['target'] = 'fork'
                document['content']['edges'][:] = [e for e in document['content']['edges'] if e['source'] != 'write']
                document['content']['edges'].extend([{'id': identity, 'source': 'fork', 'target': identity} for identity in ['left-loop', 'right-loop']] + [{'id': identity + '-body', 'source': identity, 'target': body, 'sourceHandle': 'loop'} for identity, body in [('left-loop', 'write'), ('right-loop', 'other-write')]] + [{'id': identity + '-done', 'source': identity, 'target': 'end', 'sourceHandle': 'done'} for identity in ['left-loop', 'right-loop']])
                next(n for n in nodes if n['id'] == 'end')['data']['retainEnvironment']['recordTargets'].append({'recordRef': "{secondSaved['ref']}", 'expectedLinkRevision': "{secondSaved['linkRevision']}", 'replaceAllowed': False})
            if scenario.startswith('manual-'):
                nodes.append({'id': 'manual', 'type': 'project_manual', 'position': {'x': 100, 'y': 900}, 'data': {'moduleType': 'project_manual', 'reason': '确认登录', 'timeoutSeconds': .3 if scenario == 'manual-expire' else 3 if scenario == 'manual-expire-race' else 120 if scenario == 'manual-force-stop' else 30}})
                document['content']['edges'].append({'id': 'manual-task', 'source': 'read-input', 'target': 'manual'})
                nodes.append({'id': 'after-manual', 'type': 'set_variable', 'position': {'x': 100, 'y': 950}, 'data': {'moduleType': 'set_variable', 'variableName': 'continued', 'variableValue': 'once'}})
                document['content']['edges'].append({'id': 'continue-task', 'source': 'manual', 'target': 'after-manual'})
                if scenario == 'manual-evidence-reconnect':
                    nodes.append({'id': 'after-failure', 'type': nodes[2]['type'], 'position': {'x': 100, 'y': 1000}, 'data': {**nodes[2]['data'], 'selector': '#missing-after-resume', 'timeout': 1}})
                    document['content']['edges'].append({'id': 'fail-after-resume', 'source': 'after-manual', 'target': 'after-failure'})
                if scenario == 'manual-double':
                    nodes.append({'id': 'second-manual', 'type': 'project_manual', 'position': {'x': 100, 'y': 1000}, 'data': {'moduleType': 'project_manual', 'reason': '第二次确认', 'timeoutSeconds': 30}})
                    document['content']['edges'].append({'id': 'second-checkpoint', 'source': 'after-manual', 'target': 'second-manual'})
            if scenario in {'manual-parallel', 'manual-parallel-finish', 'manual-parallel-stop'}:
                nodes.extend([
                    {'id': 'fork', 'type': 'set_variable', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'set_variable', 'variableName': 'start', 'variableValue': 'yes', 'parallel': {'joinNodeId': 'join', 'outputs': {}}}},
                    {'id': 'second-manual', 'type': 'project_manual', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'project_manual', 'reason': '并行第二项', 'timeoutSeconds': 30}},
                    {'id': 'other-normal', 'type': 'get_element_info', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'get_element_info', 'selector': '#field', 'attribute': 'value', 'variableName': 'afterOther'}},
                    {'id': 'join', 'type': 'set_variable', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'set_variable', 'variableName': 'joined', 'variableValue': 'once'}},
                ])
                next(e for e in document['content']['edges'] if e['id'] == 'manual-task')['target'] = 'fork'
                document['content']['edges'].extend([{'id': str(i) + '-parallel', 'source': a, 'target': b} for i, (a, b) in enumerate([('fork', 'manual'), ('fork', 'second-manual'), ('second-manual', 'other-normal'), ('after-manual', 'join'), ('other-normal', 'join')])])
            if scenario == 'manual-declared':
                next(n for n in nodes if n['id'] == 'manual')['data'].update(inputSchema=[{'name': 'code', 'type': 'string', 'required': True, 'enum': ['001', '002']}, {'name': 'confirmed', 'type': 'boolean', 'required': True}], resumeTargets=[{'nodeId': 'after-manual', 'requiredVariables': ['code', 'confirmed']}, {'nodeId': 'other-manual', 'requiredVariables': ['absent']}])
                next(n for n in nodes if n['id'] == 'after-manual')['data']['variableValue'] = 'code-{code}'
                nodes.append({'id': 'other-manual', 'type': 'set_variable', 'position': {'x': 600, 'y': 950}, 'data': {'moduleType': 'set_variable', 'variableName': 'wrong', 'variableValue': 'must not execute'}})
                document['content']['edges'].append({'id': 'alternate', 'source': 'manual', 'target': 'other-manual'})
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
                        "maxTasks": 1 if scenario in {"parameter-single", "manual-evidence-reconnect", "manual-force-stop", "data-subflow-cancel", "data-delete-field", "data-delete-field-conflict"} else 2,
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
            if scenario in {'data-subflow', 'data-subflow-cancel'}:
                original_run = app.state.project_workflow_worker_manager.run
                async def edit_child_after_prepare(**kwargs):
                    nonlocal subflow_source_edited
                    if not subflow_source_edited:
                        from copy import deepcopy
                        changed = deepcopy(saved_workflow.json())
                        next(n for n in changed['nodes'] if n['id'] == 'write')['data']['arguments']['values'][field_id] = 'edited after prepare'
                        updated = await client.put('/api/workflows/' + workflow_id, json={**changed, 'expectedRevision': changed['revision'], 'clientRequestId': str(uuid4())})
                        assert updated.status_code == 200, updated.text
                        subflow_source_edited = True
                    return await original_run(**kwargs)
                monkeypatch.setattr(app.state.project_workflow_worker_manager, 'run', edit_child_after_prepare)
                if scenario == 'data-subflow-cancel':
                    manager = app.state.project_workflow_worker_manager
                    original_capability = manager._on_capability
                    child_requests = []
                    async def cancel_before_second_child_write(run_id, generation, request):
                        if request.get('nodeId') == 'write':
                            child_requests.append(request)
                            if len(child_requests) == 2:
                                dispatcher = app.state.project_workflow_dispatcher
                                run = dispatcher.query_run(run_id)
                                await dispatcher.cancel(run_id, expected_status_revision=run.status_revision, execution_generation=generation)
                                from autoflow.domain.projects.models import ProjectError
                                try:
                                    return await original_capability(run_id, generation, request)
                                except ProjectError as error:
                                    cancelled_child_writes.append(error.code)
                                    raise
                        return await original_capability(run_id, generation, request)
                    monkeypatch.setattr(manager, '_on_capability', cancel_before_second_child_write)

            key = str(uuid4())
            payload = {
                "expectedAutomationRevision": automation["managementRevision"],
                "parameters": {parameter_id: parameter_value},
                "maxTasks": 1 if scenario in {"parameter-single", "manual-evidence-reconnect", "manual-force-stop", "data-subflow-cancel", "data-delete-field", "data-delete-field-conflict"} else 2,
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
            for _ in range(600 if scenario == "manual-force-stop" else 300):
                if scenario == 'manual-expire-race' and late_resume is None:
                    manual = (await client.get(prefix + '/manual-items')).json()['items']
                    waiting = next((item for item in manual if item['status'] == 'waiting'), None)
                    if waiting:
                        late_resume = asyncio.create_task(client.post(prefix + f"/manual-items/{waiting['manualItemId']}/resume", headers={'Idempotency-Key': str(uuid4())}, json={'checkpointRevision': waiting['checkpointRevision'], 'expectedStatusRevision': waiting['statusRevision']}))
                if scenario in {'manual-resume', 'manual-evidence-reconnect', 'manual-declared', 'manual-parallel', 'manual-parallel-finish', 'manual-finish', 'manual-double'}:
                    manual = await client.get(prefix + '/manual-items')
                    assert manual.status_code == 200, manual.text
                    for item in manual.json()['items']:
                        if item['status'] != 'waiting' or item['manualItemId'] in handled_manual:
                            continue
                        manual_id = item['manualItemId']
                        if scenario in {'manual-resume', 'manual-evidence-reconnect', 'manual-declared', 'manual-parallel', 'manual-double'}:
                            body = {'checkpointRevision': item['checkpointRevision'], 'expectedStatusRevision': item['statusRevision']}
                            action = 'resume'
                        else:
                            body = {'expectedCheckpointRevision': item['checkpointRevision'], 'expectedStatusRevision': item['statusRevision'], 'outcome': 'succeeded', 'reason': '已核验', 'retainEnvironment': {'enabled': False}}
                            action = 'finish'
                        if scenario == 'manual-declared':
                            original = (await client.get(prefix + f'/manual-items/{manual_id}')).json()
                            assert original['canResume'] and original['inputSchema'][0]['name'] == 'code'
                            valid = {**body, 'targetNodeId': 'after-manual', 'inputs': {'code': '001', 'confirmed': True}}
                            invalid = [{**valid, 'inputs': {}}, {**valid, 'inputs': {'code': 1, 'confirmed': True}}, {**valid, 'inputs': {'code': '003', 'confirmed': True}}, {**valid, 'inputs': {'code': '001', 'confirmed': True, 'extra': 1}}, {**valid, 'targetNodeId': 'manual'}, {**valid, 'targetNodeId': 'other-manual'}]
                            for rejected_body in invalid:
                                rejected_key = str(uuid4())
                                rejected = await client.post(prefix + f'/manual-items/{manual_id}/resume', headers={'Idempotency-Key': rejected_key}, json=rejected_body)
                                assert rejected.status_code == 422, rejected.text
                                assert (await client.get(prefix + f'/manual-items/{manual_id}')).json() == original
                                assert (await client.get(prefix + f'/operations/by-idempotency-key/{rejected_key}')).status_code == 404
                            for revision in ['checkpointRevision', 'expectedStatusRevision']:
                                rejected = await client.post(prefix + f'/manual-items/{manual_id}/resume', headers={'Idempotency-Key': str(uuid4())}, json={**valid, revision: valid[revision] + 1})
                                assert rejected.status_code == 409, rejected.text
                                assert (await client.get(prefix + f'/manual-items/{manual_id}')).json() == original
                            body = valid
                        if scenario == 'manual-parallel':
                            await asyncio.sleep(.15)
                            items = (await client.get(prefix + '/manual-items')).json()['items']
                            assert [i['manualItemId'] for i in items if i['status'] == 'waiting'] == [manual_id]
                            with app.state.session_factory() as session:
                                events = SqlAlchemyWorkflowRuntimeRepository(session).list_events(item['runId'], after_sequence=0, limit=300)
                            assert not any(e.kind == 'nodeAttempt' and e.node_id in {'after-manual', 'other-normal'} for e in events)
                        if scenario == 'manual-evidence-reconnect':
                            # Serve this same app/runtime over TCP; disconnect only the observer.
                            event_socket = socket.socket()
                            event_socket.bind(('127.0.0.1', 0))
                            event_server = uvicorn.Server(uvicorn.Config(app, lifespan='off', access_log=False, log_level='warning'))
                            event_server_task = asyncio.create_task(event_server.serve(sockets=[event_socket]))
                            for _ in range(100):
                                if event_server.started:
                                    break
                                await asyncio.sleep(.01)
                            assert event_server.started
                            event_url = f'http://127.0.0.1:{event_socket.getsockname()[1]}'
                            event_task_path = prefix + f"/tasks/{item['taskId']}"
                            checkpoint_snapshot = (await client.get(event_task_path)).json()
                            prefix_events = []
                            async with httpx.AsyncClient(base_url=event_url, trust_env=False, headers={'x-autoflow-token': settings.instance_token}, timeout=10) as observer, observer.stream('GET', event_task_path + '/events/stream') as stream:
                                if stream.status_code != 200:
                                    pytest.fail((await stream.aread()).decode())
                                async for line in stream.aiter_lines():
                                    if line.startswith('data: '):
                                        prefix_events.append(json.loads(line[6:]))
                                        if prefix_events[-1]['kind'] == 'output':
                                            break
                            seen_sequence = prefix_events[-1]['sequence']
                            assert checkpoint_snapshot['run']['status'] == 'waiting_manual'
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

                if scenario in {'manual-stop', 'manual-force-stop', 'manual-parallel-stop', 'manual-restart', 'manual-loss'} and not manual_interrupted:
                    items = (await client.get(prefix + '/manual-items')).json()['items']
                    waiting = next((item for item in items if item['status'] == 'waiting'), None)
                    if waiting:
                        manual_interrupted = True
                        if scenario == 'manual-loss':
                            app.state.project_workflow_worker_manager._workers[waiting['runId']].process.kill()
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
                            if scenario == 'manual-force-stop':
                                from autoflow.infrastructure.process.browser_processes import (
                                    process_birth,
                                )

                                force_worker = app.state.project_workflow_worker_manager._workers[waiting['runId']]
                                assert force_worker.process.returncode is None
                                assert force_worker.birth is not None
                                assert process_birth(force_worker.process.pid) == force_worker.birth
                                current = (await client.get(prefix + f'/batches/{batch_id}')).json()
                                assert current['forceStopAllowed'] is False and current['forceStopAvailableAt']
                                denied = await client.post(prefix + f'/batches/{batch_id}/force-stop', headers={'Idempotency-Key': str(uuid4())}, json={
                                    'expectedStatusRevision': current['batch']['statusRevision'], 'reason': '宽限期内拒绝',
                                })
                                assert denied.status_code == 409, denied.text
                                assert denied.json()['error']['code'] == 'FORCE_STOP_GRACE_ACTIVE'
                                assert force_worker.process.returncode is None
                if scenario == 'manual-force-stop' and force_worker is not None and force_receipt is None:
                    current = (await client.get(prefix + f'/batches/{batch_id}')).json()
                    if current['forceStopAllowed']:
                        assert dropped_stops and force_worker.process.returncode is None
                        force_key = str(uuid4())
                        force_body = {'expectedStatusRevision': current['batch']['statusRevision'], 'reason': '普通停止消息丢失后强停'}
                        forced = await client.post(prefix + f'/batches/{batch_id}/force-stop', headers={'Idempotency-Key': force_key}, json=force_body)
                        assert forced.status_code == 202, forced.text
                        force_receipt = forced.json()['operation']
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
            assert len(tasks) == (1 if scenario in {"parameter-single", "manual-evidence-reconnect", "manual-force-stop", "data-subflow-cancel", "data-delete-field", "data-delete-field-conflict"} else 2)
            for task in tasks:
                viewed = await client.get(prefix + f"/tasks/{task['taskId']}")
                assert viewed.status_code == 200, viewed.text
                assert viewed.json()["inputSnapshot"]["parameters"] == {
                    parameter_id: parameter_value
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
            if scenario in {"success", "parameter-single"}:
                expected_outputs = ["yes", "first" if scenario == "parameter-single" else "before-真实参数"]
                assert detail["statusCounts"]["succeeded"] == len(tasks) and requests, {
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
                    assert [item["value"] for item in outputs.json()["items"]] == expected_outputs
                    with app.state.session_factory() as session:
                        events = SqlAlchemyWorkflowRuntimeRepository(
                            session
                        ).list_events(task["runId"], after_sequence=0, limit=200)
                    assert [
                        event.payload["value"]
                        for event in events
                        if event.kind == "output"
                    ] == expected_outputs
                    assert [event.sequence for event in events] == list(
                        range(1, len(events) + 1)
                    )
                if scenario == 'parameter-single':
                    from sqlalchemy import func, select

                    from autoflow.infrastructure.database.project_run_models import (
                        ProjectBatchRow,
                        ProjectRecordLeaseRow,
                        ProjectTaskRow,
                    )
                    from autoflow.infrastructure.database.workflow_runtime_models import (
                        WorkflowRunRow,
                    )

                    with app.state.session_factory() as session:
                        for model in (ProjectBatchRow, ProjectTaskRow, WorkflowRunRow):
                            assert session.scalar(select(func.count()).select_from(model)) == 1
                        assert session.scalar(select(func.count()).select_from(ProjectRecordLeaseRow)) == 0
                    assert requests.count('/fixture') == 1
                    assert (await client.get(prefix + '/tables')).json()['items'] == []
            elif scenario == 'parameter-isolation':
                from sqlalchemy import select

                from autoflow.infrastructure.database.project_run_models import (
                    ProjectRecordLeaseRow,
                )

                assert detail['statusCounts']['succeeded'] == 2
                assert len({task['taskId'] for task in tasks}) == len({task['runId'] for task in tasks}) == 2
                for task in tasks:
                    outputs = (await client.get(prefix + f"/tasks/{task['taskId']}/outputs")).json()['items']
                    # The existing set_variable executor defaults an unset name to 0.
                    assert [output['value'] for output in outputs] == ['yes', 'before-真实参数', 0, 'must-not-leak']
                    attempts = (await client.get(prefix + f"/tasks/{task['taskId']}/node-attempts")).json()['items']
                    assert len(attempts) == 7 and all(attempt['status'] == 'succeeded' for attempt in attempts)
                with app.state.session_factory() as session:
                    assert not session.scalars(select(ProjectRecordLeaseRow)).all()
                assert requests.count('/fixture') == 2
                assert (await client.get(result_path + '/records', params={'datasetGeneration': result_table['datasetGeneration']})).json()['items'] == original_result_rows
            elif scenario == 'manual-evidence-reconnect':
                assert detail['statusCounts']['failed'] == len(handled_manual) == 1, detail
                assert tasks[0]['taskId'] == checkpoint_snapshot['task']['taskId']
                async with httpx.AsyncClient(base_url=event_url, trust_env=False, headers={'x-autoflow-token': settings.instance_token}, timeout=10) as observer:
                    suffix_events = []
                    cursor = seen_sequence
                    while True:
                        response = await observer.get(event_task_path + '/events', params={'afterSequence': cursor})
                        assert response.status_code == 200, response.text
                        page = response.json()
                        suffix_events.extend(page['items'])
                        cursor = page['afterSequence']
                        if not page['hasMore']:
                            break
                    assert page['terminal'] and cursor == page['lastSequence']
                    stream = await observer.get(event_task_path + '/events/stream', params={'afterSequence': 0}, headers={'Last-Event-ID': str(seen_sequence)})
                    assert stream.status_code == 200, stream.text
                    frames = [dict(line.split(': ', 1) for line in frame.splitlines()) for frame in stream.text.strip().split('\n\n')]
                    replay_events = [json.loads(frame['data']) for frame in frames]
                    for event in replay_events + suffix_events:
                        event['occurredAt'] = datetime.fromisoformat(event['occurredAt'])
                    assert replay_events == suffix_events
                    assert all(frame['id'] == str(event['sequence']) and frame['event'] == event['kind'] for frame, event in zip(frames, suffix_events, strict=True))
                    events = prefix_events + suffix_events
                    assert [event['sequence'] for event in events] == list(range(1, cursor + 1))
                    assert len({event['eventId'] for event in events}) == len(events)
                    assert {event['runId'] for event in events} == {tasks[0]['runId']}
                    assert {event['executionGeneration'] for event in events} == {checkpoint_snapshot['run']['executionGeneration']}
                    snapshot = (await observer.get(event_task_path)).json()
                    assert snapshot['run']['status'] == 'failed' and snapshot['run']['lastSequence'] == cursor
                    assert snapshot['inputSnapshot'] == checkpoint_snapshot['inputSnapshot']
                    attempts = (await observer.get(event_task_path + '/node-attempts')).json()['items']
                    assert len(attempts) == len({(item['nodeVisitId'], item['attempt']) for item in attempts}) == 8
                    assert {item['nodeId'] for item in attempts if item['status'] == 'failed'} == {'after-failure'}
                    assert sum(item['status'] == 'succeeded' for item in attempts) == 7
                    outputs = (await observer.get(event_task_path + '/outputs')).json()['items']
                    assert len({item['outputId'] for item in outputs}) == 3
                    assert [item['value'] for item in outputs] == ['yes', 'before-真实参数', 'once']
                    assert [item['value'] for item in outputs] == [event['payload']['value'] for event in events if event['kind'] == 'output']
                    logs, log_cursor = [], 0
                    while True:
                        log_page = (await observer.get(event_task_path + '/logs', params={'afterSequence': log_cursor, 'pageSize': 2})).json()
                        logs.extend(log_page['items'])
                        log_cursor = log_page['afterSequence']
                        if not log_page['hasMore']:
                            break
                    assert [item['sequence'] for item in logs] == [event['sequence'] for event in events if event['kind'] == 'log']
                    assert len({item['eventId'] for item in logs}) == len(logs) > 2
                    artifacts = (await observer.get(event_task_path + '/artifacts')).json()['items']
                    assert len(artifacts) == 1 and artifacts[0]['availability'] == 'available'
                    artifact = artifacts[0]
                    assert artifact['artifactId'] in [event['payload'].get('artifactId') for event in events if event['kind'] == 'artifact']
                    screenshot = await observer.get(artifact['contentUrl'])
                    assert screenshot.status_code == 200 and screenshot.headers['content-type'] == 'image/png', screenshot.text if screenshot.status_code != 200 else screenshot.headers
                    assert screenshot.content.startswith(b'\x89PNG\r\n\x1a\n')
                    assert len(screenshot.content) == artifact['byteSize']
                    assert hashlib.sha256(screenshot.content).hexdigest() == artifact['sha256']
                    assert (await observer.get(event_task_path)).json() == snapshot
                    assert (await observer.get(event_task_path + '/outputs')).json()['items'] == outputs
                    assert (await observer.get(event_task_path + '/artifacts')).json()['items'] == artifacts
                    assert (await observer.get(event_task_path + '/events', params={'afterSequence': cursor})).json()['items'] == []
                assert requests.count('/fixture') == 1
            elif scenario.startswith('manual-'):
                if scenario in {'manual-race', 'manual-race-intent'}:
                    assert detail['statusCounts']['succeeded'] == 2, detail
                    assert len(race_commands) == 2
                    for task in tasks:
                        attempts = (await client.get(prefix + f"/tasks/{task['taskId']}/node-attempts")).json()['items']
                        assert sum(attempt['nodeId'] == 'after-manual' for attempt in attempts) == 1
                elif scenario in {'manual-stop', 'manual-force-stop', 'manual-parallel-stop', 'manual-restart', 'manual-loss'}:
                    assert manual_interrupted
                    assert detail['statusCounts']['interrupted' if scenario in {'manual-force-stop', 'manual-restart', 'manual-loss'} else 'cancelled'] >= 1, detail
                    manual_items = (await client.get(prefix + '/manual-items')).json()['items']
                    assert all(item['status'] == 'cancelled' for item in manual_items)
                    if scenario == 'manual-force-stop':
                        assert force_receipt is not None and force_worker is not None
                        assert detail['batch']['status'] == 'stopped'
                        assert detail['statusCounts']['interrupted'] == 1
                        current_task = (await client.get(prefix + f"/tasks/{tasks[0]['taskId']}")).json()
                        assert current_task['run']['error']['code'] == 'WORKFLOW_RESULT_UNKNOWN'
                        assert current_task['run']['executionGeneration'] > force_worker.generation
                        assert force_worker.process.returncode is not None
                        assert process_birth(force_worker.process.pid) != force_worker.birth
                        assert not force_worker.directory.exists()
                        force_final = await client.get(prefix + f'/operations/by-idempotency-key/{force_key}')
                        assert force_final.status_code == 200, force_final.text
                        assert force_final.json()['operationId'] == force_receipt['operationId']
                        assert force_final.json()['status'] == 'succeeded'
                        force_replay = await client.post(prefix + f'/batches/{batch_id}/force-stop', headers={'Idempotency-Key': force_key}, json=force_body)
                        assert force_replay.status_code == 202, force_replay.text
                        replayed_stop, queried_stop = force_replay.json()['operation'], force_final.json()
                        # Generic operation lookup types BatchView dates; run commands
                        # retain JSON dates in result. Compare the same instants.
                        for operation in (replayed_stop, queried_stop):
                            for name in ('createdAt', 'completedAt'):
                                value = operation['result']['batch'][name]
                                if value is not None:
                                    operation['result']['batch'][name] = datetime.fromisoformat(value).isoformat()
                        assert replayed_stop == queried_stop
                        attempts = (await client.get(prefix + f"/tasks/{tasks[0]['taskId']}/node-attempts")).json()['items']
                        assert not any(attempt['nodeId'] == 'after-manual' for attempt in attempts)
                        assert requests.count('/fixture') == 1
                elif scenario not in {'manual-expire', 'manual-expire-race'}:
                    assert detail['statusCounts']['succeeded'] == 2, detail
                    assert len(handled_manual) == (4 if scenario in {'manual-double', 'manual-parallel'} else 2)
                    if scenario == 'manual-double':
                        assert len(replayed_manual) == 2
                    for task in tasks:
                        attempts = (await client.get(prefix + f"/tasks/{task['taskId']}/node-attempts")).json()['items']
                        assert len([a for a in attempts if a['nodeId'] == 'read-input']) == 1
                        if scenario == 'manual-parallel':
                            assert sum(a['nodeId'] == 'join' for a in attempts) == 1
                            assert sum(a['nodeId'] == 'other-normal' for a in attempts) == 1
                            items = [i for i in (await client.get(prefix + '/manual-items')).json()['items'] if i['runId'] == task['runId']]
                            items.sort(key=lambda i: i['createdAt'])
                            assert len(items) == 2
                            assert datetime.fromisoformat(items[1]['createdAt']) >= datetime.fromisoformat(items[0]['updatedAt'])
                            assert all(29.5 < (datetime.fromisoformat(i['expiresAt']) - datetime.fromisoformat(i['createdAt'])).total_seconds() <= 30 for i in items)
                        if scenario == 'manual-declared':
                            assert not any(a['nodeId'] == 'other-manual' for a in attempts)
                            outputs = (await client.get(prefix + f"/tasks/{task['taskId']}/outputs")).json()['items']
                            assert any(output['value'] == 'code-001' for output in outputs)

                        assert any(a['nodeId'] == 'after-manual' for a in attempts) == (scenario in {'manual-resume', 'manual-declared', 'manual-parallel', 'manual-double'})
                else:
                    assert detail['statusCounts']['timed_out'] == 1, detail
                    if scenario == 'manual-expire-race':
                        assert late_resume is not None
                        rejected = await late_resume
                        assert rejected.status_code == 409, rejected.text
                        assert rejected.json()['error']['code'] == 'MANUAL_TRANSITION_LOST'
                        items = (await client.get(prefix + '/manual-items')).json()['items']
                        assert len(items) == 1 and items[0]['status'] == 'expired'
            elif scenario == 'data-loop-partial':
                from sqlalchemy import select

                from autoflow.infrastructure.database.models import ProjectOperationRow
                from autoflow.infrastructure.database.project_run_models import (
                    ProjectRecordLeaseRow,
                )

                assert detail['statusCounts']['failed'] == 1, detail
                assert detail['statusCounts']['cancelled'] == 1, detail
                records = (await client.get(table_path + '/records', params={'datasetGeneration': table['datasetGeneration']})).json()['items']
                assert sorted(row['values'][0]['value'] for row in records) == ['row-0', 'row-1']
                assert all(row['contentRevision'] == row['statusRevision'] == row['linkRevision'] == 1 for row in records)
                assert all(row['statusId'] is None and row['currentEnvironmentId'] is None for row in records)
                failed = next(task for task in tasks if task['status'] == 'failed')
                attempts = (await client.get(prefix + f"/tasks/{failed['taskId']}/node-attempts")).json()['items']
                writes = [attempt for attempt in attempts if attempt['nodeId'] == 'write']
                assert sorted(attempt['status'] for attempt in writes) == ['failed', 'succeeded', 'succeeded']
                assert not any(attempt['nodeId'] == 'end' for attempt in attempts)
                with app.state.session_factory() as session:
                    operations = session.scalars(select(ProjectOperationRow).where(ProjectOperationRow.project_id == project_id)).all()
                    confirmed = [op for op in operations if op.kind == 'createRecord' and op.status == 'succeeded']
                    # One source record plus the two committed loop outputs remain.
                    assert len(confirmed) == 3
                    leases = session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.task_id == failed['taskId'])).all()
                    assert len(leases) == 2 and all(lease.state == 'released' for lease in leases)
            elif scenario == 'data-parallel-failure':
                assert detail['statusCounts']['failed'] == 1, detail
                records = (await client.get(table_path + '/records', params={'datasetGeneration': table['datasetGeneration']})).json()['items']
                assert sorted(row['values'][0]['value'] for row in records) == ['A-0', 'A-1']
                assert all(row['currentEnvironmentId'] is None for row in records)
                for task in tasks:
                    attempts = (await client.get(prefix + f"/tasks/{task['taskId']}/node-attempts")).json()['items']
                    assert not any(a['nodeId'] == 'end' for a in attempts)
            elif scenario == 'data-parallel':
                assert detail['statusCounts']['succeeded'] == 2, {'detail': detail, 'tasks': [(await client.get(prefix + f"/tasks/{t['taskId']}")).json() for t in tasks]}
                records = (await client.get(table_path + '/records', params={'datasetGeneration': table['datasetGeneration']})).json()['items']
                assert sorted(row['values'][0]['value'] for row in records) == sorted(['A-0', 'A-1', 'B-0', 'B-1', 'B-2'] * 2)
                assert sum(bool(row['currentEnvironmentId']) for row in records) == 4
                for task in tasks:
                    with app.state.session_factory() as session:
                        events = SqlAlchemyWorkflowRuntimeRepository(session).list_events(task['runId'], after_sequence=0, limit=300)
                    starts = [e for e in events if e.kind == 'nodeAttempt' and e.payload['status'] == 'started']
                    assert sum(e.node_id == 'end' for e in starts) == 1
                    for identity, branch, count in [('write', 'left-loop', 2), ('other-write', 'right-loop', 3)]:
                        writes = [e for e in starts if e.node_id == identity]
                        assert len(writes) == count
                        assert all(e.payload['executionContext']['scopes'][0]['branchNodeId'] == branch for e in writes)
                        assert [e.payload['executionContext']['loops'][0]['currentIndex'] for e in writes] == list(range(count))
            elif scenario == 'data-subflow-cancel':
                assert cancelled_child_writes == ['CAPABILITY_SCOPE_DENIED']
                assert detail['statusCounts']['cancelled'] == 1, detail
                records = (await client.get(table_path + '/records', params={'datasetGeneration': table['datasetGeneration']})).json()['items']
                assert [row['values'][0]['value'] for row in records] == ['before-真实参数-first']
                assert records[0]['currentEnvironmentId'] is None
            elif scenario == 'data-subflow':
                assert subflow_source_edited
                assert detail['statusCounts']['succeeded'] == 2, {'detail': detail, 'tasks': [(await client.get(prefix + f"/tasks/{t['taskId']}")).json() for t in tasks]}
                records = (await client.get(table_path + '/records', params={'datasetGeneration': table['datasetGeneration']})).json()['items']
                assert sorted(row['values'][0]['value'] for row in records) == ['before-真实参数-first'] * 2 + ['before-真实参数-second'] * 2
                assert all(row['currentEnvironmentId'] for row in records)
                for task in tasks:
                    with app.state.session_factory() as session:
                        events = SqlAlchemyWorkflowRuntimeRepository(session).list_events(task['runId'], after_sequence=0, limit=300)
                    writes = [e for e in events if e.kind == 'nodeAttempt' and e.node_id == 'write' and e.payload['status'] == 'started']
                    assert len(writes) == 2 and writes[0].node_visit_id != writes[1].node_visit_id
                    assert [e.payload['executionContext']['scopes'][0]['callNodeId'] for e in writes] == ['first-call', 'second-call']
            elif scenario == 'data-link-forged-end':
                from sqlalchemy import select

                from autoflow.infrastructure.database.project_run_models import (
                    ProjectRecordLeaseRow,
                )

                assert detail['statusCounts']['failed'] == detail['statusCounts']['cancelled'] == 1, detail
                failed = next(task for task in tasks if task['status'] == 'failed')
                task_path = prefix + f"/tasks/{failed['taskId']}"
                outputs = (await client.get(task_path + '/outputs')).json()['items']
                created_refs = [output['value']['ref'] for output in outputs if output['nodeId'] in {'write', 'second-write'}]
                assert len(created_refs) == 2 and all(ref['projectId'] == project_id for ref in created_refs)
                assert len(end_requests) == 1
                targets = end_requests[0]['arguments']['retainEnvironment']['recordTargets']
                assert targets == [
                    {'recordRef': created_refs[0], 'expectedLinkRevision': 1, 'replaceAllowed': False},
                    {'recordRef': {**created_refs[1], 'projectId': foreign_project_id}, 'expectedLinkRevision': 1, 'replaceAllowed': False},
                ]
                assert end_requests[0]['browserClosed'] is True
                attempts = (await client.get(task_path + '/node-attempts')).json()['items']
                end_attempts = [attempt for attempt in attempts if attempt['nodeId'] == 'end']
                assert len(end_attempts) == 1 and end_attempts[0]['status'] == 'failed'
                assert end_attempts[0]['error']['code'] == 'CAPABILITY_SCOPE_DENIED'
                rows = (await client.get(table_path + '/records', params={'datasetGeneration': table['datasetGeneration']})).json()['items']
                assert len(rows) == 2 and all(row['values'][0]['value'] == 'before-真实参数-001' for row in rows)
                assert all(row['currentEnvironmentId'] is None and row['linkRevision'] == 1 for row in rows)
                assert (await client.get(prefix + '/environments')).json()['total'] == 0
                assert (await client.get(f'/api/v1/projects/{foreign_project_id}/environments')).json()['total'] == 0
                operations = (await client.get(prefix + '/operations', params={'pageSize': 200})).json()['items']
                assert not any(operation['idempotencyKey'].startswith('end-save:') for operation in operations)
                with app.state.session_factory() as session:
                    leases = session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.task_id == failed['taskId'])).all()
                    assert len(leases) == 2 and all(lease.state == 'released' for lease in leases)
                assert requests.count('/login') == 1
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
                forged_targets = [{'recordRef': row['ref'], 'expectedLinkRevision': row['linkRevision'], 'replaceAllowed': False} for row in rows]
                forged_targets[0]['recordRef'] = {**forged_targets[0]['recordRef'], 'projectId': str(uuid4())}
                forged = await client.post(prefix + f"/environment-operations/{saved['operationId']}/repair", headers={'Idempotency-Key': str(uuid4())}, json={'recordTargets': forged_targets})
                assert forged.status_code == 202, forged.text
                assert forged.json()['outcome']['phase'] == 'saved_unlinked'
                assert (await client.get(prefix + '/environments')).json() == environments
                assert (await client.get(table_path + '/records', params={'datasetGeneration': table['datasetGeneration']})).json()['items'] == rows
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
            elif scenario.startswith('data-delete-field'):
                succeeded = not scenario.endswith('conflict')
                assert detail['statusCounts'].get('succeeded' if succeeded else 'failed') == 1, detail
                fields_after = (await client.get(source_path + '/fields')).json()['items']
                assert (removed_field not in {field['ref']['fieldId'] for field in fields_after}) == succeeded
                source_rows = (await client.get(source_path + '/records', params={'datasetGeneration': source_table['datasetGeneration']})).json()['items']
                values = {value['fieldId']: value['value'] for value in source_rows[0]['values']}
                assert values[source_field] == '001'
                assert (removed_field not in values) == succeeded
                written = (await client.get(table_path + '/records', params={'datasetGeneration': table['datasetGeneration']})).json()['items']
                assert [row['values'][0]['value'] for row in written] == ['before-真实参数-001']
                assert bool(written[0]['currentEnvironmentId']) == succeeded
                evidence = (await client.get(prefix + f"/tasks/{tasks[0]['taskId']}")).json()
                assert any(write['kind'] == 'fieldDeleted' for write in evidence['dataWrites']) == succeeded
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
            elif scenario in {"data", "data-schema", "data-old-candidate"}:
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
        try:
            if event_server is not None:
                event_server.should_exit = True
                await asyncio.wait_for(event_server_task, timeout=10)
        finally:
            if event_socket is not None:
                event_socket.close()
            await app.router.on_shutdown[-1]()
