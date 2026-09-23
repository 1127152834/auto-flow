"""FX-04 version interleaving and partial failure through TCP and real workers."""

import asyncio
import json
import shutil
import socket
from itertools import pairwise
from uuid import uuid4

import httpx
import pytest
import uvicorn
from sqlalchemy import select

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.profiles.models import ProfileSpec
from autoflow.domain.project_data.identity import RecordKey, encode_record_key
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.project_run_models import (
    ProjectRecordLeaseRow,
    ProjectTaskRecordCursorRow,
)
from tests.integration.test_project_run_data_start import _input, _table
from tests.integration.test_workflow_real_cloakbrowser import (
    real_cloak_page as cloak_fixture,
)

real_cloak_page = cloak_fixture


@pytest.mark.asyncio
@pytest.mark.parametrize('human_edit', [False, True], ids=['own-version-progress', 'human-field-and-status-conflicts'])
async def test_real_write_versions_and_partial_failure(
    tmp_path, valid_profile_values, real_cloak_page, human_edit,
):
    executable, url, requests = real_cloak_page
    kernel = next(parent for parent in executable.parents if parent.name.startswith('chromium-'))
    shutil.copytree(kernel, tmp_path / 'data' / 'kernels' / kernel.name)
    app = create_app(Settings(data_dir=str(tmp_path), instance_id='write-conflict-real', instance_token='renderer'))
    server = uvicorn.Server(uvicorn.Config(app, lifespan='off', access_log=False, log_level='warning'))
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    server_task = None
    try:
        profile = app.state.profile_service.create(ProfileSpec.from_values({**valid_profile_values, 'headless': True, 'browser_version': kernel.name.removeprefix('chromium-')}))
        await app.state.project_workflow_dispatcher.startup()
        await app.state.project_run_scheduler.startup()
        server_task = asyncio.create_task(server.serve(sockets=[listener]))
        async with asyncio.timeout(10):
            while not server.started:
                await asyncio.sleep(.01)
        async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{listener.getsockname()[1]}', headers={'x-autoflow-token': 'renderer'}, trust_env=False, timeout=30) as client:
            async def api(method, path, body=None, status=200):
                response = await client.request(method, path, json=body, headers={'Idempotency-Key': str(uuid4())})
                assert response.status_code == status, response.text
                return response.json()

            project_id = (await api('POST', '/api/v1/projects', {'name': 'FX-04 人工版本竞争'}, 201))['projectId']
            prefix = f'/api/v1/projects/{project_id}'
            table, field = _table(app.state.session_factory, project_id, 'W01', '旧值')
            field_id = field['ref']['fieldId']
            table_path = prefix + f"/tables/{table['tableId']}"
            records_path = table_path + '/records?datasetGeneration=' + table['datasetGeneration']
            statuses = []
            for index, name in enumerate(['待处理', '已申请']):
                statuses.append((await api('POST', table_path + '/statuses', {'name': name, 'color': '#123456', 'order': index, 'expectedTableRevision': 2 + index}, 201))['statusId'])
            # Only initial business fixture facts are seeded. Task/Run/lease,
            # mutations, cursors, outputs and terminal outcomes are all real.
            with app.state.session_factory() as session:
                record = session.scalar(select(DataRecordRow).where(DataRecordRow.table_id == table['tableId']))
                record.content_revision, record.status_revision, record.link_revision = 7, 3, 2
                record.status_id = statuses[0]
                session.commit()
            before, = (await api('GET', records_path))['items']
            ref = before['ref']
            record_path = table_path + '/records/' + encode_record_key(RecordKey(**ref['recordKey']))
            grant = {'tableId': table['tableId'], 'datasetGeneration': table['datasetGeneration'], 'fieldIds': [field_id], 'readPurposes': []}

            def node(identity, kind, **data):
                return {'id': identity, 'type': kind, 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': kind, **data}}

            nodes = [
                node('inputs', 'project_data', operation='inputs', variableName='frozen', arguments={}),
                node('open', 'open_page', url=url, timeout=30),
                node('fill', 'input_text', selector='#field', text="{frozen[0]['values'][0]['value']}", clearBefore=True),
                node('read', 'get_element_info', selector='#field', attribute='value', variableName='browserValue'),
                node('create', 'project_data', operation='createRecord', variableName='created', tableGrant={**grant, 'operations': ['createRecord']}, arguments={'tableId': table['tableId'], 'datasetGeneration': table['datasetGeneration'], 'values': {field_id: '前序成功保留'}}),
                node('before-write', 'project_manual', reason='人工编辑窗口', timeoutSeconds=120),
                node('write', 'project_data', operation='updateRecord', variableName='written', tableGrant={**grant, 'operations': ['updateRecord']}, arguments={'recordRef': "{frozen[0]['recordRef']}", 'changes': {field_id: '任务新值'}, 'expectedContentRevision': "{frozen[0]['contentRevision']}"}),
            ]
            if human_edit:
                nodes.append(node('field-conflict', 'project_manual', reason='字段冲突处置', timeoutSeconds=120))
            nodes.append(node('status', 'project_data', operation='setRecordStatus', variableName='changed', tableGrant={**grant, 'operations': ['setRecordStatus']}, arguments={
                'recordRef': "{frozen[0]['recordRef']}", 'statusId': statuses[1], 'expectedStatusRevision': "{frozen[0]['statusRevision']}",
                'expectedContentRevisionWhenDerived': "{frozen[0]['contentRevision']}" if human_edit else "{written['contentRevision']}", 'allowedFrom': [statuses[0]],
            }))
            if human_edit:
                nodes.append(node('status-conflict', 'project_manual', reason='状态冲突处置', timeoutSeconds=120))
            nodes.extend([
                node('before-failure', 'project_manual', reason='核对已提交效果', timeoutSeconds=120),
                node('failure', 'click_element', selector='#missing-after-writes', timeout=1),
                node('end', 'project_end', retainEnvironment={'enabled': False}),
            ])
            edges = [{'id': str(uuid4()), 'source': left['id'], 'target': right['id'], **({'sourceHandle': 'error'} if human_edit and left['id'] in {'write', 'status'} else {})} for left, right in pairwise(nodes)]
            workflow = await api('POST', '/api/workflows', {'id': str(uuid4()), 'clientRequestId': str(uuid4()), 'name': '版本与部分失败', 'variables': [], 'nodes': nodes, 'edges': edges}, 201)
            automation = await api('POST', prefix + '/automations', {
                'name': '版本与部分失败', 'description': '', 'workflowId': workflow['id'], 'parameterSchema': [], 'inputPlan': {'inputs': [_input(project_id, table, field, 'W01')]},
                'environmentPolicy': {'source': 'newFromProfile', 'profileId': profile.id, 'proxyOverride': {'mode': 'none'}, 'modelProviderId': None},
                'runPolicy': {'maxTasks': 1, 'concurrency': 1, 'maxLiveInstances': 1, 'continueAfterFailure': False, 'automaticExecutionTimeoutSeconds': 60, 'manualDeadlineSeconds': 120},
            }, 201)
            accepted = await api('POST', prefix + f"/automations/{automation['automationId']}/batches", {'expectedAutomationRevision': automation['managementRevision'], 'parameters': {}, 'maxTasks': 1, 'concurrency': 1}, 202)
            batch_id = accepted['operation']['result']['batch']['batchId']
            batch_path = prefix + '/batches/' + batch_id

            async def waiting(reason):
                async with asyncio.timeout(60):
                    while True:
                        items = (await api('GET', prefix + '/manual-items'))['items']
                        found = next((item for item in items if item['status'] == 'waiting' and item['reason'] == reason), None)
                        if found:
                            return found
                        detail = await api('GET', batch_path)
                        assert detail['batch']['status'] not in {'completed', 'failed', 'interrupted', 'stopped'}, detail
                        await asyncio.sleep(.05)

            async def resume(item):
                await api('POST', prefix + f"/manual-items/{item['manualItemId']}/resume", {'checkpointRevision': item['checkpointRevision'], 'expectedStatusRevision': item['statusRevision']}, 202)

            checkpoint = await waiting('人工编辑窗口')
            task_path = prefix + '/tasks/' + checkpoint['taskId']
            original_input = (await api('GET', task_path))['inputSnapshot']
            frozen, = original_input['inputs']
            assert frozen['recordRef'] == ref and [frozen[name] for name in ('contentRevision', 'statusRevision', 'linkRevision')] == [7, 3, 2]
            assert frozen['values'][0]['value'] == '旧值'
            with app.state.session_factory() as session:
                held = list(session.scalars(select(ProjectRecordLeaseRow)))
                assert len(held) == 2 and all(lease.state == 'held' and lease.task_id == checkpoint['taskId'] for lease in held)
            if human_edit:
                edited = await api('PATCH', record_path, {'datasetGeneration': table['datasetGeneration'], 'recordKeyType': ref['recordKey']['type'], 'values': [{'fieldId': field_id, 'value': '人工新值'}], 'expectedContentRevision': 7})
                assert edited['contentRevision'] == 8 and edited['statusRevision'] == 3
            await resume(checkpoint)
            if human_edit:
                for reason, node_id in [('字段冲突处置', 'write'), ('状态冲突处置', 'status')]:
                    conflict = await waiting(reason)
                    attempts = (await api('GET', task_path + '/node-attempts'))['items']
                    failed, = [attempt for attempt in attempts if attempt['nodeId'] == node_id]
                    assert failed['status'] == 'failed' and failed['error']['code'] == 'REVISION_CONFLICT', attempts
                    assert (await api('GET', task_path))['inputSnapshot'] == original_input
                    await resume(conflict)
            checkpoint = await waiting('核对已提交效果')
            committed = (await api('GET', records_path))['items']
            current, = [row for row in committed if row['ref'] == ref]
            created, = [row for row in committed if row['ref'] != ref]
            assert current['values'][0]['value'] == ('人工新值' if human_edit else '任务新值')
            assert [current[name] for name in ('contentRevision', 'statusRevision', 'linkRevision')] == [8, 3 if human_edit else 4, 2]
            assert current['statusId'] == statuses[0 if human_edit else 1]
            assert created['values'][0]['value'] == '前序成功保留' and created['contentRevision'] == 1
            assert created['statusId'] is None and created['currentEnvironmentId'] is None
            with app.state.session_factory() as session:
                cursor, = [row for row in session.scalars(select(ProjectTaskRecordCursorRow)) if row.record_ref == ref]
                cursor_versions = [cursor.content_revision, cursor.status_revision, cursor.link_revision]
                assert cursor_versions == ([7, 3, 2] if human_edit else [8, 4, 2])
            await resume(checkpoint)
            async with asyncio.timeout(30):
                while True:
                    detail = await api('GET', batch_path)
                    if detail['batch']['status'] in {'completed', 'failed', 'interrupted', 'stopped'}:
                        break
                    await asyncio.sleep(.05)
            assert detail['statusCounts']['failed'] == detail['batch']['createdTaskCount'] == 1
            assert detail['batch']['activeTaskCount'] == 0
            assert (await api('GET', records_path))['items'] == committed
            task = await api('GET', task_path)
            assert task['inputSnapshot'] == original_input
            assert task['task']['status'] == 'failed' and task['run']['error']['code'] == 'WORKFLOW_FAILED'
            expected_writes = ['recordCreated'] if human_edit else ['recordCreated', 'recordUpdated', 'statusChange']
            assert [write['kind'] for write in task['dataWrites']] == expected_writes
            assert all(write['outcome'] == 'succeeded' for write in task['dataWrites'])
            outputs = {item['name']: item['value'] for item in (await api('GET', task_path + '/outputs'))['items']}
            assert outputs['browserValue'] == '旧值' and outputs['created']['ref'] == created['ref']
            assert ('written' in outputs) == ('changed' in outputs) == (not human_edit)
            attempts = (await api('GET', task_path + '/node-attempts'))['items']
            failed, = [attempt for attempt in attempts if attempt['nodeId'] == 'failure']
            assert failed['status'] == 'failed' and failed['error']['code'] == 'WORKFLOW_NODE_TIMEOUT'
            expected_failures = {'write', 'status', 'failure'} if human_edit else {'failure'}
            assert {attempt['nodeId'] for attempt in attempts if attempt['status'] == 'failed'} == expected_failures
            assert all(attempt['status'] == 'succeeded' for attempt in attempts if attempt['nodeId'] not in expected_failures)
            assert not any(attempt['nodeId'] == 'end' for attempt in attempts)
            with app.state.session_factory() as session:
                leases = list(session.scalars(select(ProjectRecordLeaseRow)))
                assert len(leases) == 2 and all(lease.state == 'released' and lease.released_at is not None for lease in leases)
            assert requests.count('/fixture') == 1
            assert not app.state.project_workflow_worker_manager.busy()
            assert app.state.project_workflow_dispatcher.blockers() == app.state.project_run_scheduler.blockers() == []
            assert not list((tmp_path / 'tmp').glob('**/generation-*'))
            print('PM9_WRITE_CONFLICT_EVIDENCE=' + json.dumps({'humanEdit': human_edit, 'batch': detail, 'task': task, 'recordBefore': before, 'recordsAfter': committed, 'outputs': outputs, 'attempts': attempts, 'cursorVersions': cursor_versions, 'releasedLeaseCount': len(leases)}, ensure_ascii=False))
    finally:
        try:
            if server_task is not None:
                server.should_exit = True
                await asyncio.wait_for(server_task, 10)
        finally:
            listener.close()
            await app.router.on_shutdown[-1]()
