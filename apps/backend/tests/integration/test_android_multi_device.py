import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from autoflow.application.android.bulk import AndroidBulkService
from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.android_operations import (
    SqlAlchemyAndroidOperationRepository,
)
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


class _Capacity:
    def __init__(self):
        self.ready = False

    async def __call__(self, _device):
        if not self.ready:
            raise AndroidError("ANDROID_CAPACITY_UNKNOWN", "capacity not measured")


class _Devices:
    def __init__(self, operations):
        self.items = {
            "d1": {"deviceId": "d1", "name": "一号", "generation": 1, "control": "idle"},
            "d2": {"deviceId": "d2", "name": "二号", "generation": 1, "control": "idle"},
        }
        self.capacity = _Capacity()
        self.runtime = type("Runtime", (), {"capacity": self.capacity})()
        self.operations = operations
        self.management = type("Management", (), {"workspace_identity": "ws", "operations": operations})()
        self.requests = []

    def get(self, identifier):
        return self.items[identifier]

    def operate(self, device_id, request):
        self.requests.append(request)
        record = self.operations.accept(
            "ws",
            request["requestId"],
            device_id,
            request["action"],
            hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            request,
            retry_of=request.get("retryOf"),
        )
        record = self.operations.transition(record.operation_id, "queued", "running", {})
        self.items[device_id]["operation"] = {"id": record.operation_id, "state": "running"}
        return {"deviceId": device_id, "operation": {"id": record.operation_id}}


@pytest.mark.asyncio
async def test_multi_device_bulk_uses_persistent_queue_capacity_and_new_retry_ids(tmp_path: Path):
    database = tmp_path / "android.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    devices = _Devices(operations)
    service = AndroidBulkService(resources, devices)
    batch = service.create("ws", "bulk-1", "start", [{"deviceId": "d1", "expectedRevision": 2}, {"deviceId": "d2", "expectedRevision": 2}], False)
    assert all(item["operationId"] for item in batch["items"])

    await service.tick()
    batch = service.get(batch["id"])
    assert [item["state"] for item in batch["items"]] == ["waiting_capacity", "queued"]
    devices.capacity.ready = True
    await service.tick()
    batch = service.get(batch["id"])
    assert [request["requestId"] for request in devices.requests] == ["bulk-1:d1:1"]
    assert batch["items"][1]["state"] == "queued"

    service.action(batch["id"], "cancelPending", "cancel-1")
    batch = service.get(batch["id"])
    assert batch["items"][0]["state"] == "accepted"
    assert batch["items"][1]["state"] == "cancelled"
    assert operations.get(batch["items"][1]["operationId"], "ws").state == "cancelled"
    await service.tick()
    assert [request["requestId"] for request in devices.requests] == ["bulk-1:d1:1"]

    first_operation = operations.by_request("ws", "bulk-1:d1:1")
    operations.transition(first_operation.operation_id, "running", "failed", {"message": "first attempt failed"})
    devices.items["d1"]["operation"].update(state="failed")
    await service.tick()
    batch = service.get(batch["id"])
    assert batch["items"][0]["state"] == "failed"
    service.action(batch["id"], "retryFailed")
    batch = service.get(batch["id"])
    assert batch["items"][0]["operationId"]
    assert batch["items"][0]["retryOf"] == first_operation.operation_id
    await service.tick()
    batch = service.get(batch["id"])
    assert [request["requestId"] for request in devices.requests] == ["bulk-1:d1:1", "bulk-1:d1:2"]
    assert batch["items"][0]["state"] == "accepted"
    assert batch["items"][1]["state"] == "cancelled"

    retry_operation = operations.by_request("ws", "bulk-1:d1:2")
    assert retry_operation.retry_of == first_operation.operation_id
    assert retry_operation.attempt == first_operation.attempt + 1
    operations.transition(retry_operation.operation_id, "running", "succeeded", {})
    devices.items["d1"]["operation"].update(state="succeeded")
    await service.tick()
    batch = service.get(batch["id"])
    assert batch["items"][1]["state"] == "cancelled"
    assert batch["items"][0]["state"] == "succeeded"

    await service.shutdown()
    sessions.dispose()


@pytest.mark.asyncio
async def test_bulk_verify_reconciles_unknown_item_without_replaying_operation(tmp_path: Path):
    database = tmp_path / "android-bulk-verify.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    devices = _Devices(operations)

    async def inspect(_device):
        return {"androidStatus": "stopped"}

    devices.runtime.inspect = inspect
    service = AndroidBulkService(resources, devices)
    batch = service.create("ws", "bulk-verify", "stop", [{"deviceId": "d1", "expectedRevision": 2}], False)
    result = service.run(batch["id"], "ws")
    operation_id = result["items"][0]["operationId"]
    operation = operations.get(operation_id, "ws")
    operations.transition(operation.operation_id, "running", "needs_verification", {})
    devices.items["d1"]["control"] = "recovery_required"
    devices.repository = SqlAlchemyDeviceRepository(sessions)
    devices.repository.save(devices.items["d1"])
    devices.get = devices.repository.get

    result = await service.verify(batch["id"], "ws")

    assert result["items"][0]["state"] == "succeeded"
    assert operations.get(operation_id, "ws").state == "succeeded"
    assert devices.repository.get("d1")["control"] == "idle"
    assert len(devices.requests) == 1
    sessions.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("probe_result", ["available", "full", "error", "cancelled"])
