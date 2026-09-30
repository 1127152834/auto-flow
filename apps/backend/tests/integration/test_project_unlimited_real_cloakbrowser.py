"""Unlimited final-state reuse and public stop through TCP HTTP and real workers."""

import asyncio
import json
import shutil
import socket
from datetime import datetime
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
from autoflow.infrastructure.database.project_run_models import ProjectRecordLeaseRow
from tests.integration.test_project_run_data_start import _input, _table
from tests.integration.test_workflow_real_cloakbrowser import (
    real_cloak_page as cloak_fixture,
)

real_cloak_page = cloak_fixture


@pytest.mark.asyncio
async def test_unlimited_final_record_reclaim_stops_after_five_successes(
    tmp_path, valid_profile_values, real_cloak_page, monkeypatch,
):
    executable, url, requests = real_cloak_page
    kernel = next(parent for parent in executable.parents if parent.name.startswith('chromium-'))
    shutil.copytree(kernel, tmp_path / 'data' / 'kernels' / kernel.name)
    app = create_app(Settings(data_dir=str(tmp_path), instance_id='unlimited-real', instance_token='renderer'))
    server = uvicorn.Server(uvicorn.Config(app, lifespan='off', access_log=False, log_level='warning'))
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    server_task = None
    manager = app.state.project_workflow_worker_manager
    real_run = manager.run
    starts = []

    async def observe_one_owner(**kwargs):
        with app.state.session_factory() as session:
            leases = list(session.scalars(select(ProjectRecordLeaseRow)))
            held = [lease for lease in leases if lease.state == 'held']
            assert len(held) == 1 and held[0].run_id == kwargs['run_id']
            assert all(lease.state == 'released' for lease in leases if lease not in held)
            starts.append({'runId': kwargs['run_id'], 'recordRef': held[0].record_ref})
        return await real_run(**kwargs)

    monkeypatch.setattr(manager, 'run', observe_one_owner)
    try:
        profile = app.state.profile_service.create(ProfileSpec.from_values({**valid_profile_values, 'headless': True, 'browser_version': kernel.name.removeprefix('chromium-')}))
        await app.state.project_workflow_dispatcher.startup()
        await app.state.project_run_scheduler.startup()
        server_task = asyncio.create_task(server.serve(sockets=[listener]))
        async with asyncio.timeout(10):
            while not server.started:
                await asyncio.sleep(.01)
        async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{listener.getsockname()[1]}', headers={'x-autoflow-token': 'renderer'}, trust_env=False, timeout=30) as client:
            async def api(method, path, body=None, status=200, key=None):
                response = await client.request(method, path, json=body, headers={'Idempotency-Key': key or str(uuid4())})
                assert response.status_code == status, response.text
                return response.json()

            project_id = (await api('POST', '/api/v1/projects', {'name': '不限任务最终态复用'}, 201))['projectId']
            prefix = f'/api/v1/projects/{project_id}'
            # Real local table fixture; no synthetic Task/Run/lease or worker outcome.
            table, field = _table(app.state.session_factory, project_id, '账号', 'A01')
            table_path = prefix + f"/tables/{table['tableId']}"
            record_path = table_path + '/records?datasetGeneration=' + table['datasetGeneration']
            original = (await api('GET', record_path))['items'][0]
            completed = await api('POST', table_path + '/statuses', {'name': '已完成', 'color': '#123456', 'order': 0, 'expectedTableRevision': 2}, 201)
            record_key = original['ref']['recordKey']
            await api('PUT', table_path + '/records/' + encode_record_key(RecordKey(**record_key)) + '/status', {'datasetGeneration': table['datasetGeneration'], 'recordKeyType': record_key['type'], 'statusId': completed['statusId'], 'expectedStatusRevision': 1})
            before = (await api('GET', record_path))['items']
            assert len(before) == 1 and before[0]['statusRevision'] == 2
            input_spec = _input(project_id, table, field, 'A01')
            input_spec['filter'] = {'type': 'status', 'operator': 'eq', 'statusId': completed['statusId']}

            def node(identity, kind, **data):
                return {'id': identity, 'type': kind, 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': kind, **data}}

            nodes = [
                node('inputs', 'project_data', operation='inputs', variableName='frozen', arguments={}),
                node('open', 'open_page', url=url, timeout=30),
                node('fill', 'input_text', selector='#field', text="{frozen[0]['values'][0]['value']}", clearBefore=True),
                node('read', 'get_element_info', selector='#field', attribute='value', variableName='browserValue'),
                node('manual', 'project_manual', reason='观察下一次领取；第六次公开停止', timeoutSeconds=120),
                node('after', 'set_variable', variableName='afterResume', variableValue='completed'),
                node('end', 'project_end', retainEnvironment={'enabled': False}),
            ]
            workflow = await api('POST', '/api/workflows', {'id': str(uuid4()), 'clientRequestId': str(uuid4()), 'name': '不限最终态复用', 'variables': [], 'nodes': nodes, 'edges': [{'id': str(uuid4()), 'source': a['id'], 'target': b['id']} for a, b in pairwise(nodes)]}, 201)
            automation = await api('POST', prefix + '/automations', {
                'name': '不限最终态复用', 'description': '', 'workflowId': workflow['id'], 'parameterSchema': [], 'inputPlan': {'inputs': [input_spec]},
                'environmentPolicy': {'source': 'newFromProfile', 'profileId': profile.id, 'proxyOverride': {'mode': 'none'}, 'modelProviderId': None},
                'runPolicy': {'maxTasks': 1, 'concurrency': 1, 'maxLiveInstances': 1, 'continueAfterFailure': False, 'automaticExecutionTimeoutSeconds': 60, 'manualDeadlineSeconds': 120},
            }, 201)
            start_key = str(uuid4())
            start_body = {'expectedAutomationRevision': automation['managementRevision'], 'parameters': {}, 'maxTasks': None, 'concurrency': 1}
            start_path = prefix + f"/automations/{automation['automationId']}/batches"
            accepted = await api('POST', start_path, start_body, 202, start_key)
            batch_id = accepted['operation']['result']['batch']['batchId']
            batch_path = prefix + '/batches/' + batch_id
            resumed = set()
            async with asyncio.timeout(180):
                while True:
                    detail = await api('GET', batch_path)
                    assert detail['batch']['requestedCount'] is None
                    assert detail['batch']['status'] not in {'completed', 'failed', 'interrupted', 'stopped'}, detail
                    items = (await api('GET', prefix + '/manual-items'))['items']
                    waiting = next((item for item in items if item['status'] == 'waiting' and item['manualItemId'] not in resumed), None)
                    if waiting:
                        if len(resumed) == 5:
                            detail = await api('GET', batch_path)
                            assert detail['statusCounts']['succeeded'] == 5
                            assert detail['batch']['createdTaskCount'] == 6
                            break
                        await api('POST', prefix + f"/manual-items/{waiting['manualItemId']}/resume", {'checkpointRevision': waiting['checkpointRevision'], 'expectedStatusRevision': waiting['statusRevision']}, 202)
                        resumed.add(waiting['manualItemId'])
                    await asyncio.sleep(.05)
            stop_key = str(uuid4())
            stop_body = {'expectedStatusRevision': detail['batch']['statusRevision'], 'reason': '五次成功复用后公开停止'}
            stopped = await api('POST', batch_path + '/stop', stop_body, 202, stop_key)
            stop_id = stopped['operation']['operationId']
            async with asyncio.timeout(30):
                while True:
                    final = await api('GET', batch_path)
                    operation = await api('GET', prefix + '/operations/by-idempotency-key/' + stop_key)
                    if final['batch']['status'] == 'stopped' and operation['status'] == 'succeeded':
                        break
                    await asyncio.sleep(.05)
            assert final['batch']['createdTaskCount'] == 6 and final['batch']['activeTaskCount'] == 0
            assert final['statusCounts']['succeeded'] == 5 and final['statusCounts']['cancelled'] == 1
            assert final['batch']['claimGateState'] == 'closed'
            assert (await api('GET', record_path))['items'] == before
            tasks = (await api('GET', prefix + '/tasks?batchId=' + batch_id))['items']
            tasks.sort(key=lambda task: task['taskOrdinal'])
            assert [task['status'] for task in tasks] == ['succeeded'] * 5 + ['cancelled']
            assert len({task['runId'] for task in tasks}) == len({task['taskId'] for task in tasks}) == 6
            evidence = []
            for index, task in enumerate(tasks):
                path = prefix + '/tasks/' + task['taskId']
                snapshot = (await api('GET', path))['inputSnapshot']['inputs']
                assert len(snapshot) == 1 and snapshot[0]['recordRef'] == before[0]['ref']
                assert snapshot[0]['statusRevision'] == 2 and snapshot[0]['contentRevision'] == 1
                outputs = (await api('GET', path + '/outputs'))['items']
                assert next(output['value'] for output in outputs if output['name'] == 'browserValue') == 'A01'
                attempts = (await api('GET', path + '/node-attempts'))['items']
                if index < 5:
                    assert len(attempts) == 7 and all(attempt['status'] == 'succeeded' for attempt in attempts)
                else:
                    assert not any(attempt['nodeId'] in {'after', 'end'} for attempt in attempts)
                evidence.append({'task': task, 'frozenInput': snapshot, 'attempts': attempts})
            cancelled_manual = await api('GET', prefix + f"/manual-items/{waiting['manualItemId']}")
            assert cancelled_manual['status'] == 'cancelled'
            replay = await api('POST', batch_path + '/stop', stop_body, 202, stop_key)
            assert replay['operation']['operationId'] == operation['operationId'] == stop_id
            assert replay['operation']['status'] == 'succeeded'
            # Generic lookup types batch dates; command results retain JSON dates.
            for receipt in (replay['operation'], operation):
                for name in ('createdAt', 'completedAt'):
                    value = receipt['result']['batch'][name]
                    if value is not None:
                        receipt['result']['batch'][name] = datetime.fromisoformat(value).isoformat()
            assert replay['operation'] == operation
            start_replay = await api('POST', start_path, start_body, 202, start_key)
            assert start_replay['operation']['operationId'] == accepted['operation']['operationId']
            for _ in range(3):
                # Exercise the actual scheduled continuation after terminal admission.
                await app.state.project_run_scheduler.tick()
                current = (await api('GET', prefix + '/tasks?batchId=' + batch_id))['items']
                assert sorted(current, key=lambda task: task['taskOrdinal']) == tasks
            with app.state.session_factory() as session:
                leases = list(session.scalars(select(ProjectRecordLeaseRow)))
                assert len(leases) == 6 and len({lease.lease_key for lease in leases}) == 1
                assert all(lease.state == 'released' and lease.released_at is not None for lease in leases)
            assert len(starts) == 6 and all(start['recordRef'] == before[0]['ref'] for start in starts)
            assert requests.count('/fixture') == 6
            assert not manager.busy()
            assert app.state.project_workflow_dispatcher.blockers() == []
            assert app.state.project_run_scheduler.blockers() == []
            assert not list((tmp_path / 'tmp').glob('**/generation-*'))
            print('PM9_UNLIMITED_EVIDENCE=' + json.dumps({'batch': final, 'stopOperation': operation, 'recordBefore': before, 'recordAfter': (await api('GET', record_path))['items'], 'tasks': evidence, 'workerStarts': starts, 'resumedManualCount': len(resumed), 'cancelledManual': waiting['manualItemId'], 'releasedLeaseCount': len(leases), 'fixtureRequests': requests.count('/fixture')}, ensure_ascii=False))
    finally:
        try:
            if server_task is not None:
                server.should_exit = True
                await asyncio.wait_for(server_task, 10)
        finally:
            listener.close()
            await app.router.on_shutdown[-1]()
