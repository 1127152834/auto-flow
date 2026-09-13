import base64
from time import monotonic, sleep
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.fixtures.workflow_control import literal, node, payload
from tests.fixtures.workflow_runs import workflow_runtime
from tests.unit.test_android_handoff import Runtime

ROOT = '/api/v1/workflows/runs'


def test_android_loop_uses_unique_execution_artifacts_and_handoffs(tmp_path):
    app, _, _ = workflow_runtime(tmp_path)
    service = app.state.android_service
    runtime = Runtime()
    runtime.connect = AsyncMock()
    runtime.inspect = AsyncMock(return_value={'androidStatus': 'ready'})
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
    runtime.command = AsyncMock(return_value=png)
    service.runtime = runtime
    identifier = str(uuid4())
    service.repository.save({'deviceId': identifier, 'name': 'loop test', 'runtimeId': 'test', 'control': 'idle', 'ownerRunId': None, 'generation': 0, 'width': 1, 'height': 1, 'imageId': 'test'})
    graph = payload([node('loop', 'loop', endNodeId='end', mode='count', source=literal(2)), node('screen', 'android_screenshot'), node('manual', 'android_manual', prompt='第 ${index} 轮', timeoutSeconds=30), node('end', 'loop_end', ownerNodeId='loop')], [('loop', 'body', 'screen'), ('screen', 'out', 'manual'), ('manual', 'out', 'end')])
    run_id = str(uuid4())
    body = {'runId': run_id, 'target': {'kind': 'android', 'deviceId': identifier}, **graph}
    with TestClient(app, headers={'x-autoflow-token': 'renderer'}) as client:
        assert client.post(ROOT + '/validate', json=body).status_code == 200
        response = client.post(ROOT, json=body)
        assert response.status_code == 201, response.text
        handoffs = []
        end = monotonic() + 15
        while monotonic() < end:
            record = client.get(ROOT + '/' + run_id).json()
            if record['state'] == 'waiting_manual' and record['handoff']['handoffId'] not in handoffs:
                handoffs.append(record['handoff']['handoffId'])
                assert record['handoff']['prompt'] == f'第 {len(handoffs)} 轮'
                response = client.post(f"{ROOT}/{run_id}/handoffs/{handoffs[-1]}/continue", json={'requestId': str(uuid4())})
                assert response.status_code == 202, response.text
            if record['state'] in {'succeeded', 'failed', 'cancelled'}:
                break
            sleep(.03)
        assert record['state'] == 'succeeded', record
        assert len(handoffs) == 2
        artifacts = client.get(f'{ROOT}/{run_id}/artifacts').json()['items']
        assert len(artifacts) == len({a['executionId'] for a in artifacts}) == 2
        assert [a['loopPath'][0]['iteration'] for a in artifacts] == [1, 2]
        assert record['artifactCount'] == 2 and record['executionCount'] == 9
        assert service.repository.get(identifier)['control'] == 'idle'
