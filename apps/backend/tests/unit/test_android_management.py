import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from autoflow.adapters.http.android import AndroidCreate, AndroidDeviceCommand
from autoflow.adapters.http.android_fleet_schemas import BatchCreate
from autoflow.adapters.http.android_management_schemas import BackupRestore
from autoflow.application.android.management import AndroidManagement
from autoflow.domain.android.ports import AndroidDiskPreflightCancelled, AndroidError
from autoflow.providers.android import management as android_management_runtime
from autoflow.providers.android.mac_runtime import LABEL, MacAndroidRuntime
from autoflow.providers.android.management import manage


class Repository:
    def __init__(self):
        self.records = {}

    def get(self, identifier):
        if identifier not in self.records:
            raise AndroidError('ANDROID_NOT_FOUND', 'missing', 404)
        return deepcopy(self.records[identifier])

    def save(self, device):
        self.records[device['deviceId']] = deepcopy(device)


class Runtime:
    def __init__(self):
        self.locked = False
        self.gate = asyncio.Event()
        self.gate.set()
        self.calls = []
        self.fail = False

    def lock(self):
        if self.locked:
            raise AndroidError('ANDROID_RUNTIME_BUSY', 'busy')
        self.locked = True

    def unlock(self):
        self.locked = False

    def new_device(self, config):
        return {**config, 'control': 'idle', 'ownerRunId': None}

    async def manage(self, device, request, stage, save):
        self.calls.append(request['action'])
        stage('等待 Android 就绪')
        await self.gate.wait()
        if self.fail:
            raise AndroidError('ANDROID_PARTIAL_FAILURE', '保留已创建的数据，等待核实')
        device['androidStatus'] = 'ready'
        if request['action'] == 'delete':
            device['deleted'] = request['deleteData']
            device['dataRetained'] = not request['deleteData']
        if request['action'] == 'restore':
            device['dataRetained'] = False
        save()


@pytest.mark.asyncio
@pytest.mark.parametrize("control, action", [("recovery_required", "recover"), ("idle", "stop")])
async def test_recover_cannot_consume_unverified_application_completion_marker(control, action):
    repository = Repository()
    runtime = Runtime()
    repository.save({"deviceId": "device", "control": control, "generation": 3, "pendingCommand": "/data/local/tmp/autoflow-operation-" + "a" * 32})
    management = AndroidManagement(repository, runtime)

    with pytest.raises(AndroidError) as error:
        management.operate("device", {"requestId": "lifecycle-1", "action": action, "deleteData": False})

    assert error.value.code == "ANDROID_APP_OPERATION_UNVERIFIED"
    assert runtime.calls == []


@pytest.mark.asyncio
async def test_bulk_expected_revision_is_checked_after_runtime_lock_is_acquired():
    repository = Repository()
    repository.save({"deviceId": "device", "control": "idle", "generation": 1})

    class RacingRuntime(Runtime):
        def lock(self):
            super().lock()
            changed = repository.get("device")
            changed["generation"] = 2
            repository.save(changed)

    runtime = RacingRuntime()
    management = AndroidManagement(repository, runtime)
    with pytest.raises(AndroidError) as caught:
        management.operate("device", {"requestId": "stale-batch", "action": "stop", "deleteData": False, "expectedRevision": 2})
    assert caught.value.code == "ANDROID_REVISION_CONFLICT"
    assert repository.get("device")["generation"] == 2
    assert not runtime.locked


def config():
    return {'deviceId': str(uuid4()), 'name': 'test', 'imageId': 'sha256:' + 'a' * 64, 'width': 720, 'height': 1280, 'cpu': 1, 'memoryMb': 768, 'dpi': 320, 'start': True}


def request(action, delete=False):
    return {'requestId': str(uuid4()), 'action': action, 'deleteData': delete}


