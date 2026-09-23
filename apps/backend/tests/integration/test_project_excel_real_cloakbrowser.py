"""FX-01 through TCP HTTP, actual Excel import, SQLite and native browser workers."""

import asyncio
import hashlib
import json
import shutil
import socket
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from uuid import uuid4

import httpx
import pytest
import uvicorn
from openpyxl import Workbook
from sqlalchemy import select

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.profiles.models import ProfileSpec
from autoflow.domain.project_data.identity import RecordKey, encode_record_key
from autoflow.infrastructure.database.project_run_models import ProjectRecordLeaseRow
from tests.integration.test_project_run_data_start import _input
from tests.integration.test_workflow_real_cloakbrowser import (
    real_cloak_page as cloak_fixture,
)

real_cloak_page = cloak_fixture


@pytest.mark.asyncio
async def test_excel_multi_input_status_progression_and_same_batch_reclaim(
    tmp_path, valid_profile_values, real_cloak_page, monkeypatch,
):
    executable, url, requests = real_cloak_page
    kernel = next(parent for parent in executable.parents if parent.name.startswith('chromium-'))
    shutil.copytree(kernel, tmp_path / 'data' / 'kernels' / kernel.name)
    app = create_app(Settings(data_dir=str(tmp_path), instance_id='excel-real', instance_token='renderer', host_token='host'))
    server = uvicorn.Server(uvicorn.Config(app, lifespan='off', access_log=False, log_level='warning'))
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    server_task = None
    manager = app.state.project_workflow_worker_manager
    real_run = manager.run
    active_groups = []

    async def observe_committed_group(**kwargs):
        with app.state.session_factory() as session:
            leases = list(session.scalars(select(ProjectRecordLeaseRow)))
            held = [lease for lease in leases if lease.state == 'held']
            assert len(held) == 2
            assert {lease.run_id for lease in held} == {kwargs['run_id']}
            assert all(lease.state == 'released' for lease in leases if lease not in held)
            active_groups.append({lease.record_ref['recordKey']['value'] for lease in held})
        return await real_run(**kwargs)

    monkeypatch.setattr(manager, 'run', observe_committed_group)
    try:
        profile = app.state.profile_service.create(ProfileSpec.from_values({
            **valid_profile_values, 'headless': True,
            'browser_version': kernel.name.removeprefix('chromium-'),
        }))
        await app.state.project_workflow_dispatcher.startup()
        await app.state.project_run_scheduler.startup()
        server_task = asyncio.create_task(server.serve(sockets=[listener]))
        async with asyncio.timeout(10):
            while not server.started:
                await asyncio.sleep(.01)
        async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{listener.getsockname()[1]}', headers={'x-autoflow-token': 'renderer'}, timeout=30, trust_env=False) as client:
            async def api(method, path, body=None, status=200, headers=None):
                response = await client.request(method, path, json=body, headers=headers)
                assert response.status_code == status, response.text
                return response.json() if response.content else None

            async def post(path, body, status=201, headers=None):
                return await api('POST', path, body, status, {'Idempotency-Key': str(uuid4()), **(headers or {})})

            project = await post('/api/v1/projects', {'name': 'FX-01 Excel多输入'})
            project_id = project['projectId']
            prefix = f'/api/v1/projects/{project_id}'
            workbook_path = tmp_path / 'FX-01.xlsx'
            book = Workbook()
            book.remove(book.active)
            fixtures = {'W': [('code', 'account'), ('W01', 'A01'), ('W02', 'A01'), ('W03', 'A01')], 'A': [('code', 'value'), ('A01', 'account-value')], 'D': [('code', 'value'), ('D01', 'reference-value')]}
            for name, rows in fixtures.items():
                sheet = book.create_sheet(name)
                for row in rows:
                    sheet.append(row)
            book.save(workbook_path)
            original_hash = hashlib.sha256(workbook_path.read_bytes()).hexdigest()
            proof, token = str(uuid4()), str(uuid4())
            await api('POST', '/internal/project-files/selections', {
                'projectId': project_id, 'path': str(workbook_path), 'windowId': 7,
                'purpose': 'inspectExcel', 'selectionToken': token,
                'expiresAt': (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            }, 204, {'x-autoflow-host-token': 'host', 'x-autoflow-file-window-token': proof})
            file_headers = {'x-autoflow-file-window-id': '7', 'x-autoflow-file-window-token': proof}
            inspection = (await post(prefix + '/table-imports/excel/inspect', {'selectionToken': token}, 200, file_headers))['inspection']
            tables, fields, imported = {}, {}, {}
            for sheet in inspection['sheets']:
                name = sheet['name']
                key = str(uuid4())
                await post(prefix + '/table-imports/excel', {
                    'name': name, 'inspectionId': inspection['inspectionId'], 'fingerprint': inspection['fingerprint'], 'sheetId': sheet['sheetId'],
                    'mapping': [{'columnIndex': i, 'target': {'kind': 'new', 'definition': {'key': key, 'name': key, 'type': 'string', 'required': True, 'validation': {}}}} for i, key in enumerate(fixtures[name][0])],
                    'identity': {'mode': 'column', 'columnIndex': 0},
                }, 202, {**file_headers, 'Idempotency-Key': key})
                async with asyncio.timeout(20):
                    while True:
                        operation = await api('GET', prefix + '/operations/by-idempotency-key/' + key)
                        if operation['status'] in {'succeeded', 'failed'}:
                            break
                        await asyncio.sleep(.02)
                assert operation['status'] == 'succeeded', operation
                tables[name] = operation['result']['table']
                path = prefix + f"/tables/{tables[name]['tableId']}"
                fields[name] = {field['key']: field for field in (await api('GET', path + '/fields'))['items']}
                imported[name] = (await api('GET', path + '/records?datasetGeneration=' + tables[name]['datasetGeneration']))['items']
                assert len(imported[name]) == len(fixtures[name]) - 1
                assert all(row['statusId'] is None and row['statusRevision'] == 1 for row in imported[name])

            async def rows(name):
                table = tables[name]
                return (await api('GET', prefix + f"/tables/{table['tableId']}/records?datasetGeneration={table['datasetGeneration']}"))['items']

            statuses = {}
            for name, titles in [('W', ['待处理', '已完成']), ('A', ['可用'])]:
                table = tables[name]
                path = prefix + f"/tables/{table['tableId']}"
                statuses[name] = []
                for index, title in enumerate(titles):
                    current = await api('GET', path)
                    status = await post(path + '/statuses', {'name': title, 'color': '#123456', 'order': index, 'expectedTableRevision': current['tableRevision']})
                    statuses[name].append(status['statusId'])
                for row in imported[name]:
                    key = row['ref']['recordKey']
                    await api('PUT', path + '/records/' + encode_record_key(RecordKey(**key)) + '/status', {
                        'datasetGeneration': table['datasetGeneration'], 'recordKeyType': key['type'],
                        'statusId': statuses[name][0], 'expectedStatusRevision': 1,
                    }, headers={'Idempotency-Key': str(uuid4())})
            account_before = await rows('A')
            document_before = await rows('D')
            work_input = _input(project_id, tables['W'], fields['W']['account'], '待办')
            account_input = _input(project_id, tables['A'], fields['A']['code'], '账号')
            account_input.update(mode='related', relation={
                'type': 'fieldEquals', 'sourceInputId': work_input['inputId'],
                'sourceFieldRef': work_input['fieldBindings'][0]['fieldRef'],
                'targetFieldRef': account_input['fieldBindings'][0]['fieldRef'],
            }, filter={'type': 'status', 'operator': 'eq', 'statusId': statuses['A'][0]})

            def node(identity, kind, **data):
                return {'id': identity, 'type': kind, 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': kind, **data}}

            details_field = fields['D']['value']['ref']['fieldId']
            completed_rows = None
            batches = []
            evidence = []
            for change_status in [True, False]:
                selected = deepcopy(work_input)
                selected['filter'] = {'type': 'status', 'operator': 'eq', 'statusId': statuses['W'][0 if change_status else 1]}
                nodes = [
                    node('inputs', 'project_data', operation='inputs', variableName='frozen', arguments={}),
                    node('reference', 'project_data', operation='queryRecords', variableName='reference', arguments={
                        'tableId': tables['D']['tableId'], 'datasetGeneration': tables['D']['datasetGeneration'], 'fieldIds': [details_field],
                        'readPurpose': 'condition', 'filter': None, 'orderBy': [], 'cursor': None, 'limit': 20,
                    }, tableGrant={'tableId': tables['D']['tableId'], 'datasetGeneration': tables['D']['datasetGeneration'], 'operations': ['queryRecords'], 'fieldIds': [details_field], 'readPurposes': ['condition']}),
                    node('open', 'open_page', url=url, timeout=30),
                    node('fill', 'input_text', selector='#field', clearBefore=True, text="{frozen[0]['recordRef']['recordKey']['value']}/{frozen[1]['recordRef']['recordKey']['value']}/{reference['items'][0]['values'][0]['value']}"),
                    node('read', 'get_element_info', selector='#field', attribute='value', variableName='browserResult'),
                ]
                if change_status:
                    nodes.append(node('status', 'project_data', operation='setRecordStatus', variableName='changed', arguments={
                        'recordRef': "{frozen[0]['recordRef']}", 'statusId': statuses['W'][1], 'expectedStatusRevision': "{frozen[0]['statusRevision']}",
                        'expectedContentRevisionWhenDerived': "{frozen[0]['contentRevision']}", 'allowedFrom': [statuses['W'][0]],
                    }, tableGrant={'tableId': tables['W']['tableId'], 'datasetGeneration': tables['W']['datasetGeneration'], 'operations': ['setRecordStatus'], 'fieldIds': [fields['W']['account']['ref']['fieldId']], 'readPurposes': []}))
                nodes.append(node('end', 'project_end', retainEnvironment={'enabled': False}))
                workflow = await post('/api/workflows', {'id': str(uuid4()), 'clientRequestId': str(uuid4()), 'name': '推进状态' if change_status else '最终态复用', 'variables': [], 'nodes': nodes, 'edges': [{'id': str(uuid4()), 'source': left['id'], 'target': right['id']} for left, right in pairwise(nodes)]})
                automation = await post(prefix + '/automations', {
                    'name': '推进状态' if change_status else '最终态复用', 'description': '', 'workflowId': workflow['id'],
                    'parameterSchema': [], 'inputPlan': {'inputs': [selected, account_input]},
                    'environmentPolicy': {'source': 'newFromProfile', 'profileId': profile.id, 'proxyOverride': {'mode': 'none'}, 'modelProviderId': None},
                    'runPolicy': {'maxTasks': 3, 'concurrency': 1, 'maxLiveInstances': 1, 'continueAfterFailure': False, 'automaticExecutionTimeoutSeconds': 60, 'manualDeadlineSeconds': 120},
                })
                batch_id = (await post(prefix + f"/automations/{automation['automationId']}/batches", {'expectedAutomationRevision': automation['managementRevision'], 'parameters': {}, 'maxTasks': 3, 'concurrency': 1}, 202))['operation']['result']['batch']['batchId']
                batches.append(batch_id)
                async with asyncio.timeout(120):
                    while True:
                        detail = await api('GET', prefix + '/batches/' + batch_id)
                        if detail['batch']['status'] in {'completed', 'failed', 'interrupted', 'stopped'}:
                            break
                        await asyncio.sleep(.05)
                assert detail['batch']['status'] == 'completed', detail
                assert detail['batch']['createdTaskCount'] == detail['statusCounts']['succeeded'] == 3
                tasks = (await api('GET', prefix + '/tasks?batchId=' + batch_id))['items']
                tasks.sort(key=lambda task: task['taskOrdinal'])
                assert len({task['taskId'] for task in tasks}) == len({task['runId'] for task in tasks}) == 3
                expected_keys = ['W01', 'W02', 'W03'] if change_status else ['W01'] * 3
                task_evidence = []
                for task, expected_key in zip(tasks, expected_keys, strict=True):
                    task_path = prefix + '/tasks/' + task['taskId']
                    inputs = (await api('GET', task_path))['inputSnapshot']['inputs']
                    assert [item['recordRef']['recordKey']['value'] for item in inputs] == [expected_key, 'A01']
                    assert [item['statusRevision'] for item in inputs] == [2 if change_status else 3, 2]
                    outputs = (await api('GET', task_path + '/outputs'))['items']
                    browser_value = next(output['value'] for output in outputs if output['name'] == 'browserResult')
                    assert browser_value == expected_key + '/A01/reference-value'
                    task_evidence.append({'taskId': task['taskId'], 'runId': task['runId'], 'frozenInputs': inputs, 'browserValue': browser_value})
                    attempts = (await api('GET', task_path + '/node-attempts'))['items']
                    assert len(attempts) == len(nodes) and all(attempt['status'] == 'succeeded' for attempt in attempts)
                with app.state.session_factory() as session:
                    leases = list(session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.batch_id == batch_id)))
                    assert len(leases) == 6
                    assert all(lease.state == 'released' and lease.released_at is not None for lease in leases)
                    assert [lease.record_ref['recordKey']['value'] for lease in leases].count('A01') == 3
                    assert not any(lease.record_ref['tableId'] == tables['D']['tableId'] for lease in leases)
                current = await rows('W')
                assert all(row['statusId'] == statuses['W'][1] and row['statusRevision'] == 3 and row['contentRevision'] == 1 and row['linkRevision'] == 1 and row['currentEnvironmentId'] is None for row in current)
                assert [row['values'] for row in current] == [row['values'] for row in imported['W']]
                if change_status:
                    completed_rows = current
                else:
                    assert current == completed_rows
                assert await rows('A') == account_before
                assert await rows('D') == document_before
                assert hashlib.sha256(workbook_path.read_bytes()).hexdigest() == original_hash
                evidence.append({'batch': detail, 'changeStatus': change_status, 'tasks': task_evidence, 'workRows': current, 'releasedLeases': len(leases)})
            assert len(set(batches)) == 2
            assert active_groups == [{'W01', 'A01'}, {'W02', 'A01'}, {'W03', 'A01'}] + [{'W01', 'A01'}] * 3
            assert requests.count('/fixture') == 6
            assert not manager.busy()
            assert app.state.project_workflow_dispatcher.blockers() == []
            assert app.state.project_run_scheduler.blockers() == []
            assert not list((tmp_path / 'tmp').glob('**/generation-*'))
            print('PM9_EXCEL_EVIDENCE=' + json.dumps({'batches': evidence, 'initialRecords': imported, 'accountAfter': await rows('A'), 'detailsAfter': await rows('D'), 'sourceHashBefore': original_hash, 'sourceHashAfter': hashlib.sha256(workbook_path.read_bytes()).hexdigest(), 'activeLeaseGroups': [sorted(group) for group in active_groups], 'fixtureRequests': requests.count('/fixture')}, ensure_ascii=False))
    finally:
        try:
            if server_task is not None:
                server.should_exit = True
                await asyncio.wait_for(server_task, 10)
        finally:
            listener.close()
            await app.router.on_shutdown[-1]()
