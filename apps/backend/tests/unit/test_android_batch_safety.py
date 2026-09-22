import pytest

from autoflow.adapters.http.android_fleet_schemas import BatchCreate
from autoflow.application.android.fleet import AndroidFleet
from autoflow.domain.android.ports import AndroidError


def test_batch_defaults_to_one_persistent_instance():
    item = BatchCreate.model_validate({"batchId": "33333333-3333-4333-8333-333333333333", "profileId": "22222222-2222-4222-8222-222222222222", "profileRevision": 1, "name": "设备"})
    assert item.quantity == 1 and item.instance_type == "persistent"


def test_temporary_instances_are_rejected_with_stable_error_code():
    payload = {"batchId": "33333333-3333-4333-8333-333333333333", "profileId": "22222222-2222-4222-8222-222222222222", "profileRevision": 1, "name": "设备", "instanceType": "temporary"}
    assert BatchCreate.model_validate(payload).instance_type == "temporary"

    class _Resources:
        def get(self, _kind, _identifier):
            raise AndroidError("NOT_FOUND", "not found", 404)

        def save(self, *_args):
            raise AssertionError("temporary request must be rejected before persistence")

    fleet = AndroidFleet(None, _Resources(), None, None)
    with pytest.raises(AndroidError) as raised:
        fleet.batch(BatchCreate.model_validate(payload).model_dump(by_alias=True, mode="json"))
    assert raised.value.code == "ANDROID_TEMPORARY_DISABLED"


def test_temporary_allocation_replay_returns_existing_record_before_rejection():
    request = {
        "requestId": "request-1",
        "workflowId": "workflow-1",
        "profileId": "profile-1",
        "mode": "temporary",
        "values": {},
    }

    class _Resources:
        def __init__(self):
            self.items = {("allocation", "request-1"): {"id": "request-1", "request": request, "state": "succeeded"}}

        def get(self, kind, identifier):
            if (kind, identifier) not in self.items:
                raise AndroidError("NOT_FOUND", "not found", 404)
            return self.items[(kind, identifier)]

        def list(self, _kind):
            return []

    fleet = AndroidFleet(None, _Resources(), None, None)
    assert fleet.allocate(request)["id"] == "request-1"
    fleet.resources.items.clear()
    with pytest.raises(AndroidError) as raised:
        fleet.allocate(request)
    assert raised.value.code == "ANDROID_TEMPORARY_DISABLED"
