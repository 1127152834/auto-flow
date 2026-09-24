from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.android_operations import (
    SqlAlchemyAndroidOperationRepository,
)
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


@pytest.fixture
def repository(tmp_path: Path) -> SqlAlchemyAndroidOperationRepository:
    database = tmp_path / "android-management.sqlite3"
    migrate_database(database)
    return SqlAlchemyAndroidOperationRepository(create_session_factory(database))


def test_request_id_is_idempotent_and_digest_conflict_is_rejected(repository):
    first = repository.accept("ws", "r1", "d1", "stop", "digest-a", {})
    again = repository.accept("ws", "r1", "d1", "stop", "digest-a", {})
    assert again.operation_id == first.operation_id
    with pytest.raises(AndroidError) as error:
        repository.accept("ws", "r1", "d2", "stop", "digest-b", {})
    assert error.value.status == 409


def test_transition_requires_expected_state_and_unknown_result_is_readable(repository):
    operation = repository.accept("ws", "r2", "d1", "start", "digest", {})
    running = repository.transition(operation.operation_id, "queued", "running", {"stage_code": "starting"})
    assert running.state == "running"
    with pytest.raises(AndroidError):
        repository.transition(operation.operation_id, "queued", "succeeded", {})
    unknown = repository.transition(operation.operation_id, "running", "needs_verification", {"message": "响应丢失"})
    assert unknown.state == "needs_verification"


def test_compaction_keeps_request_receipt(repository):
    first = repository.accept("ws", "old", "d", "stop", "hash", {"verbose": "detail"})
    repository.transition(first.operation_id, "queued", "cancelled", {})
    assert repository.compact(datetime.now(UTC) + timedelta(days=1)) == 1
    assert repository.by_request("ws", "old").operation_id == first.operation_id
    assert repository.accept("ws", "old", "d", "stop", "hash", {}).operation_id == first.operation_id
    with pytest.raises(AndroidError):
        repository.accept("ws", "old", "other", "stop", "other", {})


def test_terminal_operations_cannot_be_replayed(repository):
    first = repository.accept("ws", "closed", "d", "stop", "hash", {})
    repository.transition(first.operation_id, "queued", "cancelled", {})
    with pytest.raises(AndroidError):
        repository.transition(first.operation_id, "cancelled", "running", {})


def test_cursor_matches_timestamp_order(repository):
    expected = [repository.accept("ws", f"r{i}", "d", "stop", str(i), {}).operation_id for i in range(12)][::-1]
    seen = []
    cursor = None
    while page := repository.page(cursor=cursor, limit=2):
        seen.extend(item.operation_id for item in page)
        cursor = page[-1].operation_id
    assert seen == expected


def test_transition_with_device_commits_operation_and_projection_together(repository):
    device_repository = SqlAlchemyDeviceRepository(repository.sessions)
    operation = repository.accept("ws", "r-atomic", "d-atomic", "start", "digest", {})
    device = {"deviceId": "d-atomic", "control": "managing", "generation": 1, "operation": {"state": "running"}}

    running = repository.transition_with_device(operation.operation_id, "queued", "running", {"stage_code": "starting"}, device)

    assert running.state == "running"
    assert device_repository.get("d-atomic")["operation"]["state"] == "running"


@pytest.mark.asyncio
async def test_old_verification_cannot_overwrite_recovered_device_and_new_session(repository):
    import asyncio

    from autoflow.application.android.devices import AndroidDeviceService
    from autoflow.application.android.verification import verify_lifecycle_operation

    devices_repo = SqlAlchemyDeviceRepository(repository.sessions)
    old = repository.accept("ws", "old-start", "device", "start", "digest", {})
    repository.transition(old.operation_id, "queued", "running", {})
    old = repository.transition(old.operation_id, "running", "needs_verification", {})
    devices_repo.save({"deviceId": "device", "workspaceId": "ws", "generation": 2,
                       "ownerRunId": None, "control": "recovery_required", "androidStatus": "unknown",
                       "operation": {"id": old.operation_id, "action": "start", "state": "needs_verification"}})
    inspecting, release = asyncio.Event(), asyncio.Event()

    class Runtime:
        workspace_id = "ws"
        locked = False

        def lock(self):
            if self.locked:
                raise AndroidError("ANDROID_RUNTIME_BUSY", "busy", 409)
            self.locked = True

        def unlock(self):
            self.locked = False

        async def manage(self, device, request, stage, save):
            device["androidStatus"] = "ready"

        async def inspect(self, device):
            inspecting.set()
            await release.wait()
            return {"androidStatus": "ready"}

    devices = AndroidDeviceService(devices_repo, Runtime())
    devices.management.operations = repository
    devices.management.workspace_identity = "ws"
    verification = asyncio.create_task(verify_lifecycle_operation(repository, devices, old, workspace_identity="ws"))
    await inspecting.wait()
    devices.operate("device", {"requestId": "new-recover", "action": "recover", "deleteData": False})
    await devices.management.task
    current = devices_repo.claim("device", "new-session")
    current["control"] = "manual"
    devices_repo.save(current)
    release.set()
    try:
        await verification
    except AndroidError as error:
        assert error.status == 409
    assert devices_repo.get("device") == current
    assert current["generation"] == 4
    assert repository.get(old.operation_id).state == "needs_verification"


