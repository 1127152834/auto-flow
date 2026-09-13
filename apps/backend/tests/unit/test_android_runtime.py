import asyncio
import json
import struct
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock

import pytest

from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.process.android_workflow_worker import (
    AndroidWorkflowWorker,
)
from autoflow.providers.android import mac_runtime as mac


def test_database_claim_has_one_winner(tmp_path):
    path = tmp_path / 'test.db'
    migrate_database(path)
    sessions = create_session_factory(path)
    repo = SqlAlchemyDeviceRepository(sessions)
    repo.save({'deviceId': 'device', 'control': 'idle', 'ownerRunId': None})
    def claim(owner):
        try:
            return repo.claim('device', owner)['ownerRunId']
        except AndroidError:
            return None
    with ThreadPoolExecutor(2) as pool:
        winners = list(pool.map(claim, ['one', 'two']))
    assert sum(winner is not None for winner in winners) == 1
    assert repo.get('device')['ownerRunId'] in winners
    sessions.dispose()


def test_controller_lock_is_shared_across_workspaces(tmp_path, monkeypatch):
    monkeypatch.setattr(mac.platform, 'system', lambda: 'Darwin')
    first = mac.MacAndroidRuntime(tmp_path / 'shared', tmp_path / 'one')
    second = mac.MacAndroidRuntime(tmp_path / 'shared', tmp_path / 'two')
    first.lock()
    try:
        with pytest.raises(AndroidError, match='控制器'):
            second.lock()
    finally:
        first.unlock()
    second.lock()
    second.unlock()


@pytest.mark.asyncio
async def test_unsupported_platform_is_unavailable_without_running_commands(tmp_path, monkeypatch):
    monkeypatch.setattr(mac.platform, 'system', lambda: 'Windows')
    command = AsyncMock()
    monkeypatch.setattr(mac, 'docker', command)
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    assert not (await runtime.environment())['available']
    command.assert_not_awaited()
    with pytest.raises(AndroidError):
        runtime.lock()


@pytest.mark.asyncio
async def test_container_and_volume_ownership_are_independently_checked(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    device = {'containerId': 'container', 'volumeId': 'data', 'workspaceId': runtime.workspace_id, 'deviceId': 'id'}
    container = {'Config': {'Labels': {'autoflow.demo': 'true'}}}
    docker = AsyncMock(return_value=json.dumps([container]).encode())
    monkeypatch.setattr(mac, 'docker', docker)
    with pytest.raises(AndroidError, match='归属'):
        await runtime.inspect(device)
    container['Config']['Labels'] = {mac.LABEL: runtime.workspace_id, 'io.autoflow.android.device': 'id'}
    container['Mounts'] = [{'Name': 'data', 'Destination': '/data'}]
    docker.side_effect = [json.dumps([container]).encode(), json.dumps([{'Labels': {mac.LABEL: runtime.workspace_id, 'io.autoflow.android.device': 'another-device'}}]).encode()]
    with pytest.raises(AndroidError, match='标签'):
        await runtime.inspect(device)


@pytest.mark.asyncio
async def test_stale_screenshot_basis_never_sends_tap(tmp_path):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    png = b'\x89PNG\r\n\x1a\n' + b'\0\0\0\rIHDR' + struct.pack('>II', 720, 1280)
    runtime._adb = AsyncMock(return_value=png)
    with pytest.raises(AndroidError, match='尺寸'):
        await runtime.command('android_tap', {'basisWidth': 1280, 'basisHeight': 720, 'x': 1, 'y': 1}, 1)
    assert runtime._adb.await_count == 1


@pytest.mark.asyncio
async def test_reused_pid_is_not_signalled_but_unknown_live_identity_is_quarantined(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    monkeypatch.setattr(mac, 'process_birth', lambda _: 222)
    signals = []
    monkeypatch.setattr(mac.os, 'kill', lambda pid, signal: signals.append((pid, signal)))
    await runtime.recover({'processes': {'viewer': {'pid': 123, 'birth': 111}}})
    assert not signals
    with pytest.raises(AndroidError, match='身份'):
        await runtime.recover({'processes': {'viewer': {'pid': 123, 'birth': None}}})
    assert signals == [(123, 0)]


@pytest.mark.asyncio
@pytest.mark.parametrize('worker', [False, True])
async def test_cancel_during_spawn_waits_for_owned_process_and_reaps_it(tmp_path, monkeypatch, worker):
    gate, spawned = asyncio.Event(), asyncio.Event()
    class Process:
        returncode = None
        killed = False
        def kill(self):
            self.killed = True
        async def wait(self):
            self.returncode = -9
    process = Process()
    async def spawn(*args, **kwargs):
        spawned.set()
        await gate.wait()
        return process
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', spawn)
    operation = AndroidWorkflowWorker()._execute(None, None, None) if worker else mac.run(['unused'])
    task = asyncio.create_task(operation)
    await spawned.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    gate.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert process.killed and process.returncode == -9


def test_worker_eof_stops_before_the_next_node():
    import subprocess
    import sys
    payload = {'variables': {}, 'nodeIds': ['one', 'two'], 'document': {'nodes': [{'id': name, 'type': 'android_key', 'config': {'key': 'BACK', 'timeoutSeconds': 15}} for name in ['one', 'two']]}}
    result = subprocess.run([sys.executable, '-m', 'autoflow', '--android-workflow-worker'], input=json.dumps(payload) + '\n', capture_output=True, text=True, timeout=5, check=False)
    messages = [json.loads(line) for line in result.stdout.splitlines()]
    assert result.returncode == 1
    assert [message['nodeId'] for message in messages if message['type'] == 'android_command'] == ['one']