@pytest.mark.parametrize("model,payload", [
    (AndroidCreate, config()),
    (AndroidDeviceCommand, request("restore")),
    (BatchCreate, {"batchId": str(uuid4()), "name": "batch", "profileId": str(uuid4()), "profileRevision": 1}),
    (BackupRestore, {"requestId": "restore", "newName": "copy"}),
])
def test_disk_confirmation_contract_defaults_false_and_requires_real_boolean(model, payload):
    assert model.model_validate(payload).allow_unknown_disk_estimate is False
    assert model.model_validate({**payload, "allowUnknownDiskEstimate": True}).allow_unknown_disk_estimate is True
    with pytest.raises(ValueError):
        model.model_validate({**payload, "allowUnknownDiskEstimate": "true"})


@pytest.mark.asyncio
async def test_creation_is_durable_before_work_and_retries_never_create_twice():
    repo, runtime = Repository(), Runtime()
    service = AndroidManagement(repo, runtime)
    runtime.gate.clear()
    c = config()
    first = service.create(c)
    assert repo.get(c['deviceId'])['operation']['state'] == 'running'
    assert service.create(c) == first
    with pytest.raises(AndroidError):
        service.create({**c, 'name': 'changed'})
    with pytest.raises(AndroidError):
        service.create(config())
    assert service.busy()
    runtime.gate.set()
    await service.task
    assert runtime.calls == ['create'] and not runtime.locked
    assert repo.get(c['deviceId'])['control'] == 'idle'


@pytest.mark.asyncio
async def test_partial_failure_stays_reviewable_and_requires_explicit_recovery():
    repo, runtime = Repository(), Runtime()
    service = AndroidManagement(repo, runtime)
    c = config()
    runtime.fail = True
    service.create(c)
    await service.task
    assert repo.get(c['deviceId'])['control'] == 'recovery_required'
    with pytest.raises(AndroidError):
        service.operate(c['deviceId'], request('start'))
    runtime.fail = False
    service.operate(c['deviceId'], request('recover'))
    await service.task
    command = request('delete')
    service.operate(c['deviceId'], command)
    await service.task
    assert repo.get(c['deviceId'])['dataRetained'] and not repo.get(c['deviceId'])['deleted']
    service.operate(c['deviceId'], command)
    assert runtime.calls.count('delete') == 1
    service.operate(c['deviceId'], request('delete', True))
    await service.task
    assert repo.get(c['deviceId'])['deleted']
    with pytest.raises(AndroidError):
        service.operate(c['deviceId'], request('start'))


@pytest.mark.asyncio
async def test_retained_device_only_restarts_through_explicit_restore():
    repo, runtime = Repository(), Runtime()
    c = config()
    repo.save({**runtime.new_device(c), 'androidStatus': 'retained', 'dataRetained': True})
    service = AndroidManagement(repo, runtime)

    with pytest.raises(AndroidError) as blocked:
        service.operate(c['deviceId'], request('start'))
    assert blocked.value.code == 'ANDROID_DATA_RETAINED'
    assert runtime.calls == []

    service.operate(c['deviceId'], request('restore'))
    await service.task
    assert runtime.calls == ['restore']

    with pytest.raises(AndroidError) as rejected:
        service.operate(c['deviceId'], request('restore'))
    assert rejected.value.code == 'ANDROID_DATA_NOT_RETAINED'


@pytest.mark.asyncio
async def test_retained_restore_with_missing_volume_never_creates_blank_data(tmp_path, monkeypatch):
    runtime = MacAndroidRuntime(tmp_path, tmp_path / 'workspace')
    device = runtime.new_device(config())
    device.update(androidStatus='retained', dataRetained=True)
    monkeypatch.setattr(android_management_runtime, 'verify', AsyncMock(return_value=([], [])))
    monkeypatch.setattr(android_management_runtime, '_admit_image', AsyncMock())
    mutation = AsyncMock()
    monkeypatch.setattr(android_management_runtime, 'mutation', mutation)

    with pytest.raises(AndroidError) as error:
        await manage(runtime, device, request('restore'), lambda _stage: None, lambda: None)

    assert error.value.code == 'ANDROID_DATA_MISSING'
    mutation.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("action, volumes", [("create", []), ("restore", [{"Name": "owned"}])])