def test_verification_transaction_rejects_changed_device_snapshot(repository):
    devices = SqlAlchemyDeviceRepository(repository.sessions)
    operation = repository.accept("ws", "verify-cas", "d", "start", "digest", {})
    repository.transition(operation.operation_id, "queued", "running", {})
    repository.transition(operation.operation_id, "running", "needs_verification", {})
    original = {"deviceId": "d", "generation": 2, "control": "recovery_required"}
    devices.save(original | {"generation": 3, "control": "manual", "ownerRunId": "new-session"})
    with pytest.raises(AndroidError) as error:
        repository.transition_with_device(operation.operation_id, "needs_verification", "succeeded", {},
                                          original | {"control": "idle"}, expected_device=original)
    assert error.value.status == 409
    assert devices.get("d")["ownerRunId"] == "new-session"
    assert repository.get(operation.operation_id).state == "needs_verification"


@pytest.mark.asyncio
@pytest.mark.parametrize('changes', [
    {'operation': None},
    {'operation': {'id': 'newer-operation'}},
    {'pendingCommand': {'requestId': 'app-unknown'}},
    {'restoreState': 'pending'},
    {'restoreRequestId': 'restore-unknown'},
])
async def test_verification_preserves_current_operation_and_pending_isolation(repository, changes):
    from autoflow.application.android.devices import AndroidDeviceService
    from autoflow.application.android.verification import verify_lifecycle_operation

    devices = SqlAlchemyDeviceRepository(repository.sessions)
    operation = repository.accept('ws', 'verify-isolation', 'd', 'start', 'digest', {})
    repository.transition(operation.operation_id, 'queued', 'running', {})
    operation = repository.transition(operation.operation_id, 'running', 'needs_verification', {})
    original = {'deviceId': 'd', 'generation': 2, 'control': 'recovery_required',
                'operation': {'id': operation.operation_id, 'state': 'needs_verification'}} | changes
    devices.save(original)

    class Runtime:
        async def inspect(self, device):
            return {'androidStatus': 'ready'}

    with pytest.raises(AndroidError) as error:
        await verify_lifecycle_operation(repository, AndroidDeviceService(devices, Runtime()), operation, workspace_identity='ws')
    assert error.value.status == 409
    assert devices.get('d') == original
    assert repository.get(operation.operation_id).state == 'needs_verification'


@pytest.mark.asyncio
async def test_verification_allows_confirmed_permanent_disposal_of_pending_restore(repository):
    from autoflow.application.android.devices import AndroidDeviceService
    from autoflow.application.android.verification import verify_lifecycle_operation

    devices = SqlAlchemyDeviceRepository(repository.sessions)
    operation = repository.accept('ws', 'delete-pending', 'd', 'delete', 'digest', {'deleteData': True})
    repository.transition(operation.operation_id, 'queued', 'running', {})
    operation = repository.transition(operation.operation_id, 'running', 'needs_verification', {})
    devices.save({'deviceId': 'd', 'generation': 2, 'control': 'recovery_required', 'restoreState': 'pending',
                  'operation': {'id': operation.operation_id, 'state': 'needs_verification'}})

    class Runtime:
        async def verify_deleted(self, device):
            return {'androidStatus': 'missing'}

    result = await verify_lifecycle_operation(repository, AndroidDeviceService(devices, Runtime()), operation, workspace_identity='ws')
    assert result.state == 'succeeded'
    assert devices.get('d')['deleted'] is True
    assert devices.get('d')['restoreState'] == 'pending'
