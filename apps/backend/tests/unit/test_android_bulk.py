
import asyncio

import pytest

from autoflow.application.android.bulk import AndroidBulkService
from autoflow.application.android.devices import AndroidDeviceService
from autoflow.domain.android.ports import AndroidError


def test_bulk_freezes_targets_and_keeps_partial_failures():
    resources = _Resources()
    devices = _Devices()
    service = AndroidBulkService(resources, devices)
    batch = service.create("ws", "r1", "stop", [{"deviceId": "d1", "expectedRevision": 1}, {"deviceId": "d2", "expectedRevision": 9}], False)
    assert [item["deviceId"] for item in batch["items"]] == ["d1", "d2"]
    result = service.run(batch["id"])
    assert result["state"] == "running"
    assert result["items"][0]["state"] in {"queued", "accepted", "succeeded"}
    assert result["items"][1]["state"] == "failed"


@pytest.mark.asyncio
async def test_bulk_tick_projects_terminal_device_operation_state_without_get_side_effects():
    resources = _Resources()
    devices = _Devices()
    service = AndroidBulkService(resources, devices)
    batch = service.create("ws", "r-project", "stop", [{"deviceId": "d1", "expectedRevision": 1}], False)
    result = service.run(batch["id"])
    assert result["state"] == "running"
    devices.items["d1"]["operation"] = {"id": "r-project:d1:1", "state": "succeeded"}

    result = service.get(batch["id"])
    assert result["items"][0]["state"] == "accepted"

    await service.tick()

    result = service.get(batch["id"])
    assert result["items"][0]["state"] == "succeeded"
    assert result["state"] == "succeeded"


@pytest.mark.asyncio
async def test_bulk_waits_for_unknown_capacity_then_advances_one_device_at_a_time():
    resources = _Resources()
    devices = _QueueDevices()
    service = AndroidBulkService(resources, devices)
    batch = service.create("ws", "r-capacity", "start", [{"deviceId": "d1", "expectedRevision": 1}, {"deviceId": "d2", "expectedRevision": 1}], False)

    await service.tick()
    assert batch["items"][0]["state"] == "waiting_capacity"
    assert devices.calls == []

    devices.runtime.ready = True
    await service.tick()
    assert batch["items"][0]["state"] == "accepted"
    assert batch["items"][1]["state"] == "queued"
    assert [call[0] for call in devices.calls] == ["d1"]

    devices.items["d1"]["operation"]["state"] = "succeeded"
    await service.tick()
    assert batch["items"][0]["state"] == "succeeded"
    assert batch["items"][1]["state"] == "accepted"
    assert [call[0] for call in devices.calls] == ["d1", "d2"]


def test_bulk_retry_uses_a_new_request_id_after_terminal_failure():
    resources = _Resources()
    devices = _RetryDevices()
    service = AndroidBulkService(resources, devices)
    batch = service.create("ws", "r-retry", "stop", [{"deviceId": "d1", "expectedRevision": 1}], False)

    first = service.run(batch["id"])
    assert first["items"][0]["state"] == "failed"
    service.action(batch["id"], "retryFailed")
    second = service.run(batch["id"])

    assert second["items"][0]["state"] == "accepted"
    assert devices.requests == ["r-retry:d1:1", "r-retry:d1:2"]


def test_bulk_action_request_is_idempotent_and_conflicts_on_changed_action():
    resources = _Resources()
    service = AndroidBulkService(resources, _Devices())
    batch = service.create("ws", "r-action", "stop", [{"deviceId": "d1", "expectedRevision": 1}], False)

    first = service.action(batch["id"], "cancelPending", "a1")
    again = service.action(batch["id"], "cancelPending", "a1")
    assert again["items"] == first["items"]
    with pytest.raises(AndroidError, match="请求编号"):
        service.action(batch["id"], "retryFailed", "a1")


def test_bulk_unknown_result_is_not_reported_as_running_when_queue_is_drained():
    batch = {"items": [{"state": "needs_verification"}, {"state": "succeeded"}]}

    AndroidBulkService._batch_state(batch)

    assert batch["state"] == "partially_failed"


def test_bulk_request_id_is_idempotent_and_conflicts_on_changed_action():
    resources = _Resources()
    service = AndroidBulkService(resources, _Devices())
    items = [{"deviceId": "d1", "expectedRevision": 1}]
    first = service.create("ws", "r1", "stop", items, False)
    again = service.create("ws", "r1", "stop", items, False)
    assert again["id"] == first["id"]
    try:
        service.create("ws", "r1", "start", items, False)
    except AndroidError as error:
        assert error.code == "ANDROID_BULK_REQUEST_CONFLICT"
    else:
        raise AssertionError("changed bulk request must conflict")


def test_bulk_service_uses_android_device_service_management_facade():
    resources = _Resources()
    devices = AndroidDeviceService(_Repository(), object())
    devices.management = _Management()
    service = AndroidBulkService(resources, devices)
    batch = service.create("ws", "r-facade", "stop", [{"deviceId": "d1", "expectedRevision": 1}], False)

    result = service.run(batch["id"])

    assert result["items"][0]["state"] == "accepted"
    assert devices.management.calls == [("d1", {"requestId": "r-facade:d1:1", "action": "stop", "deleteData": False})]


def test_bulk_rejects_targets_owned_by_another_workspace():
    resources = _Resources()
    devices = _WorkspaceDevices()
    service = AndroidBulkService(resources, devices)

    with pytest.raises(AndroidError) as error:
        service.create("ws-a", "r-cross", "stop", [{"deviceId": "d-b", "expectedRevision": 1}], False)

    assert error.value.status == 404