@pytest.mark.parametrize("code", ["ANDROID_DISK_ESTIMATE_UNKNOWN", "ANDROID_DISK_SPACE_INSUFFICIENT", "ANDROID_DISK_PROBE_FAILED"])
async def test_new_container_disk_rejection_precedes_every_docker_write(tmp_path, monkeypatch, action, volumes, code):
    runtime = MacAndroidRuntime(tmp_path, tmp_path / "workspace")
    device = runtime.new_device(config())
    device["creationConfig"] = {"start": False, **({"allowUnknownDiskEstimate": True} if action == "create" else {})}
    monkeypatch.setattr(android_management_runtime, "verify", AsyncMock(return_value=([], volumes)))
    monkeypatch.setattr(android_management_runtime, "_admit_image", AsyncMock())
    mutation = AsyncMock(return_value=b"container-id")
    monkeypatch.setattr(android_management_runtime, "mutation", mutation)
    disk_check = AsyncMock(side_effect=AndroidError(code, "disk blocked", 409))
    monkeypatch.setattr(runtime, "require_vm_disk_space", disk_check)

    with pytest.raises(AndroidError) as caught:
        await manage(runtime, device, {**request(action), "allowUnknownDiskEstimate": True}, lambda _: None, lambda: None)

    assert caught.value.code == code
    disk_check.assert_awaited_once_with(allow_unknown_disk_estimate=True)
    mutation.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirmed_creation_checks_disk_once_before_volume_and_container(tmp_path, monkeypatch):
    runtime = MacAndroidRuntime(tmp_path, tmp_path / "workspace")
    device = runtime.new_device(config())
    device["creationConfig"] = {"start": False, "allowUnknownDiskEstimate": True}
    monkeypatch.setattr(android_management_runtime, "verify", AsyncMock(return_value=([], [])))
    monkeypatch.setattr(android_management_runtime, "_admit_image", AsyncMock())
    writes = []

    async def mutation(_device, _save, *argv, **_kwargs):
        writes.append(argv[:2])
        return b"container-id"

    monkeypatch.setattr(android_management_runtime, "mutation", mutation)
    disk_check = AsyncMock(side_effect=lambda **_kwargs: writes.append(("disk-check",)))
    monkeypatch.setattr(runtime, "require_vm_disk_space", disk_check)

    await manage(runtime, device, request("create"), lambda _: None, lambda: None)

    assert writes == [("disk-check",), ("volume", "create"), ("create", "--name")]
    disk_check.assert_awaited_once_with(allow_unknown_disk_estimate=True)


@pytest.mark.asyncio
async def test_empty_create_retry_rejects_any_existing_owned_resource_before_write(tmp_path, monkeypatch):
    runtime = MacAndroidRuntime(tmp_path, tmp_path / "workspace")
    device = runtime.new_device(config())
    device["creationConfig"] = {"start": False, "allowUnknownDiskEstimate": True}
    monkeypatch.setattr(android_management_runtime, "verify", AsyncMock(return_value=([], [{"Name": device["volumeId"]}])))
    monkeypatch.setattr(android_management_runtime, "_admit_image", AsyncMock())
    disk_check = AsyncMock()
    monkeypatch.setattr(runtime, "require_vm_disk_space", disk_check)
    mutation = AsyncMock(return_value=b"container-id")
    monkeypatch.setattr(android_management_runtime, "mutation", mutation)

    with pytest.raises(AndroidError) as caught:
        await manage(runtime, device, {**request("create"), "retryEmptyCreate": True, "allowUnknownDiskEstimate": True}, lambda _: None, lambda: None)

    assert caught.value.code == "ANDROID_DATA_MISSING"
    disk_check.assert_not_awaited()
    mutation.assert_not_awaited()


