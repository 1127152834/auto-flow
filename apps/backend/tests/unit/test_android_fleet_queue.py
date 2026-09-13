from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from autoflow.application.android.fleet import AndroidFleet
from autoflow.domain.android.ports import AndroidError


class Store:
    def __init__(self, device=None):
        self.device = device
        self.saved = {}

    def get(self, identifier):
        if self.device is None:
            raise AndroidError("ANDROID_NOT_FOUND", "missing", 404)
        return deepcopy(self.device)

    def save(self, kind, value):
        self.saved[kind] = deepcopy(value)


def fleet(device=None, run=None):
    store = Store(device)
    manager = SimpleNamespace(
        create=Mock(), operate=Mock(), busy=Mock(return_value=False)
    )
    runtime = SimpleNamespace(
        inspect=AsyncMock(return_value={"androidStatus": "stopped"}),
        capacity=AsyncMock(),
    )
    service = SimpleNamespace(repository=store, management=manager, runtime=runtime)
    return AndroidFleet(
        service, store, None, SimpleNamespace(get=Mock(return_value=run))
    )


def batch():
    return {
        "id": "batch",
        "state": "queued",
        "profile": {
            "id": "p",
            "name": "p",
            "imageId": "image",
            "dpi": 320,
            "cpu": 1,
            "memoryMb": 1536,
        },
        "request": {
            "start": True,
            "width": 720,
            "height": 1280,
            "instanceType": "persistent",
            "locale": "zh-CN",
            "timezone": "Asia/Shanghai",
        },
        "items": [
            {"deviceId": "one", "name": "one", "state": "waiting_create", "error": None}
        ],
    }


@pytest.mark.asyncio
async def test_create_uses_preallocated_identifier_then_waits_for_capacity():
    service, request = fleet(), batch()
    await service._batch_step(request)
    assert service.devices.management.create.call_args.args[0]["deviceId"] == "one"
    assert request["items"][0]["state"] == "creating"
    service.devices.repository.device = {"deviceId": "one", "control": "idle"}
    service.devices.runtime.capacity.side_effect = AndroidError(
        "ANDROID_MEMORY_BUDGET", "full"
    )
    await service._batch_step(request)
    assert request["items"][0]["state"] == "waiting_capacity"
    service.devices.management.operate.assert_not_called()
    service.devices.runtime.capacity.side_effect = None
    await service._batch_step(request)
    assert request["items"][0]["state"] == "starting"
    assert service.devices.management.create.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["failed", "interrupted", "stopped"])
async def test_unsuccessful_temporary_runs_retain_device(state):
    service = fleet(
        {"deviceId": "one", "control": "idle", "instanceType": "temporary"},
        {"state": state, "error": {"message": "retained"}},
    )
    item = {"id": "allocation", "runId": "run", "deviceId": "one"}
    await service._allocation_step(item)
    assert item["state"] == "failed"
    service.devices.management.operate.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_failure_remains_visible_and_persistent_success_never_deletes():
    service = fleet(
        {
            "deviceId": "one",
            "control": "recovery_required",
            "instanceType": "temporary",
        },
        {"state": "succeeded"},
    )
    item = {"id": "allocation", "runId": "run", "deviceId": "one"}
    await service._allocation_step(item)
    assert item["state"] == "failed" and "回收失败" in item["error"]
    service.devices.repository.device.update(control="idle", instanceType="persistent")
    await service._allocation_step(item)
    assert item["state"] == "succeeded"
    service.devices.management.operate.assert_not_called()
