from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from autoflow.domain.android.ports import AndroidError
from autoflow.providers.android import mac_runtime
from autoflow.providers.android.stream import AndroidStream


@pytest.mark.asyncio
async def test_disconnected_stream_closes_only_after_forward_and_owned_file_are_verified(monkeypatch):
    runtime = SimpleNamespace(serial="127.0.0.1:9999", device={"containerId": "owned"},
        _stop=AsyncMock(), _adb=AsyncMock(side_effect=AndroidError("ANDROID_COMMAND_FAILED", "device offline")),
        inspect=AsyncMock())
    stream = AndroidStream(runtime)
    stream.port = 45678
    command = AsyncMock(return_value=b"")
    docker = AsyncMock()
    monkeypatch.setattr(mac_runtime, "run", command)
    monkeypatch.setattr(mac_runtime, "docker", docker)
    await stream.close()
    assert stream.port is None
    command.assert_awaited_once_with(["adb", "forward", "--list"])
    runtime.inspect.assert_awaited_once_with(runtime.device)
    docker.assert_awaited_once_with("exec", "owned", "rm", "-f", stream.remote, timeout=5)


@pytest.mark.asyncio
@pytest.mark.parametrize("listing", [b"127.0.0.1:9999 tcp:45678 localabstract:scrcpy_123\n", b"unrecognized output\n"])
async def test_disconnected_stream_keeps_unremoved_forward_isolated(monkeypatch, listing):
    runtime = SimpleNamespace(serial="127.0.0.1:9999", device={"containerId": "owned"},
        _stop=AsyncMock(), _adb=AsyncMock(side_effect=AndroidError("ANDROID_COMMAND_FAILED", "device offline")),
        inspect=AsyncMock())
    stream = AndroidStream(runtime)
    stream.port = 45678
    monkeypatch.setattr(mac_runtime, "run", AsyncMock(return_value=listing))
    docker = AsyncMock()
    monkeypatch.setattr(mac_runtime, "docker", docker)
    with pytest.raises(AndroidError):
        await stream.close()
    assert stream.port == 45678
    docker.assert_not_awaited()


@pytest.mark.asyncio
async def test_disconnected_stream_does_not_remove_file_from_unowned_container(monkeypatch):
    runtime = SimpleNamespace(serial="127.0.0.1:9999", device={"containerId": "foreign"},
        _stop=AsyncMock(), _adb=AsyncMock(side_effect=AndroidError("ANDROID_COMMAND_FAILED", "device offline")),
        inspect=AsyncMock(side_effect=AndroidError("ANDROID_OWNERSHIP", "foreign", 403)))
    stream = AndroidStream(runtime)
    docker = AsyncMock()
    monkeypatch.setattr(mac_runtime, "docker", docker)
    with pytest.raises(AndroidError) as failure:
        await stream.close()
    assert failure.value.code == "ANDROID_OWNERSHIP"
    docker.assert_not_awaited()