@pytest.mark.asyncio
async def test_false_confirmation_keeps_old_create_and_restore_receipts():
    repo, runtime = Repository(), Runtime()
    service = AndroidManagement(repo, runtime)
    c = config()
    service.create(c)
    assert service.create({**c, "allowUnknownDiskEstimate": False})["deviceId"] == c["deviceId"]
    with pytest.raises(AndroidError, match="设备编号"):
        service.create({**c, "allowUnknownDiskEstimate": True})
    await service.task
    retained = repo.get(c["deviceId"])
    retained.update(dataRetained=True, control="idle")
    repo.save(retained)
    restore = request("restore")
    service.operate(c["deviceId"], restore)
    assert service.operate(c["deviceId"], {**restore, "allowUnknownDiskEstimate": False})["deviceId"] == c["deviceId"]
    with pytest.raises(AndroidError, match="操作编号"):
        service.operate(c["deviceId"], {**restore, "allowUnknownDiskEstimate": True})
    await service.task


@pytest.mark.asyncio
async def test_cancelled_create_disk_preflight_is_failed_without_unknown_side_effects():
    class CancelledRuntime(Runtime):
        async def manage(self, _device, _request, _stage, _save):
            raise AndroidDiskPreflightCancelled()

    repo, runtime = Repository(), CancelledRuntime()
    service = AndroidManagement(repo, runtime)
    c = config()
    service.create(c)
    await service.task

    stored = repo.get(c["deviceId"])
    assert stored["operation"]["state"] == "failed"
    assert stored["control"] == "idle"
    assert stored["lastError"] == "磁盘预检取消，尚未开始写入"
    assert not runtime.locked


@pytest.mark.asyncio
async def test_known_disk_rejection_keeps_failed_create_retryable_without_recovery():
    class RejectedRuntime(Runtime):
        async def manage(self, _device, _request, _stage, _save):
            raise AndroidError("ANDROID_DISK_ESTIMATE_UNKNOWN", "最终占用未知，尚未开始写入", 409)

    repo, runtime = Repository(), RejectedRuntime()
    service = AndroidManagement(repo, runtime)
    c = config()
    service.create(c)
    await service.task

    stored = repo.get(c["deviceId"])
    assert stored["operation"]["state"] == "failed"
    assert stored["control"] == "idle"
    assert stored["lastError"] == "最终占用未知，尚未开始写入"


@pytest.mark.asyncio
async def test_shutdown_marks_interrupted_and_busy_device_cannot_be_mutated():
    repo, runtime = Repository(), Runtime()
    service = AndroidManagement(repo, runtime)
    c = config()
    runtime.gate.clear()
    service.create(c)
    await asyncio.sleep(0)
    await service.shutdown()
    assert repo.get(c['deviceId'])['operation']['state'] == 'interrupted'
    assert repo.get(c['deviceId'])['control'] == 'recovery_required'
    assert not runtime.locked
    d = repo.get(c['deviceId']); d.update(ownerRunId='other', control='manual'); repo.save(d)
    other = AndroidManagement(repo, runtime)
    with pytest.raises(AndroidError):
        other.operate(c['deviceId'], request('delete', True))


@pytest.mark.asyncio
async def test_archived_operation_receipts_do_not_block_new_lifecycle_request():
    repo, runtime = Repository(), Runtime()
    c = config()
    device = runtime.new_device(c)
    device["operationReceipts"] = {
        f"old-{index}": {"requestId": f"old-{index}", "action": "stop", "deleteData": False}
        for index in range(1000)
    }
    repo.save(device)
    service = AndroidManagement(repo, runtime)

    service.operate(c["deviceId"], request("stop"))
    await service.task

    assert runtime.calls == ["stop"]


@pytest.mark.asyncio
async def test_external_timeout_marks_operation_needs_verification():
    repo, runtime = Repository(), TimeoutRuntime()
    service = AndroidManagement(repo, runtime)

    c = config()
    service.create(c)
    await service.task

    device = repo.get(c["deviceId"])
    assert device["control"] == "recovery_required"
    assert device["operation"]["state"] == "needs_verification"


def test_create_replayed_terminal_operation_releases_runtime_lock():
    repo, runtime = Repository(), Runtime()
    service = AndroidManagement(repo, runtime)

    class Operations:
        def accept(self, *_args, **_kwargs):
            return SimpleNamespace(state="succeeded", operation_id="already-done")

    service.operations = Operations()

    with pytest.raises(AndroidError, match="已处理"):
        service.create(config())

    assert not runtime.locked