async def test_cancel_pending_survives_in_flight_capacity_probe(tmp_path: Path, probe_result: str):
    database = tmp_path / "cancel-during-capacity.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    devices = _Devices(operations)
    entered, release = asyncio.Event(), asyncio.Event()

    async def capacity(_device):
        entered.set()
        await release.wait()
        if probe_result == "full":
            raise AndroidError("ANDROID_MEMORY_BUDGET", "full")
        if probe_result == "error":
            raise AndroidError("ANDROID_COMMAND_FAILED", "probe unavailable")

    devices.runtime.capacity = capacity
    service = AndroidBulkService(resources, devices)
    batch = service.create("ws", "cancel-race", "start", [{"deviceId": "d1", "expectedRevision": 2}], False)
    tick = asyncio.create_task(service.tick())
    try:
        await asyncio.wait_for(entered.wait(), 2)
        cancelled = service.action(batch["id"], "cancelPending", "cancel-original")
        assert cancelled["state"] == "cancelled"
        if probe_result == "cancelled":
            tick.cancel()
            with pytest.raises(asyncio.CancelledError):
                await tick
        else:
            release.set()
            await tick
        saved = service.get(batch["id"])
        assert saved["state"] == "cancelled"
        assert saved["items"][0]["state"] == "cancelled"
        assert saved["actionReceipts"] == {"cancel-original": "cancelPending"}
        assert operations.get(saved["items"][0]["operationId"], "ws").state == "cancelled"
        assert devices.requests == []
        assert service.action(batch["id"], "cancelPending", "cancel-original") == saved
    finally:
        tick.cancel()
        await asyncio.gather(tick, return_exceptions=True)
        sessions.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("verified", [True, False])
async def test_verification_preserves_cancellation_recorded_while_runtime_read_is_pending(tmp_path: Path, verified: bool):
    database = tmp_path / "cancel-during-verify.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    devices = _Devices(operations)
    devices.capacity.ready = True
    entered, release = asyncio.Event(), asyncio.Event()

    async def inspect(_device):
        entered.set()
        await release.wait()
        if not verified:
            raise OSError("runtime disconnected")
        return {"androidStatus": "ready"}

    devices.runtime.inspect = inspect
    service = AndroidBulkService(resources, devices)
    batch = service.create("ws", "verify-cancel-race", "start", [{"deviceId": "d1", "expectedRevision": 2}, {"deviceId": "d2", "expectedRevision": 2}], False)
    await service.tick()
    batch = service.get(batch["id"])
    operations.transition(batch["items"][0]["operationId"], "running", "needs_verification", {})
    devices.repository = SqlAlchemyDeviceRepository(sessions)
    for device in devices.items.values():
        devices.repository.save(device)
    devices.get = devices.repository.get
    verify = asyncio.create_task(service.verify(batch["id"], "ws"))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        service.action(batch["id"], "cancelPending", "cancel-during-verify")
        release.set()
        result = await verify
        assert result["items"][1]["state"] == "cancelled"
        assert result["actionReceipts"] == {"cancel-during-verify": "cancelPending"}
        assert result["items"][0]["state"] == ("succeeded" if verified else "needs_verification")
        assert service.get(batch["id"]) == result
        assert len(devices.requests) == 1
    finally:
        verify.cancel()
        await asyncio.gather(verify, return_exceptions=True)
        sessions.dispose()


@pytest.mark.asyncio
async def test_tick_rereads_later_batch_cancelled_during_an_earlier_capacity_probe(tmp_path: Path):
    database = tmp_path / "cancel-later-batch.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    devices = _Devices(operations)
    entered, release = asyncio.Event(), asyncio.Event()
    probed = []

    async def capacity(device):
        probed.append(device["deviceId"])
        entered.set()
        await release.wait()
        raise AndroidError("ANDROID_MEMORY_BUDGET", "full")

    devices.runtime.capacity = capacity
    service = AndroidBulkService(resources, devices)
    service.create("ws", "earlier", "start", [{"deviceId": "d1", "expectedRevision": 2}], False)
    later = service.create("ws", "later", "start", [{"deviceId": "d2", "expectedRevision": 2}], False)
    tick = asyncio.create_task(service.tick())
    try:
        await asyncio.wait_for(entered.wait(), 2)
        service.action(later["id"], "cancelPending", "cancel-later")
        release.set()
        await tick
        saved = service.get(later["id"])
        assert saved["state"] == "cancelled"
        assert saved["actionReceipts"] == {"cancel-later": "cancelPending"}
        assert probed == ["d1"]
        assert devices.requests == []
    finally:
        tick.cancel()
        await asyncio.gather(tick, return_exceptions=True)
        sessions.dispose()
