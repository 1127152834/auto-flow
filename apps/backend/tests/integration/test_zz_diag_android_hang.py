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
    captured = []
    original_manage = runtime.manage

    async def spy(*args, **kwargs):
        try:
            return await original_manage(*args, **kwargs)
        except BaseException as error:
            captured.append("".join(traceback.format_exception(error)))
            raise

    monkeypatch.setattr(runtime, 'manage', spy)
    service = AndroidManagement(repository, runtime)
    service.operate(device['deviceId'], {'requestId': str(uuid4()), 'action': action, 'deleteData': False})
    await service.task
    return repository.get(device['deviceId'])



import asyncio, sys, traceback, faulthandler


def _dump(tag, tasks):
    lines = [tag]
    for task in tasks:
        lines.append("task %s done=%s" % (task.get_name(), task.done()))
        for frame in task.get_stack(limit=12):
            lines.append("  %s:%s %s" % (frame.f_code.co_filename.split("autoflow")[-1], frame.f_lineno, frame.f_code.co_name))
    text = "\n".join(lines).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print("::error title=android hang trace::" + text, flush=True)


@pytest.mark.asyncio
async def test_diag(environment, monkeypatch):
    runtime, repository, first = environment.device('first')
    other, other_repository, second = environment.device('second')
    entered = asyncio.Event()
    async def interrupted_run(*_args, **_kwargs):
        entered.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(management, 'run', interrupted_run)
    captured = []
    original_manage = runtime.manage

    async def spy(*args, **kwargs):
        try:
            return await original_manage(*args, **kwargs)
        except BaseException as error:
            captured.append("".join(traceback.format_exception(error)))
            raise

    monkeypatch.setattr(runtime, 'manage', spy)
    service = AndroidManagement(repository, runtime)
    service.operate(first['deviceId'], {'requestId': str(uuid4()), 'action': 'start', 'deleteData': False})
    print("::notice title=DIAG::operate returned", flush=True)
    try:
        await asyncio.wait_for(entered.wait(), 20)
    except TimeoutError:
        _dump("never entered run", asyncio.all_tasks())
        def emit(title, text):
            print("::error title=%s::%s" % (title, str(text)[-3500:].replace("%", "%25").replace("\r", "").replace("\n", "%0A")), flush=True)
        emit("android manage error", captured[-1] if captured else "manage not reached")
        try:
            record = repository.get(first['deviceId'])
            emit("android device state", "control=%s lastError=%s operation=%s task=%r" % (record.get('control'), record.get('lastError'), record.get('operation'), service.task))
        except BaseException as error:
            emit("android device state failed", "".join(traceback.format_exception(error)))
        raise
    print("::notice title=DIAG::entered", flush=True)
    with pytest.raises(AndroidError) as error:
        AndroidManagement(other_repository, other).operate(second['deviceId'], {'requestId': str(uuid4()), 'action': 'start', 'deleteData': False})
    print("::notice title=DIAG::busy code", error.value.code, flush=True)
    try:
        await asyncio.wait_for(service.shutdown(), 20)
    except TimeoutError:
        _dump("shutdown hung", asyncio.all_tasks())
        raise
    print("::notice title=DIAG::shutdown ok", repository.get(first['deviceId'])['control'], flush=True)
    with pytest.raises(AndroidError) as error:
        await asyncio.wait_for(mac.MacAndroidRuntime(other.root, other.workspace).capacity(second), 20)
    print("::notice title=DIAG::capacity code", error.value.code, flush=True)