class TimeoutRuntime(Runtime):
    async def manage(self, device, request, stage, save):
        raise TimeoutError("response lost")


@pytest.mark.asyncio
async def test_delete_refuses_foreign_volume_before_any_mutation(tmp_path, monkeypatch):
    runtime = MacAndroidRuntime(tmp_path, tmp_path / 'workspace')
    c = config()
    device = runtime.new_device(c)
    container = {'Config': {'Labels': {LABEL: runtime.workspace_id, 'io.autoflow.android.device': c['deviceId']}}, 'Mounts': [{'Name': device['volumeId'], 'Destination': '/data'}]}
    from autoflow.providers.android import management
    monkeypatch.setattr(management, 'objects', AsyncMock(side_effect=[[container], [{'Labels': {LABEL: 'foreign'}}]]))
    mutation = AsyncMock()
    monkeypatch.setattr(management, 'mutation', mutation)
    with pytest.raises(AndroidError, match='归属'):
        await manage(runtime, device, request('delete', True), lambda _: None, lambda: None)
    mutation.assert_not_called()


@pytest.mark.asyncio
async def test_restoration_records_intended_container_name_before_a_lost_create_response(tmp_path, monkeypatch):
    from autoflow.providers.android import management
    runtime = MacAndroidRuntime(tmp_path, tmp_path / 'workspace')
    device = runtime.new_device(config())
    device.update(containerId='old-removed-id', dataRetained=True)
    monkeypatch.setattr(management, 'verify', AsyncMock(return_value=([], [{}])))
    monkeypatch.setattr(management, 'images', AsyncMock(return_value=[{'id': device['imageId']}]))
    saved = []
    async def lost(*_args, **_kwargs):
        assert saved[-1]['containerId'] == 'autoflow-android-' + device['deviceId']
        raise TimeoutError
    monkeypatch.setattr(management, 'mutation', lost)
    disk_check = AsyncMock()
    monkeypatch.setattr(runtime, 'require_vm_disk_space', disk_check)
    with pytest.raises(TimeoutError):
        await manage(runtime, device, {**request('start'), 'allowUnknownDiskEstimate': True}, lambda _: None, lambda: saved.append(deepcopy(device)))
    disk_check.assert_awaited_once_with(allow_unknown_disk_estimate=True)


@pytest.mark.asyncio
async def test_image_discovery_inspects_requested_custom_digest(monkeypatch):
    custom = "sha256:" + "b" * 64

    async def fake_docker(*args, **_kwargs):
        assert args[:3] == ("image", "inspect", custom)
        return json.dumps([{"Id": custom, "Architecture": "arm64", "Os": "linux"}]).encode()

    monkeypatch.setattr(android_management_runtime, "docker", fake_docker)
    discovered = await android_management_runtime.images(custom)

    assert discovered == [{"id": custom, "name": "Android ARM64 镜像", "reference": custom}]


@pytest.mark.asyncio
async def test_recover_requires_catalog_and_runtime_admission_for_custom_digest(monkeypatch, tmp_path):
    custom = "sha256:" + "c" * 64
    runtime = MacAndroidRuntime(tmp_path, tmp_path / "workspace")
    runtime.image_catalog = type("Catalog", (), {"list": lambda _self: [{"imageId": custom, "state": "registered"}]})()
    device = runtime.new_device({**config(), "imageId": custom})

    admitted = []

    async def discover(image_id):
        admitted.append(image_id)
        return [{"id": image_id}]

    monkeypatch.setattr(android_management_runtime, "images", discover)
    monkeypatch.setattr(android_management_runtime, "verify", AsyncMock(return_value=([], [{}])))
    runtime.recover = AsyncMock()

    await manage(runtime, device, request("recover"), lambda _: None, lambda: None)

    assert admitted == [custom]
    runtime.recover.assert_awaited_once_with(device)
