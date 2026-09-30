import pytest

from autoflow.application.android.capacity import admit
from autoflow.application.android.fleet import AndroidFleet
from autoflow.domain.android.ports import AndroidError


def test_capacity_reserves_host_memory_and_unknown_state_blocks():
    assert admit({"cpu": 1, "memoryMb": 1024}, {"cpu": 4, "memoryMb": 8192, "usedMb": 1024}) is True
    with pytest.raises(AndroidError):
        admit({"cpu": 1, "memoryMb": 1024}, {"cpu": 4, "memoryMb": None, "usedMb": None})


@pytest.mark.parametrize(
    "snapshot",
    [
        {},
        {"cpu": 0, "memoryMb": 8192, "usedMb": 1024},
        {"cpu": 4, "memoryMb": 0, "usedMb": 0},
        {"cpu": 4, "memoryMb": 8192, "usedMb": -1},
    ],
)
def test_capacity_rejects_unknown_or_zero_host_resources(snapshot):
    with pytest.raises(AndroidError) as error:
        admit({"cpu": 1, "memoryMb": 1024}, snapshot)
    assert error.value.code == "ANDROID_CAPACITY_UNKNOWN"


@pytest.mark.asyncio
async def test_fleet_capacity_unknown_is_a_waiting_result() -> None:
    class Runtime:
        async def capacity(self, _device):
            raise AndroidError("ANDROID_CAPACITY_UNKNOWN", "容量尚未核实")

    class Devices:
        runtime = Runtime()

    fleet = AndroidFleet(Devices(), _Resources(), None, None)

    assert await fleet._capacity({"deviceId": "d1"}) is False


@pytest.mark.asyncio
async def test_fleet_capacity_missing_snapshot_fails_closed() -> None:
    class Runtime:
        async def capacity(self, _device):
            raise KeyError("MemTotal")

    class Devices:
        runtime = Runtime()

    fleet = AndroidFleet(Devices(), _Resources(), None, None)

    assert await fleet._capacity({"deviceId": "d1"}) is False


@pytest.mark.asyncio
async def test_fleet_capacity_without_runtime_fails_closed() -> None:
    class Devices:
        pass

    fleet = AndroidFleet(Devices(), _Resources(), None, None)

    assert await fleet._capacity({"deviceId": "d1"}) is False


class _Resources:
    def list(self, _kind):
        return []


@pytest.mark.asyncio
@pytest.mark.parametrize("memory", [0, None, True, -1])
async def test_runtime_capacity_blocks_unknown_external_memory(monkeypatch, memory):
    import json
    from unittest.mock import AsyncMock

    from autoflow.providers.android import management

    monkeypatch.setattr(management, "docker", AsyncMock(side_effect=[
        json.dumps({"NCPU": 4, "MemTotal": 8 * 1024**3}).encode(),
        b"other\n",
        json.dumps([{"Id": "other", "HostConfig": {"Memory": memory}}]).encode(),
    ]))
    with pytest.raises(AndroidError) as error:
        await management.capacity({"containerId": "target", "cpu": 1, "memoryMb": 1024})
    assert error.value.code == "ANDROID_CAPACITY_UNKNOWN"


@pytest.mark.asyncio
@pytest.mark.parametrize("inspection", [[], [{"Id": "unlisted", "HostConfig": {"Memory": 1024**3}}]])
async def test_runtime_capacity_requires_complete_running_container_inventory(monkeypatch, inspection):
    import json
    from unittest.mock import AsyncMock

    from autoflow.providers.android import management

    monkeypatch.setattr(management, "docker", AsyncMock(side_effect=[
        json.dumps({"NCPU": 4, "MemTotal": 8 * 1024**3}).encode(),
        b"other\n",
        json.dumps(inspection).encode(),
    ]))
    with pytest.raises(AndroidError) as error:
        await management.capacity({"containerId": "target", "cpu": 1, "memoryMb": 1024})
    assert error.value.code == "ANDROID_CAPACITY_UNKNOWN"


@pytest.mark.asyncio
async def test_runtime_capacity_inventory_failure_is_reported_as_unknown(monkeypatch):
    import json
    from unittest.mock import AsyncMock

    from autoflow.providers.android import management

    monkeypatch.setattr(management, "docker", AsyncMock(side_effect=[
        json.dumps({"NCPU": 4, "MemTotal": 8 * 1024**3}).encode(),
        AndroidError("ANDROID_COMMAND_FAILED", "daemon unavailable", 502),
    ]))
    with pytest.raises(AndroidError) as error:
        await management.capacity({"containerId": "target", "cpu": 1, "memoryMb": 1024})
    assert error.value.code == "ANDROID_CAPACITY_UNKNOWN"
