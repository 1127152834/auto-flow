import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from autoflow.application.android.management import AndroidManagement
from autoflow.domain.android.ports import AndroidError
from autoflow.providers.android.mac_runtime import LABEL, MacAndroidRuntime
from autoflow.providers.android.management import manage


class Repository:
    def __init__(self):
        self.records = {}

    def get(self, identifier):
        if identifier not in self.records:
            raise AndroidError('ANDROID_NOT_FOUND', 'missing', 404)
        return deepcopy(self.records[identifier])

    def save(self, device):
        self.records[device['deviceId']] = deepcopy(device)


class Runtime:
    def __init__(self):
        self.locked = False
        self.gate = asyncio.Event()
        self.gate.set()
        self.calls = []
        self.fail = False

    def lock(self):
        if self.locked:
            raise AndroidError('ANDROID_RUNTIME_BUSY', 'busy')
        self.locked = True

    def unlock(self):
        self.locked = False

    def new_device(self, config):
        return {**config, 'control': 'idle', 'ownerRunId': None}

    async def manage(self, device, request, stage, save):
        self.calls.append(request['action'])
        stage('等待 Android 就绪')
        await self.gate.wait()
        if self.fail:
            raise AndroidError('ANDROID_PARTIAL_FAILURE', '保留已创建的数据，等待核实')
        device['androidStatus'] = 'ready'
        if request['action'] == 'delete':
            device['deleted'] = request['deleteData']
            device['dataRetained'] = not request['deleteData']
        save()


def config():
    return {'deviceId': str(uuid4()), 'name': 'test', 'imageId': 'sha256:' + 'a' * 64, 'width': 720, 'height': 1280, 'cpu': 1, 'memoryMb': 768, 'dpi': 320, 'start': True}


def request(action, delete=False):
    return {'requestId': str(uuid4()), 'action': action, 'deleteData': delete}


@pytest.mark.asyncio
async def test_creation_is_durable_before_work_and_retries_never_create_twice():
    repo, runtime = Repository(), Runtime()
    service = AndroidManagement(repo, runtime)
    runtime.gate.clear()
    c = config()
    first = service.create(c)
    assert repo.get(c['deviceId'])['operation']['state'] == 'running'
    assert service.create(c) == first
    with pytest.raises(AndroidError):
        service.create({**c, 'name': 'changed'})
    with pytest.raises(AndroidError):
        service.create(config())
    assert service.busy()
    runtime.gate.set()
    await service.task
    assert runtime.calls == ['create'] and not runtime.locked
    assert repo.get(c['deviceId'])['control'] == 'idle'


@pytest.mark.asyncio
async def test_partial_failure_stays_reviewable_and_requires_explicit_recovery():
    repo, runtime = Repository(), Runtime()
    service = AndroidManagement(repo, runtime)
    c = config()
    runtime.fail = True
    service.create(c)
    await service.task
    assert repo.get(c['deviceId'])['control'] == 'recovery_required'
    with pytest.raises(AndroidError):
        service.operate(c['deviceId'], request('start'))
    runtime.fail = False
    service.operate(c['deviceId'], request('recover'))
    await service.task
    command = request('delete')
    service.operate(c['deviceId'], command)
    await service.task
    assert repo.get(c['deviceId'])['dataRetained'] and not repo.get(c['deviceId'])['deleted']
    service.operate(c['deviceId'], command)
    assert runtime.calls.count('delete') == 1
    service.operate(c['deviceId'], request('delete', True))
    await service.task
    assert repo.get(c['deviceId'])['deleted']
    with pytest.raises(AndroidError):
        service.operate(c['deviceId'], request('start'))


@pytest.mark.asyncio
async def test_shutdown_marks_interrupted_and_busy_device_cannot_be_mutated():
    repo, runtime = Repository(), Runtime()
    service = AndroidManagement(repo, runtime)
    c = config()
    runtime.gate.clear()
    service.create(c)
    await asyncio.sleep(0)
    await service.shutdown()
    assert repo.get(c['deviceId'])['operation']['state'] == 'interrupted'
    assert repo.get(c['deviceId'])['control'] == 'recovery_required'
    assert not runtime.locked
    d = repo.get(c['deviceId']); d.update(ownerRunId='other', control='manual'); repo.save(d)
    other = AndroidManagement(repo, runtime)
    with pytest.raises(AndroidError):
        other.operate(c['deviceId'], request('delete', True))


@pytest.mark.asyncio
async def test_delete_refuses_foreign_volume_before_any_mutation(tmp_path, monkeypatch):
    runtime = MacAndroidRuntime(tmp_path, tmp_path / 'workspace')
    c = config()
    device = runtime.new_device(c)
    container = {'Config': {'Labels': {LABEL: runtime.workspace_id, 'io.autoflow.android.device': c['deviceId']}}, 'Mounts': [{'Name': device['volumeId'], 'Destination': '/data'}]}
    from autoflow.providers.android import management
    monkeypatch.setattr(management, 'objects', AsyncMock(side_effect=[[container], [{'Labels': {LABEL: 'foreign'}}]]))
    mutation = AsyncMock()
    monkeypatch.setattr(management, 'mutation', mutation)
    with pytest.raises(AndroidError, match='归属'):
        await manage(runtime, device, request('delete', True), lambda _: None, lambda: None)
    mutation.assert_not_called()


@pytest.mark.asyncio
async def test_restoration_records_intended_container_name_before_a_lost_create_response(tmp_path, monkeypatch):
    from autoflow.providers.android import management
    runtime = MacAndroidRuntime(tmp_path, tmp_path / 'workspace')
    device = runtime.new_device(config())
    device.update(containerId='old-removed-id', dataRetained=True)
    monkeypatch.setattr(management, 'verify', AsyncMock(return_value=([], [{}])))
    monkeypatch.setattr(management, 'images', AsyncMock(return_value=[{'id': device['imageId']}]))
    saved = []
    async def lost(*_args, **_kwargs):
        assert saved[-1]['containerId'] == 'autoflow-android-' + device['deviceId']
        raise TimeoutError
    monkeypatch.setattr(management, 'mutation', lost)
    with pytest.raises(TimeoutError):
        await manage(runtime, device, request('start'), lambda _: None, lambda: saved.append(deepcopy(device)))