@pytest.mark.asyncio
async def test_bulk_queue_only_advances_batches_for_the_bound_workspace():
    resources = _Resources()
    devices = _WorkspaceDevices()
    devices.management = type("Management", (), {"workspace_identity": "ws-a"})()
    service = AndroidBulkService(resources, devices)
    foreign = {
        "id": "foreign-batch",
        "workspaceIdentity": "ws-b",
        "requestId": "foreign",
        "action": "stop",
        "deleteData": False,
        "state": "queued",
        "items": [{"deviceId": "d-b", "expectedRevision": 1, "state": "queued", "operationId": None, "error": None}],
    }
    resources.save("bulk", foreign)

    await service.tick()

    assert devices.requests == []
    assert resources.get("bulk", "foreign-batch")["items"][0]["state"] == "queued"


@pytest.mark.asyncio
async def test_bulk_reconciles_cancelled_operation_and_batch_state():
    resources = _Resources()
    devices = _OperationDevices(state="cancelled")
    service = AndroidBulkService(resources, devices)
    batch = service.create("ws-a", "r-cancelled", "stop", [{"deviceId": "d-a", "expectedRevision": 1}], False)
    result = service.run(batch["id"])

    assert result["items"][0]["state"] == "accepted"
    await service.tick()

    result = service.get(batch["id"])
    assert result["items"][0]["state"] == "cancelled"
    assert result["state"] == "cancelled"


@pytest.mark.asyncio
async def test_bulk_cancelled_error_persists_unknown_result_before_propagating():
    resources = _Resources()
    devices = _CancelledDevices()
    service = AndroidBulkService(resources, devices)
    batch = service.create("ws-a", "r-interrupt", "stop", [{"deviceId": "d-a", "expectedRevision": 1}], False)

    with pytest.raises(asyncio.CancelledError):
        await service.tick()

    saved = service.get(batch["id"])
    assert saved["items"][0]["state"] == "needs_verification"
    assert saved["state"] == "needs_verification"


class _Resources:
    def __init__(self): self.items = {}
    def get(self, kind, identifier):
        if (kind, identifier) not in self.items: raise AndroidError("NOT_FOUND", "not found", 404)
        return self.items[(kind, identifier)]
    def save(self, kind, item): self.items[(kind, item["id"])] = item
    def list(self, kind): return [item for (stored_kind, _), item in self.items.items() if stored_kind == kind]


class _Devices:
    def __init__(self): self.items = {"d1": {"deviceId": "d1", "generation": 1, "control": "idle"}, "d2": {"deviceId": "d2", "generation": 2, "control": "idle"}}
    def get(self, identifier): return self.items[identifier]
    def operate(self, device_id, request): return {"deviceId": device_id, "operation": {"id": request["requestId"]}}


class _WorkspaceDevices:
    def __init__(self):
        self.items = {
            "d-a": {"deviceId": "d-a", "workspaceId": "ws-a", "generation": 1, "control": "idle"},
            "d-b": {"deviceId": "d-b", "workspaceId": "ws-b", "generation": 1, "control": "idle"},
        }
        self.requests = []

    def get(self, identifier):
        return self.items[identifier]

    def operate(self, device_id, request):
        self.requests.append((device_id, request))
        return {"deviceId": device_id, "operation": {"id": request["requestId"]}}


class _OperationDevices(_WorkspaceDevices):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.management = type("Management", (), {"workspace_identity": "ws-a", "operations": self})()

    def operate(self, device_id, request):
        self.requests.append((device_id, request))
        return {"deviceId": device_id, "operation": {"id": request["requestId"]}}

    def get(self, identifier, workspace=None):
        if identifier == "r-cancelled:d-a:1":
            return type("Operation", (), {"state": self.state, "message": None, "workspace_identity": "ws-a"})()
        return self.items[identifier]


class _CancelledDevices(_WorkspaceDevices):
    def __init__(self):
        super().__init__()
        self.management = type("Management", (), {"workspace_identity": "ws-a"})()

    def operate(self, _device_id, _request):
        raise asyncio.CancelledError


class _Management:
    def __init__(self):
        self.calls = []

    def operate(self, device_id, request):
        self.calls.append((device_id, request))
        return {"deviceId": device_id, "operation": {"id": request["requestId"]}}


class _Repository:
    def get(self, identifier):
        if identifier != "d1":
            raise AndroidError("NOT_FOUND", "not found", 404)
        return {"deviceId": "d1", "generation": 1, "control": "idle"}


class _QueueRuntime:
    def __init__(self):
        self.ready = False

    async def capacity(self, _device):
        if not self.ready:
            raise AndroidError("ANDROID_CAPACITY_UNKNOWN", "unknown")


class _QueueDevices:
    def __init__(self):
        self.items = {
            "d1": {"deviceId": "d1", "generation": 1, "control": "idle"},
            "d2": {"deviceId": "d2", "generation": 1, "control": "idle"},
        }
        self.runtime = _QueueRuntime()
        self.calls = []

    def get(self, identifier):
        return self.items[identifier]

    def operate(self, device_id, request):
        self.calls.append((device_id, request))
        self.items[device_id]["operation"] = {"id": request["requestId"], "state": "running"}
        return {"deviceId": device_id, "operation": {"id": request["requestId"]}}


class _RetryDevices(_QueueDevices):
    def __init__(self):
        super().__init__()
        self.requests = []

    def operate(self, device_id, request):
        self.requests.append(request["requestId"])
        if len(self.requests) == 1:
            raise AndroidError("ANDROID_PARTIAL_FAILURE", "failed")
        return super().operate(device_id, request)
