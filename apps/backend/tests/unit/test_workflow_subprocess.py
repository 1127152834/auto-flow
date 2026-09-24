from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from autoflow.infrastructure.process import workflow_subprocess as cleanup


@pytest.mark.asyncio
async def test_cleanup_refuses_unknown_live_process_identity(monkeypatch):
    monkeypatch.setattr(cleanup.sys, 'platform', 'darwin')
    monkeypatch.setattr(cleanup, 'process_birth', lambda _pid: None)
    with pytest.raises(RuntimeError, match='身份尚未确认'):
        await cleanup.terminate_subprocess(SimpleNamespace(pid=10, returncode=None))


@pytest.mark.asyncio
async def test_cleanup_signals_only_verified_pids_not_the_worker_group(monkeypatch):
    process = SimpleNamespace(pid=10, returncode=None, wait=AsyncMock())
    killed = []
    monkeypatch.setattr(cleanup.sys, 'platform', 'darwin')
    monkeypatch.setattr(cleanup, 'process_birth', lambda pid: {10: 42, 11: 8}[pid])
    monkeypatch.setattr(cleanup, 'capture_processes', lambda *_args: {10: (99, 42), 11: (99, 7)})
    monkeypatch.setattr(cleanup, 'living_processes', lambda _owned: {})
    monkeypatch.setattr(cleanup.os, 'kill', lambda pid, _signal: killed.append(pid))
    monkeypatch.setattr(cleanup.os, 'killpg', lambda *_args: pytest.fail('must not kill the worker group'))
    await cleanup.terminate_subprocess(process)
    assert killed == [10]
    process.wait.assert_awaited_once()


def test_worker_environment_strips_host_authority_without_mutating_parent():
    source = {'AUTOFLOW_INSTANCE_TOKEN': 'dummy', 'AUTOFLOW_HOST_TOKEN': 'dummy-host', 'PATH': '/bin', 'USER_SCRIPT_VALUE': '甲'}
    assert cleanup.workflow_environment(source) == {'PATH': '/bin', 'USER_SCRIPT_VALUE': '甲'}
    assert source['AUTOFLOW_INSTANCE_TOKEN'] == 'dummy'
