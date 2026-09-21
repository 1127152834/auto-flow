import pytest
from pydantic import ValidationError

from autoflow.adapters.http.android_fleet_schemas import BatchCreate


def test_batch_defaults_to_one_persistent_instance():
    item = BatchCreate.model_validate({"batchId": "33333333-3333-4333-8333-333333333333", "profileId": "22222222-2222-4222-8222-222222222222", "profileRevision": 1, "name": "设备"})
    assert item.quantity == 1 and item.instance_type == "persistent"


def test_temporary_instances_are_rejected_from_management_entrypoint():
    with pytest.raises(ValidationError):
        BatchCreate.model_validate({"batchId": "33333333-3333-4333-8333-333333333333", "profileId": "22222222-2222-4222-8222-222222222222", "profileRevision": 1, "name": "设备", "instanceType": "temporary"})
