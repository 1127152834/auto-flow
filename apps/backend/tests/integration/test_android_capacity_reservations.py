"""Real repositories/locks/runtime journal; only Docker/Lima IO is simulated."""
import json
import re
import shlex
from uuid import uuid4

import pytest

from autoflow.application.android.management import AndroidManagement
from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.providers.android import mac_runtime as mac
from autoflow.providers.android import management


@pytest.fixture
def environment(tmp_path, monkeypatch):
    class Environment:
        def __init__(self):
            self.containers = {}
            self.markers = {}
            self.timeouts = set()
            self.commands = []
            self.sessions = []

        def device(self, workspace, memory=2048):
            root = tmp_path / 'runtime'
            path = tmp_path / workspace
            path.mkdir(exist_ok=True)
            migrate_database(path / 'state.db')
            sessions = create_session_factory(path / 'state.db')
            self.sessions.append(sessions)
            repository = SqlAlchemyDeviceRepository(sessions)
            runtime = mac.MacAndroidRuntime(root, path)
            device = runtime.new_device({'deviceId': str(uuid4()), 'name': workspace, 'imageId': 'sha256:' + 'a' * 64, 'width': 720, 'height': 1280, 'dpi': 320, 'cpu': 1, 'memoryMb': memory})
            device.update(containerId=uuid4().hex * 2, androidStatus='stopped')
            self.containers[device['containerId']] = {
                'Id': device['containerId'], 'Name': '/autoflow-android-' + device['deviceId'], 'Image': device['imageId'],
                'Config': {'Labels': {mac.LABEL: runtime.workspace_id, 'io.autoflow.android.device': device['deviceId']}},
                'HostConfig': {'Memory': memory * 1024**2}, 'State': {'Status': 'exited'},
                'Mounts': [{'Name': device['volumeId'], 'Destination': '/data'}], 'NetworkSettings': {'Ports': {}},
            }
            repository.save(device)
            return runtime, repository, device

        async def docker(self, *args, **_kwargs):
            if args[0] == 'info':
                result = {'NCPU': 4, 'MemTotal': 4 * 1024**3}
            elif args[:2] == ('ps', '-q'):
                return '\n'.join(key for key, value in self.containers.items() if value['State']['Status'] == 'running').encode()
            elif args[:2] == ('ps', '-a'):
                return '\n'.join(key + ' ' + value['Name'][1:] for key, value in self.containers.items()).encode()
            elif args[0] == 'inspect':
                result = [next(value for key, value in self.containers.items() if target in (key, value['Name'][1:])) for target in args[1:]]
            elif args[:2] == ('volume', 'ls'):
                return '\n'.join(value['Mounts'][0]['Name'] for value in self.containers.values()).encode()
            elif args[:2] == ('volume', 'inspect'):
                result = [{'Labels': value['Config']['Labels']} for value in self.containers.values() if value['Mounts'][0]['Name'] == args[2]]
            elif args[0] == 'exec':
                return b'1\n'
            else:
                raise AssertionError(args)
            return json.dumps(result).encode()

        async def run(self, argv, *_args, **_kwargs):
            if argv[-2] == 'cat':
                if argv[-1] not in self.markers:
                    raise AndroidError('ANDROID_COMMAND_FAILED', 'marker not available', 502)
                return self.markers[argv[-1]]
            script = argv[-1]
            command = shlex.split(script.split('; rc=$?;', 1)[0])
            assert command[0] == 'docker'
            self.commands.append(command)
            identifier = command[-1]
            if identifier in self.timeouts:
                if command[1] == 'stop':
                    self.containers[identifier]['State']['Status'] = 'exited'
                raise TimeoutError('response lost while command completion is unknown')
            self.containers[identifier]['State']['Status'] = 'running' if command[1] in {'start', 'restart'} else 'exited'
            marker = re.search(r'/tmp/autoflow-lifecycle-[a-f0-9]{32}', script)[0]
            self.markers[marker] = b'0\n'
            return b''

    env = Environment()
    monkeypatch.setattr(management, 'docker', env.docker)
    monkeypatch.setattr(management, 'run', env.run)
    monkeypatch.setattr(mac, 'docker', env.docker)
    monkeypatch.setattr(mac.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(management, 'images', lambda *_args: _image())
    yield env
    for sessions in env.sessions:
        sessions.dispose()


async def _image():
    return [{'id': 'sha256:' + 'a' * 64}]


async def operate(runtime, repository, device, action):
    service = AndroidManagement(repository, runtime)
    service.operate(device['deviceId'], {'requestId': str(uuid4()), 'action': action, 'deleteData': False})
    await service.task
    return repository.get(device['deviceId'])


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['start', 'restart', 'stop'])
async def test_unknown_lifecycle_keeps_shared_budget_across_runtime_restart(environment, action):
    runtime, repository, first = environment.device('first')
    other, _, second = environment.device('second')
    if action != 'start':
        environment.containers[first['containerId']]['State']['Status'] = 'running'
    environment.timeouts.add(first['containerId'])
    interrupted = await operate(runtime, repository, first, action)
    assert interrupted['control'] == 'recovery_required'
    # A restart may be between stop and start when the HTTP timeout releases the lock.
    environment.containers[first['containerId']]['State']['Status'] = 'exited'
    fresh = mac.MacAndroidRuntime(other.root, other.workspace)
    with pytest.raises(AndroidError) as error:
        await fresh.capacity(second)
    assert error.value.code == 'ANDROID_CAPACITY'


