from types import SimpleNamespace

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


@pytest.mark.asyncio
async def test_batch_copy_uses_owned_source_device_snapshot_instead_of_client_values():
    source_id = "11111111-1111-4111-8111-111111111111"
    source_config = {
        "deviceId": source_id,
        "name": "原实例",
        "imageId": "sha256:" + "a" * 64,
        "dpi": 420,
        "cpu": 4,
        "memoryMb": 4096,
        "width": 1080,
        "height": 1920,
        "profileId": "22222222-2222-4222-8222-222222222222",
        "profileName": "历史模板",
        "profileRevision": 7,
        "locale": "en-US",
        "timezone": "UTC",
        "start": False,
    }

    class _Repository:
        def get(self, identifier):
            if identifier == source_id:
                return {
                    "deviceId": source_id,
                    "workspaceId": "workspace-a",
                    "deleted": False,
                    "creationConfig": source_config,
                }
            raise AndroidError("ANDROID_NOT_FOUND", "not found", 404)

    class _Resources:
        def __init__(self):
            self.items = {}

        def get(self, kind, identifier):
            try:
                return self.items[(kind, identifier)]
            except KeyError:
                raise AndroidError("NOT_FOUND", "not found", 404) from None

        def save(self, kind, item):
            self.items[(kind, item["id"])] = item

    class _Management:
        workspace_identity = "workspace-a"

        def __init__(self):
            self.created = []

        def create(self, config):
            self.created.append(config)

    management = _Management()
    devices = SimpleNamespace(repository=_Repository(), management=management)
    fleet = AndroidFleet(devices, _Resources(), None, None)
    request = {
        "batchId": "33333333-3333-4333-8333-333333333333",
        "name": "复制实例",
        "profileId": "44444444-4444-4444-8444-444444444444",
        "profileRevision": 1,
        "sourceDeviceId": source_id,
        "quantity": 1,
        "instanceType": "persistent",
        "start": True,
        # These values are intentionally forged; sourceDeviceId must win.
        "width": 540,
        "height": 960,
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
    }
    result = fleet.batch(BatchCreate.model_validate(request).model_dump(by_alias=True))
    await fleet._device_step(result, result["items"][0])

    config = management.created[0]
    assert config["imageId"] == source_config["imageId"]
    assert config["dpi"] == source_config["dpi"]
    assert config["cpu"] == source_config["cpu"]
    assert config["memoryMb"] == source_config["memoryMb"]
    assert config["profileId"] == source_config["profileId"]
    assert config["profileRevision"] == source_config["profileRevision"]
    assert config["width"] == source_config["width"]
    assert config["height"] == source_config["height"]
    assert config["locale"] == source_config["locale"]
    assert config["timezone"] == source_config["timezone"]
    assert config["deviceId"] != source_id
    assert config["name"] == "复制实例 01"


def test_batch_copy_rejects_source_from_another_workspace():
    source_id = "11111111-1111-4111-8111-111111111111"

    class _Repository:
        def get(self, _identifier):
            return {
                "deviceId": source_id,
                "workspaceId": "workspace-b",
                "deleted": False,
                "creationConfig": {"imageId": "sha256:" + "a" * 64},
            }

    class _Resources:
        def get(self, _kind, _identifier):
            raise AndroidError("NOT_FOUND", "not found", 404)

        def save(self, *_args):
            raise AssertionError("foreign source must be rejected before persistence")

    devices = SimpleNamespace(
        repository=_Repository(),
        management=SimpleNamespace(workspace_identity="workspace-a"),
    )
    fleet = AndroidFleet(devices, _Resources(), None, None)
    request = {
        "batchId": "33333333-3333-4333-8333-333333333333",
        "name": "复制实例",
        "profileId": "44444444-4444-4444-8444-444444444444",
        "profileRevision": 1,
        "sourceDeviceId": source_id,
        "quantity": 1,
        "instanceType": "persistent",
        "start": True,
        "width": 720,
        "height": 1280,
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
    }
    with pytest.raises(AndroidError) as raised:
        fleet.batch(BatchCreate.model_validate(request).model_dump(by_alias=True))
    assert raised.value.code == "ANDROID_OWNERSHIP"


def test_batch_copy_uses_runtime_workspace_identity_when_management_uses_path():
    source_id = "11111111-1111-4111-8111-111111111111"

    class _Repository:
        def get(self, identifier):
            assert identifier == source_id
            return {
                "deviceId": source_id,
                "workspaceId": "runtime-workspace-hash",
                "deleted": False,
                "creationConfig": {
                    "imageId": "sha256:" + "a" * 64,
                    "dpi": 320,
                    "cpu": 1,
                    "memoryMb": 1536,
                    "width": 720,
                    "height": 1280,
                    "profileId": "22222222-2222-4222-8222-222222222222",
                    "profileRevision": 4,
                    "locale": "zh-CN",
                    "timezone": "Asia/Shanghai",
                },
            }

    class _Resources:
        def get(self, _kind, _identifier):
            raise AndroidError("NOT_FOUND", "not found", 404)

        def save(self, *_args):
            return None

    devices = SimpleNamespace(
        repository=_Repository(),
        runtime=SimpleNamespace(workspace_id="runtime-workspace-hash"),
        management=SimpleNamespace(workspace_identity="/Users/user/.autoflow/workspace"),
    )
    request = {
        "batchId": "33333333-3333-4333-8333-333333333333",
        "name": "复制实例",
        "profileId": "44444444-4444-4444-8444-444444444444",
        "profileRevision": 1,
        "sourceDeviceId": source_id,
        "quantity": 1,
        "instanceType": "persistent",
        "start": False,
        "width": 720,
        "height": 1280,
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
    }
    fleet = AndroidFleet(devices, _Resources(), None, None)
    assert fleet.batch(BatchCreate.model_validate(request).model_dump(by_alias=True))["state"] == "queued"
