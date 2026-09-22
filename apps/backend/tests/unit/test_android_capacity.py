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
