import asyncio
from unittest.mock import AsyncMock

import pytest

from autoflow.adapters.http.android_management import _management_device
from autoflow.application.android.management import AndroidManagement
from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.providers.android.mac_runtime import MacAndroidRuntime

TARGET = "acc0a4ce-3b23-4772-b61e-e6c0727686a5"


def repository(tmp_path):
    database = tmp_path / "restore.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    return sessions, SqlAlchemyDeviceRepository(sessions)


def pending():
    return {"deviceId": TARGET, "workspaceId": "workspace", "imageId": "image", "generation": 2, "control": "idle", "androidStatus": "stopped", "restoreState": "pending", "restoreRequestId": "restore-request", "restoreBackupId": "backup", "creationConfig": {"restoreRequestId": "restore-request", "restoreBackupId": "backup", "start": False}}


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["start", "restart", "restore"])
async def test_reconstructed_management_cannot_start_an_unpublished_restore(tmp_path, action):
    sessions, repo = repository(tmp_path)
    repo.save(pending())
    runtime = MacAndroidRuntime(tmp_path, tmp_path)
    runtime.manage = AsyncMock()
    management = AndroidManagement(repo, runtime)
    try:
        with pytest.raises(AndroidError) as error:
            management.operate(TARGET, {"requestId": "new-request", "action": action, "deleteData": False})
        assert error.value.code == "ANDROID_RESTORE_INCOMPLETE"
    finally:
        if management.task is not None:
            await management.task
    runtime.manage.assert_not_awaited()
    sessions.dispose()


def test_control_claim_rejects_legacy_pending_restore_intent(tmp_path):
    sessions, repo = repository(tmp_path)
    device = pending()
    device.pop("restoreState")
    device.pop("restoreRequestId")
    repo.save(device)
    with pytest.raises(AndroidError) as error:
        repo.claim(TARGET, "console")
    assert error.value.code == "ANDROID_RESTORE_INCOMPLETE"
    assert repo.get(TARGET)["control"] == "idle"
    sessions.dispose()


@pytest.mark.asyncio
async def test_direct_runtime_connect_refuses_pending_restore_before_io(tmp_path):
    runtime = MacAndroidRuntime(tmp_path, tmp_path)
    runtime.inspect = AsyncMock()
    with pytest.raises(AndroidError) as error:
        await runtime.connect(pending(), lambda: None)
    assert error.value.code == "ANDROID_RESTORE_INCOMPLETE"
    runtime.inspect.assert_not_awaited()


def test_projection_offers_no_start_or_open_for_pending_restore():
    item = _management_device(pending())
    assert item.model_dump(by_alias=True)["restoreState"] == "pending"
    assert set(item.allowed_actions) == {"verify", "delete"}
    assert "恢复" in item.blocked_reasons["start"]


@pytest.mark.asyncio
async def test_creation_persists_restore_intent_before_runtime_provisioning(tmp_path):
    sessions, repo = repository(tmp_path)
    runtime = MacAndroidRuntime(tmp_path, tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()

    async def provision(device, _request, _stage, save):
        entered.set()
        await release.wait()
        device["androidStatus"] = "stopped"
        save()

    runtime.manage = provision
    # Keep the production new_device behaviour, but replace process/device IO.
    runtime.for_device = lambda _identifier: runtime
    management = AndroidManagement(repo, runtime)
    runtime.lock = lambda: None
    runtime.unlock = lambda: None
    config = {"deviceId": TARGET, "name": "restore", "imageId": "image", "width": 720, "height": 1280, "dpi": 320, "cpu": 1, "memoryMb": 1536, "start": False, "restoreRequestId": "request", "restoreBackupId": "backup"}
    management.create(config)
    try:
        await asyncio.wait_for(entered.wait(), 2)
        stored = repo.get(TARGET)
        assert stored.get("restoreState") == "pending"
        assert stored.get("restoreRequestId") == "request"
        assert stored.get("restoreBackupId") == "backup"
    finally:
        release.set()
        await management.task
        sessions.dispose()


@pytest.mark.parametrize("mutation", ["generation", "request", "backup", "deleted"])
def test_restore_completion_is_bound_to_current_device_and_request(tmp_path, mutation):
    from autoflow.infrastructure.database.android_operations import (
        SqlAlchemyAndroidOperationRepository,
    )
    sessions, repo = repository(tmp_path)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    device = pending()
    repo.save(device)
    operation = operations.accept("workspace", "restore-request", TARGET, "restore", "digest", {"backupId": "backup"})
    operations.transition(operation.operation_id, "queued", "running", {})
    completion = {**device, "restoreState": "restored"}
    if mutation == "generation":
        repo.save({**device, "generation": 3})
    elif mutation == "request":
        completion["restoreRequestId"] = "other"
    elif mutation == "backup":
        completion["restoreBackupId"] = "other"
    else:
        repo.save({**device, "deleted": True})
    with pytest.raises(AndroidError) as error:
        operations.transition_with_device(operation.operation_id, "running", "succeeded", {}, completion)
    assert error.value.code == "ANDROID_OPERATION_STATE_CONFLICT"
    assert operations.get(operation.operation_id).state == "running"
    assert repo.get(TARGET)["restoreState"] == "pending"
    sessions.dispose()

@pytest.mark.asyncio
async def test_restore_creation_never_autostarts_before_data_is_published(tmp_path):
    sessions, repo = repository(tmp_path)
    runtime = MacAndroidRuntime(tmp_path, tmp_path)
    runtime.manage = AsyncMock()
    runtime.lock = lambda: None
    runtime.unlock = lambda: None
    runtime.for_device = lambda _identifier: runtime
    management = AndroidManagement(repo, runtime)
    config = {"deviceId": TARGET, "name": "unsafe", "imageId": "image", "width": 720, "height": 1280, "dpi": 320, "cpu": 1, "memoryMb": 1536, "start": True, "restoreRequestId": "request", "restoreBackupId": "backup"}
    try:
        with pytest.raises(AndroidError) as error:
            management.create(config)
        assert error.value.code == "ANDROID_RESTORE_INCOMPLETE"
    finally:
        if management.task:
            await management.task
        sessions.dispose()
    runtime.manage.assert_not_awaited()
