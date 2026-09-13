import asyncio
from copy import deepcopy
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.fixtures.workflow_runs import workflow_runtime
from tests.fixtures.workflows import workflow_payload

ROOT = '/api/v1/workflows/inspection-sessions'


class Worker:
    def __init__(self):
        self.started, self.finish = asyncio.Event(), asyncio.Event()
        self.active = False
        self.cleanup_failure = False
        self.count = 0
        self.picks = {}

    def busy(self):
        return self.active

    async def execute(self, session_id, prepared, profile, executable, proxy, license_key, on_event):
        self.active = True
        self.count += 1
        await on_event({'type': 'inspection', 'pages': [{'pageId': 'page', 'revision': 0, 'url': 'about:blank', 'title': ''}], 'targetPageId': 'page', 'pick': None})
        self.started.set()
        await self.finish.wait()
        return {'state': 'succeeded', 'error': None}

    async def stop(self, session_id):
        if self.cleanup_failure:
            raise RuntimeError('cleanup failed')
        self.active = False
        self.finish.set()

    async def shutdown(self):
        await self.stop('')

    async def command(self, session_id, command):
        if command['action'] == 'pick':
            item = {'requestId': command['requestId'], 'pageId': command['pageId'], 'pageRevision': 0,
                    'state': 'pending', 'result': None, 'error': None}
            self.picks[item['requestId']] = item
            return deepcopy(item)
        if command['action'] == 'get-pick':
            return deepcopy(self.picks[command['requestId']])
        if command['action'] == 'cancel':
            self.picks[command['requestId']]['state'] = 'cancelled'
            return deepcopy(self.picks[command['requestId']])
        if command['action'] == 'test':
            return {'pageId': command['pageId'], 'pageRevision': 0, 'selector': command['selector'],
                    'framePath': command['framePath'], 'count': 0, 'first': None, 'truncated': False}
        return {}


def runtime(tmp_path):
    app, profile, _runs = workflow_runtime(tmp_path)
    inspection = app.state.workflow_inspection_service
    worker = Worker()
    inspection._launcher = worker
    inspection._installed = app.state.workflow_run_service._installed_kernels
    return app, profile, worker


def test_inspection_contract_lifecycle_auth_idempotency_and_run_exclusion(tmp_path):
    app, profile, worker = runtime(tmp_path)
    with TestClient(app, headers={'x-autoflow-token': 'renderer'}) as client:
        body = {'sessionId': str(uuid4()), 'profileId': profile.id}
        assert client.post(ROOT, json=body, headers={'x-autoflow-token': 'bad'}).status_code == 401
        assert client.get(ROOT).json() is None
        assert client.post(ROOT, json=body).status_code == 201
        client.portal.call(worker.started.wait)
        record = client.get(ROOT).json()
        assert record['state'] == 'ready' and record['headless'] is False
        assert client.post(ROOT, json=body).json()['sessionId'] == body['sessionId']
        assert worker.count == 1
        assert client.post(ROOT, json={**body, 'profileId': 'other'}).status_code == 409
        assert client.post(ROOT, json={**body, 'sessionId': str(uuid4())}).status_code == 409
        endpoint = ROOT + '/' + body['sessionId']
        assert client.post('/api/v1/workflows/runs', json={'runId': str(uuid4()), **workflow_payload(), 'profileId': profile.id}).status_code == 409
        assert client.delete('/api/v1/profiles/' + profile.id).status_code == 409
        assert client.post('/internal/settings/quiesce', headers={'x-autoflow-host-token': 'host'}).status_code == 409
        assert client.get('/api/v1/workflows/runs').json()['items'] == []
        pick = {'requestId': str(uuid4()), 'pageId': 'page'}
        assert client.post(endpoint + '/picks', json=pick).status_code == 200
        before = client.get(endpoint + '/picks/' + pick['requestId']).json()
        assert client.get(endpoint + '/picks/' + pick['requestId']).json() == before
        assert client.post(endpoint + '/picks', json={**pick, 'pageId': 'different'}).status_code == 409
        assert client.post(endpoint + '/picks/' + pick['requestId'] + '/cancel').json()['state'] == 'cancelled'
        result = client.post(endpoint + '/test-selector', json={'pageId': 'page', 'selector': '#{target}', 'framePath': ['${frame}'], 'variables': [
            {'name': 'target', 'type': 'string', 'value': 'ready'}, {'name': 'frame', 'type': 'string', 'value': '#outer'},
        ]})
        assert result.status_code == 200, result.text
        assert result.json()['selector'] == '#ready' and result.json()['framePath'] == ['#outer']
        assert client.post(endpoint + '/test-selector', json={'pageId': 'page', 'selector': '{missing}'}).status_code == 422
        assert client.post(endpoint + '/page', json={'pageId': 'page', 'url': 'javascript:alert(1)'}).status_code == 422
        worker.cleanup_failure = True
        assert client.post(endpoint + '/close').status_code == 503
        assert client.get(ROOT).json()['state'] == 'closing'
        assert app.state.workflow_inspection_service.busy()
        worker.cleanup_failure = False
        assert client.post(endpoint + '/close').json()['state'] == 'closed'
        assert client.post(endpoint + '/close').json()['state'] == 'closed'
        assert not app.state.workflow_inspection_service.busy()
        assert client.post('/internal/settings/quiesce', headers={'x-autoflow-host-token': 'host'}).status_code == 200
        assert client.post(ROOT, json={**body, 'sessionId': str(uuid4())}).status_code == 409


def test_run_admission_blocks_inspection(tmp_path):
    app, profile, worker = runtime(tmp_path)
    with TestClient(app, headers={'x-autoflow-token': 'renderer'}) as client:
        run = client.post('/api/v1/workflows/runs', json={'runId': str(uuid4()), **workflow_payload(), 'profileId': profile.id}).json()
        assert client.post(ROOT, json={'sessionId': str(uuid4()), 'profileId': profile.id}).status_code == 409
        assert worker.count == 0
        client.post('/api/v1/workflows/runs/' + run['runId'] + '/stop')
