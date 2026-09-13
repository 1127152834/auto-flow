from copy import deepcopy
from time import monotonic, sleep
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.fixtures.workflow_runs import workflow_runtime
from tests.unit.test_android_handoff import Runtime

ROOT = '/api/v1/workflows/runs'
HEADERS = {'x-autoflow-token': 'renderer'}


def test_two_manual_nodes_persist_old_receipts_and_hold_workspace_until_stop(tmp_path):
    app, _, _ = workflow_runtime(tmp_path)
    service = app.state.android_service
    runtime = Runtime()
    runtime.connect = AsyncMock()
    runtime.inspect = AsyncMock(return_value={'androidStatus': 'ready'})
    service.runtime = runtime
    device_id = str(uuid4())
    service.repository.save({'deviceId': device_id, 'name': 'test', 'runtimeId': 'test', 'control': 'idle', 'ownerRunId': None, 'generation': 0, 'width': 720, 'height': 1280, 'imageId': 'test'})
    nodes = [{'id': str(i), 'type': 'android_manual', 'label': f'Manual {i}', 'config': {'prompt': 'wait', 'timeoutSeconds': 30}} for i in range(2)]
    run_id = str(uuid4())
    payload = {'runId': run_id, 'target': {'kind': 'android', 'deviceId': device_id},
               'document': {'id': str(uuid4()), 'name': 'two handoffs', 'schemaVersion': 1, 'nodes': nodes, 'edges': [{'id': 'edge', 'source': '0', 'target': '1', 'sourceHandle': 'out', 'targetHandle': 'in'}], 'variables': []},
               'layout': {'nodes': {n['id']: {'x': i * 240, 'y': 100} for i, n in enumerate(nodes)}, 'viewport': {'x': 0, 'y': 0, 'zoom': 1}}}
    with TestClient(app, headers=HEADERS) as client:
        def waiting(node):
            end = monotonic() + 10
            while monotonic() < end:
                record = client.get(f'{ROOT}/{run_id}').json()
                if record['state'] == 'waiting_manual' and record['handoff']['nodeId'] == node:
                    return record
                assert record['state'] not in {'failed', 'cancelled'}, record
                sleep(.02)
            raise AssertionError('manual node not reached')
        assert client.get('/api/v1/android/devices', headers={'x-autoflow-token': 'wrong'}).status_code == 401
        assert client.post(ROOT, json=payload).status_code == 201
        first = waiting('0')
        assert first['profileId'] is None and first['targetName'] == 'test'
        assert client.post(ROOT, json={**payload, 'runId': str(uuid4())}).status_code == 409
        assert client.post('/internal/settings/quiesce', headers={'x-autoflow-host-token': 'host'}).status_code == 409
        old = f"{ROOT}/{run_id}/handoffs/{first['handoff']['handoffId']}"
        request_id = str(uuid4())
        assert client.post(old + '/continue', json={'requestId': request_id}).status_code == 202
        second = waiting('1')
        assert second['handoff']['handoffId'] != first['handoff']['handoffId']
        # Replayed receipt acknowledges the old decision without touching the new node.
        replay = client.post(old + '/continue', json={'requestId': request_id})
        assert replay.status_code == 202 and replay.json()['currentNodeId'] == '1'
        assert client.post(old + '/open', json={'requestId': request_id}).status_code == 409
        assert client.post(old + '/open', json={'requestId': str(uuid4())}).status_code == 409
        saved = deepcopy(app.state.workflow_run_service.get(run_id))
        assert saved['handoffReceipts'][first['handoff']['handoffId']][request_id] == 'continue'
        assert client.post(f'{ROOT}/{run_id}/stop').json()['state'] == 'cancelled'
        assert service.repository.get(device_id)['control'] == 'idle'
        # History replay remains idempotent after resource cleanup.
        assert client.post(old + '/continue', json={'requestId': request_id}).status_code == 202