@pytest.mark.asyncio
async def test_only_confirmed_owner_recovery_releases_reservation(environment):
    runtime, repository, first = environment.device('first')
    other, _, second = environment.device('second')
    environment.timeouts.add(first['containerId'])
    interrupted = await operate(runtime, repository, first, 'start')
    marker = interrupted['pendingLifecycle']
    still_unknown = await operate(runtime, repository, first, 'recover')
    assert still_unknown['control'] == 'recovery_required'
    with pytest.raises(AndroidError):
        await other.capacity(second)
    environment.markers[marker] = b'0\n'
    with pytest.raises(AndroidError) as error:
        await other.manage(interrupted, {'action': 'recover'}, lambda _: None, lambda: None)
    assert error.value.code == 'ANDROID_OWNERSHIP'
    recovered = await operate(mac.MacAndroidRuntime(runtime.root, runtime.workspace), repository, first, 'recover')
    assert recovered['control'] == 'idle'
    await other.capacity(second)


@pytest.mark.asyncio
async def test_running_reservation_is_not_counted_twice(environment):
    runtime, repository, first = environment.device('first')
    other, _, second = environment.device('second', memory=1024)
    environment.timeouts.add(first['containerId'])
    await operate(runtime, repository, first, 'start')
    environment.containers[first['containerId']]['State']['Status'] = 'running'
    await other.capacity(second)  # 2 GiB running + 1 GiB requested + 512 MiB reserve fits.


@pytest.mark.asyncio
async def test_stop_observation_failure_does_not_release_budget(environment, monkeypatch):
    runtime, repository, first = environment.device('first')
    other, _, second = environment.device('second')
    environment.containers[first['containerId']]['State']['Status'] = 'running'
    async def lost_observation(_device):
        raise TimeoutError('cannot verify stopped state')
    monkeypatch.setattr(runtime, 'inspect', lost_observation)
    stopped = await operate(runtime, repository, first, 'stop')
    assert stopped['control'] == 'recovery_required'
    with pytest.raises(AndroidError) as error:
        await other.capacity(second)
    assert error.value.code == 'ANDROID_CAPACITY'


@pytest.mark.asyncio
async def test_connect_never_starts_a_stopped_container_outside_admission(environment):
    runtime, repository, first = environment.device('first')
    with pytest.raises(AndroidError) as error:
        await runtime.connect(first, lambda: repository.save(first))
    assert error.value.code == 'ANDROID_NOT_READY'
    assert environment.commands == []


@pytest.mark.asyncio
async def test_actual_stopped_container_limit_is_used_for_admission(environment):
    runtime, repository, first = environment.device('first', memory=1024)
    _, _, second = environment.device('second', memory=1024)
    environment.containers[second['containerId']]['State']['Status'] = 'running'
    environment.containers[first['containerId']]['HostConfig']['Memory'] = 3 * 1024**3
    rejected = await operate(runtime, repository, first, 'start')
    assert rejected['operation']['state'] != 'succeeded'
    assert environment.commands == []


@pytest.mark.asyncio
async def test_zero_container_limit_cannot_be_replaced_with_configured_memory(environment):
    runtime, repository, first = environment.device('first')
    environment.containers[first['containerId']]['HostConfig']['Memory'] = 0
    rejected = await operate(runtime, repository, first, 'start')
    assert rejected['operation']['state'] != 'succeeded'
    assert environment.commands == []


