
from autoflow.application.android.bulk import AndroidBulkService
from autoflow.domain.android.ports import AndroidError


def test_bulk_freezes_targets_and_keeps_partial_failures():
    resources = _Resources()
    devices = _Devices()
    service = AndroidBulkService(resources, devices)
    batch = service.create("ws", "r1", "stop", [{"deviceId": "d1", "expectedRevision": 1}, {"deviceId": "d2", "expectedRevision": 9}], False)
    assert [item["deviceId"] for item in batch["items"]] == ["d1", "d2"]
    result = service.run(batch["id"])
    assert result["state"] == "partially_failed"
    assert result["items"][0]["state"] in {"queued", "accepted", "succeeded"}
    assert result["items"][1]["state"] == "failed"


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
