import json
import struct
import sys
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock

import pytest

from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.providers.android import mac_runtime as mac


@pytest.mark.asyncio
async def test_failed_real_command_preserves_bounded_redacted_reason():
    with pytest.raises(AndroidError) as caught:
        await mac.run([sys.executable, '-c', 'import sys;sys.stderr.write("bridge docker0 does not exist\\nAuthorization: Bearer qa-secret");sys.exit(17)'])
    assert caught.value.code == 'ANDROID_COMMAND_FAILED'
    assert '17' in caught.value.message
    assert 'bridge docker0 does not exist' in caught.value.message
    assert 'qa-secret' not in caught.value.message
    with pytest.raises(AndroidError) as long_error:
        await mac.run([sys.executable, '-c', 'import sys;sys.stderr.write("x"*5000);sys.exit(1)'])
    assert len(long_error.value.message) < 2200


@pytest.mark.asyncio
async def test_missing_docker_bridge_is_not_a_ready_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(mac.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(mac.platform, 'machine', lambda: 'arm64')
    monkeypatch.setattr(mac.shutil, 'which', lambda tool: '/tools/' + tool)
    vendor = tmp_path / mac.VENDOR / 'scrcpy'
    vendor.parent.mkdir()
    vendor.touch()
    docker = AsyncMock(side_effect=[json.dumps({'OSType': 'linux', 'Architecture': 'aarch64'}).encode(), json.dumps([{'Options': {'com.docker.network.bridge.name': 'docker0'}}]).encode()])
    monkeypatch.setattr(mac, 'docker', docker)
    command = AsyncMock(side_effect=[b'nodev\tbinder\n', AndroidError('ANDROID_COMMAND_FAILED', 'bridge unavailable', 502)])
    monkeypatch.setattr(mac, 'run', command)
    result = await mac.MacAndroidRuntime(tmp_path, tmp_path).environment()
    assert result['available'] is False
    assert 'docker0' in result['message']
    assert command.await_args_list[-1].args[0][-2:] == ['-d', '/sys/class/net/docker0']


@pytest.mark.asyncio
async def test_malformed_environment_response_becomes_diagnostic_not_500(tmp_path, monkeypatch):
    monkeypatch.setattr(mac.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(mac.platform, 'machine', lambda: 'arm64')
    monkeypatch.setattr(mac.shutil, 'which', lambda tool: '/tools/' + tool)
    monkeypatch.setattr(mac, 'docker', AsyncMock(return_value=b'[]'))
    result = await mac.MacAndroidRuntime(tmp_path, tmp_path).environment()
    assert result['available'] is False
    assert result['cpuCount'] == 0
    assert '数据格式无效' in result['message']


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