@pytest.mark.asyncio
async def test_cancelled_start_keeps_budget_and_lifecycle_lock_serializes_workspaces(environment, monkeypatch):
    import asyncio
    runtime, repository, first = environment.device('first')
    other, other_repository, second = environment.device('second')
    entered = asyncio.Event()
    async def interrupted_run(*_args, **_kwargs):
        entered.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(management, 'run', interrupted_run)
    service = AndroidManagement(repository, runtime)
    service.operate(first['deviceId'], {'requestId': str(uuid4()), 'action': 'start', 'deleteData': False})
    await entered.wait()
    with pytest.raises(AndroidError) as error:
        AndroidManagement(other_repository, other).operate(second['deviceId'], {'requestId': str(uuid4()), 'action': 'start', 'deleteData': False})
    assert error.value.code == 'ANDROID_RUNTIME_BUSY'
    await service.shutdown()
    assert repository.get(first['deviceId'])['control'] == 'recovery_required'
    with pytest.raises(AndroidError) as error:
        await mac.MacAndroidRuntime(other.root, other.workspace).capacity(second)
    assert error.value.code == 'ANDROID_CAPACITY'


@pytest.mark.asyncio
@pytest.mark.parametrize('corruption', ['invalid_json', 'unknown_memory', 'wrong_owner', 'link'])
async def test_uncertain_reservation_journal_fails_closed(environment, corruption):
    from autoflow.providers.android import capacity_reservations
    runtime, repository, first = environment.device('first')
    other, _, second = environment.device('second')
    environment.timeouts.add(first['containerId'])
    await operate(runtime, repository, first, 'start')
    path = runtime.root / capacity_reservations.FILENAME
    if corruption == 'invalid_json':
        path.write_text('{')
    elif corruption == 'link':
        saved = path.with_suffix('.saved')
        path.rename(saved)
        path.symlink_to(saved)
    else:
        document = json.loads(path.read_text())
        item = next(iter(document['items'].values()))
        if corruption == 'unknown_memory':
            item['memoryBytes'] = None
        else:
            environment.containers[first['containerId']]['State']['Status'] = 'running'
            environment.containers[first['containerId']]['Config']['Labels'][mac.LABEL] = 'foreign'
        path.write_text(json.dumps(document))
    with pytest.raises(AndroidError) as error:
        await other.capacity(second)
    assert error.value.code == 'ANDROID_CAPACITY_UNKNOWN'


@pytest.mark.asyncio
async def test_failed_reservation_publication_never_launches_command(environment, monkeypatch):
    from autoflow.providers.android import capacity_reservations
    runtime, repository, first = environment.device('first')
    replace = capacity_reservations.os.replace
    def fail(*_args, **_kwargs):
        raise OSError('disk full')
    monkeypatch.setattr(capacity_reservations.os, 'replace', fail)
    rejected = await operate(runtime, repository, first, 'start')
    assert rejected['control'] == 'recovery_required'
    assert environment.commands == []
    assert not list(runtime.root.glob('.android-capacity-*'))
    monkeypatch.setattr(capacity_reservations.os, 'replace', replace)
    recovered = await operate(runtime, repository, first, 'recover')
    assert recovered['control'] == 'idle'


@pytest.mark.asyncio
async def test_frozen_generation_mismatch_does_not_release_budget(environment):
    from autoflow.providers.android import capacity_reservations
    runtime, repository, first = environment.device('first')
    environment.timeouts.add(first['containerId'])
    interrupted = await operate(runtime, repository, first, 'start')
    marker = interrupted['pendingLifecycle']
    with pytest.raises(AndroidError) as error:
        capacity_reservations.release(runtime.root, first, marker)  # pre-operation generation
    assert error.value.code == 'ANDROID_RECOVERY_REQUIRED'
    assert capacity_reservations.pending(runtime.root, interrupted)['marker'] == marker


@pytest.mark.asyncio
async def test_device_persistence_failure_before_dispatch_does_not_reserve_budget(environment):
    runtime, _, first = environment.device('first')
    other, _, second = environment.device('second')
    def save():
        if first.get('pendingLifecycle'):
            raise OSError('device state cannot be persisted')
    with pytest.raises(OSError):
        await runtime.manage(first, {'action': 'start'}, lambda _: None, save)
    assert environment.commands == []
    await other.capacity(second)


@pytest.mark.asyncio
async def test_recovered_container_name_is_canonicalized_before_reservation(environment):
    runtime, repository, first = environment.device('first')
    other, _, second = environment.device('second', memory=1024)
    identifier = first['containerId']
    first['containerId'] = environment.containers[identifier]['Name'][1:]
    repository.save(first)
    environment.timeouts.add(identifier)
    interrupted = await operate(runtime, repository, first, 'start')
    assert interrupted['containerId'] == identifier
    environment.containers[identifier]['State']['Status'] = 'running'
    await other.capacity(second)
