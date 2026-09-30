import asyncio
import hashlib
import json
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.devices import AndroidDeviceService
from autoflow.application.android.diagnostics import EnvironmentCheckService
from autoflow.application.android.images import AndroidImageService
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
from autoflow.providers.android import mac_runtime as mac
from autoflow.providers.android.image_catalog import ImageCatalog


def test_operation_routes_expose_idempotent_receipts_and_verification(tmp_path):
    database = tmp_path / "operations.sqlite3"
    migrate_database(database)
    operations = SqlAlchemyAndroidOperationRepository(create_session_factory(database))
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(type("Runtime", (), {"environment": lambda _self: None})()), operations))

    with TestClient(app) as client:
        response = client.get("/api/v1/android/management/operations/by-request/r1")

    assert response.status_code == 404


def test_unknown_operation_is_never_marked_verified_without_observation(tmp_path):
    database = tmp_path / "unknown.sqlite3"
    migrate_database(database)
    operations = SqlAlchemyAndroidOperationRepository(create_session_factory(database))
    original = operations.accept("default", "lost", "device", "delete", "hash", {})
    operations.transition(original.operation_id, "queued", "running", {})
    operations.transition(original.operation_id, "running", "needs_verification", {})
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations))
    with TestClient(app) as client:
        response = client.post(f"/api/v1/android/management/operations/{original.operation_id}/verify", json={"requestId": "lost"})
    assert response.status_code == 503
    assert operations.get(original.operation_id).state == "needs_verification"


def test_delete_verification_does_not_treat_runtime_not_found_as_success(tmp_path):
    database = tmp_path / "delete-runtime-missing.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    repository = SqlAlchemyDeviceRepository(sessions)

    class Runtime:
        async def inspect(self, _device):
            raise AndroidError("ANDROID_NOT_FOUND", "runtime object unavailable", 404)

    device = {
        "deviceId": "device-delete-missing",
        "name": "delete target",
        "workspaceId": "default",
        "control": "recovery_required",
        "generation": 2,
        "androidStatus": "unknown",
        "operation": {"id": "delete-op", "action": "delete", "state": "needs_verification"},
    }
    repository.save(device)
    record = operations.accept(
        "default",
        "delete-runtime-missing",
        device["deviceId"],
        "delete",
        "delete-digest",
        {"deleteData": True},
    )
    operations.transition(record.operation_id, "queued", "running", {})
    operations.transition(record.operation_id, "running", "needs_verification", {})
    devices = AndroidDeviceService(repository, Runtime())
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations, devices=devices))

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/android/management/operations/{record.operation_id}/verify",
            json={"requestId": record.request_id},
        )

    assert response.status_code == 503, response.text
    assert operations.get(record.operation_id).state == "needs_verification"
    sessions.dispose()


@pytest.mark.parametrize(("delete_data", "status"), [(True, "missing"), (False, "retained")])
def test_delete_verification_uses_owned_container_and_volume_after_crash(tmp_path, delete_data, status):
    database = tmp_path / f"delete-crash-{delete_data}.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    repository = SqlAlchemyDeviceRepository(sessions)

    class Runtime:
        workspace_id = "default"

        async def inspect(self, _device):
            raise AndroidError("ANDROID_NOT_FOUND", "container was removed", 404)

        async def verify_deleted(self, _device):
            return {"androidStatus": status}

    device = {"deviceId": "device-delete-crashed", "name": "delete target", "workspaceId": "default", "control": "recovery_required", "generation": 2, "androidStatus": "unknown", "dataRetained": False, "deleted": False}
    repository.save(device)
    record = operations.accept("default", f"delete-crashed-{delete_data}", device["deviceId"], "delete", "digest", {"deleteData": delete_data})
    device["operation"] = {"id": record.operation_id, "action": "delete", "state": "needs_verification"}
    repository.save(device)
    operations.transition(record.operation_id, "queued", "running", {})
    operations.transition(record.operation_id, "running", "needs_verification", {})
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(Runtime()), operations, devices=AndroidDeviceService(repository, Runtime())))
    with TestClient(app) as client:
        response = client.post(f"/api/v1/android/management/operations/{record.operation_id}/verify", json={"requestId": record.request_id})
    assert response.status_code == 200, response.text
    assert repository.get(device["deviceId"])["androidStatus"] == status
    assert operations.get(record.operation_id).state == "succeeded"
    sessions.dispose()


def test_operation_page_total_is_not_just_the_current_page(tmp_path):
    database = tmp_path / "page.sqlite3"
    migrate_database(database)
    operations = SqlAlchemyAndroidOperationRepository(create_session_factory(database))
    operations.accept("default", "r1", "device", "start", "a", {})
    operations.accept("default", "r2", "device", "stop", "b", {})
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations))
    with TestClient(app) as client:
        response = client.get("/api/v1/android/management/operations?limit=1")
    assert response.status_code == 200
    assert response.json()["total"] == 2


@pytest.mark.parametrize(("limit", "count", "has_next"), [(50, 50, False), (50, 51, True), (200, 200, False), (200, 201, True)])
def test_operation_page_has_next_only_when_another_device_operation_exists(tmp_path, limit, count, has_next):
    database = tmp_path / "page-boundary.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    for index in range(count):
        operations.accept("default", f"request-{index}", "device", "start", f"digest-{index}", {})
    operations.accept("default", "other-device", "other", "start", "other", {})
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations))

    with TestClient(app) as client:
        response = client.get(f"/api/v1/android/management/operations?deviceId=device&limit={limit}")

    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == limit
    assert response.json()["total"] == count
    assert bool(response.json()["nextCursor"]) is has_next
    sessions.dispose()


def test_operation_cursor_must_belong_to_same_workspace_and_device(tmp_path):
    database = tmp_path / "cursor-scope.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    operations.accept("default", "own", "device", "start", "own", {})
    other_device = operations.accept("default", "other-device", "other", "start", "other", {})
    other_workspace = operations.accept("foreign", "other-workspace", "device", "start", "foreign", {})

    for cursor in (other_device.operation_id, other_workspace.operation_id):
        with pytest.raises(AndroidError) as raised:
            operations.page("device", cursor, 50, workspace_identity="default")
        assert raised.value.code == "ANDROID_OPERATION_CURSOR_INVALID"
    sessions.dispose()


def test_operation_accept_rejects_target_ids_that_cannot_fit_migration(tmp_path):
    database = tmp_path / "target-length.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)

    with pytest.raises(AndroidError) as raised:
        operations.accept("default", "request", "x" * 37, "pull", "digest", {})
    assert raised.value.code == "ANDROID_OPERATION_TARGET_INVALID"
    assert raised.value.status == 422
    sessions.dispose()


def test_retry_operation_records_parent_and_increments_attempt(tmp_path):
    database = tmp_path / "retry-lineage.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    original = operations.accept("default", "original", "device", "stop", "digest", {})
    operations.transition(original.operation_id, "queued", "running", {})
    operations.transition(original.operation_id, "running", "failed", {})

    retry = operations.accept(
        "default", "retry", "device", "stop", "retry-digest", {}, retry_of=original.operation_id
    )

    assert retry.retry_of == original.operation_id
    assert retry.attempt == original.attempt + 1
    sessions.dispose()


def test_image_pull_uses_a_stable_uuid_target_that_fits_operation_schema(tmp_path):
    database = tmp_path / "image-pull.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    resources = AndroidResourceRepository(sessions)

    class Runtime:
        async def environment(self):
            return {"available": True, "platformSupported": True, "runtimeId": "test", "images": []}

    class Catalog:
        calls = 0

        async def pull(self, _reference, *, allow_unknown_disk_estimate=False):
            self.calls += 1
            return SimpleNamespace(
                image_id="sha256:" + "a" * 64,
                source_digest=None,
                architecture="arm64",
                os="linux",
                android_version="14",
                google_components="none",
            )

    class Devices:
        runtime = Runtime()

        def list(self):
            return []

    catalog = Catalog()
    images = AndroidImageService(resources, Devices(), catalog)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(Devices.runtime), operations, images=images))

    with TestClient(app) as client:
        first = client.post(
            "/api/v1/android/management/image-pulls",
            json={"requestId": "pull-1", "reference": "repo/android:14"},
        )
        second = client.post(
            "/api/v1/android/management/image-pulls",
            json={"requestId": "pull-1", "reference": "repo/android:14"},
        )

    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    first_operation = operations.by_request("default", "pull-1")
    assert len(first_operation.target_id) <= 36
    assert first_operation.target_id != "image"
    assert first_operation.target_id == second.json()["targetId"]
    assert catalog.calls == 1
    sessions.dispose()


def test_pull_disk_confirmation_is_persisted_and_replay_does_not_repeat_preflight(tmp_path):
    database = tmp_path / "image-pull-disk.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    resources = AndroidResourceRepository(sessions)

    class Catalog:
        def __init__(self):
            self.calls = []

        async def pull(self, _reference, *, allow_unknown_disk_estimate=False):
            self.calls.append(allow_unknown_disk_estimate)
            if not allow_unknown_disk_estimate:
                raise AndroidError("ANDROID_DISK_ESTIMATE_UNKNOWN", "最终镜像占用未知，尚未开始拉取", 409)
            return SimpleNamespace(image_id="sha256:" + "a" * 64, source_digest=None, architecture="arm64", os="linux", android_version="13", google_components="none")

    class Devices:
        def list(self):
            return []

    catalog = Catalog()
    images = AndroidImageService(resources, Devices(), catalog)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations, images=images))
    url = "/api/v1/android/management/image-pulls"
    base = {"requestId": "unconfirmed", "reference": "redroid/redroid:13"}
    unknown_payload = {"reference": "redroid/redroid:13", "allowUnknownDiskEstimate": True}
    unknown_digest = hashlib.sha256(json.dumps(unknown_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    unknown_target = str(uuid5(NAMESPACE_URL, "default/android-image-pull/unknown"))
    unknown = operations.accept("default", "unknown", unknown_target, "pull", unknown_digest, unknown_payload)
    operations.transition(unknown.operation_id, "queued", "running", {})
    operations.transition(unknown.operation_id, "running", "needs_verification", {})
    with TestClient(app) as client:
        rejected = client.post(url, json=base)
        replay = client.post(url, json={**base, "allowUnknownDiskEstimate": False})
        conflict = client.post(url, json={**base, "allowUnknownDiskEstimate": True})
        approved = client.post(url, json={**base, "requestId": "confirmed", "allowUnknownDiskEstimate": True})
        approved_replay = client.post(url, json={**base, "requestId": "confirmed", "allowUnknownDiskEstimate": True})
        approved_conflict = client.post(url, json={**base, "requestId": "confirmed"})
        unknown_replay = client.post(url, json={**base, "requestId": "unknown", "allowUnknownDiskEstimate": True})
        unknown_conflict = client.post(url, json={**base, "requestId": "unknown"})
        invalid = client.post(url, json={**base, "requestId": "invalid", "allowUnknownDiskEstimate": "yes"})

    assert rejected.status_code == 409 and rejected.json()["error"]["code"] == "ANDROID_DISK_ESTIMATE_UNKNOWN"
    assert replay.status_code == 202 and replay.json()["state"] == "failed"
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "ANDROID_OPERATION_IDEMPOTENCY_CONFLICT"
    assert approved.status_code == approved_replay.status_code == 202
    assert approved.json()["state"] == approved_replay.json()["state"] == "succeeded"
    assert approved_conflict.status_code == 409 and approved_conflict.json()["error"]["code"] == "ANDROID_OPERATION_IDEMPOTENCY_CONFLICT"
    assert unknown_replay.status_code == 202 and unknown_replay.json()["state"] == "needs_verification"
    assert unknown_conflict.status_code == 409 and unknown_conflict.json()["error"]["code"] == "ANDROID_OPERATION_IDEMPOTENCY_CONFLICT"
    assert invalid.status_code == 422
    assert catalog.calls == [False, True]
    assert operations.by_request("default", "unconfirmed").payload == {"reference": "redroid/redroid:13"}
    assert operations.by_request("default", "confirmed").payload == {"reference": "redroid/redroid:13", "allowUnknownDiskEstimate": True}
    sessions.dispose()


@pytest.mark.asyncio
async def test_cancelled_disk_preflight_fails_persistent_pull_without_starting_docker(tmp_path, monkeypatch):
    database = tmp_path / "cancel-preflight.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    resources = AndroidResourceRepository(sessions)
    entered = asyncio.Event()
    never = asyncio.Event()
    docker_calls = []

    async def fake_run(argv, timeout=15, input_data=None):
        entered.set()
        await never.wait()
        return b""

    async def fake_docker(*args, **kwargs):
        docker_calls.append(args)
        return b""

    monkeypatch.setattr(mac, "run", fake_run)
    monkeypatch.setattr(mac, "docker", fake_docker)
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)

    class Devices:
        def list(self):
            return []

    images = AndroidImageService(resources, Devices(), ImageCatalog(runtime))
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations, images=images))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        task = asyncio.create_task(client.post("/api/v1/android/management/image-pulls", json={"requestId": "cancel-before-pull", "reference": "redroid/redroid:13", "allowUnknownDiskEstimate": True}))
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        replay = await client.post("/api/v1/android/management/image-pulls", json={"requestId": "cancel-before-pull", "reference": "redroid/redroid:13", "allowUnknownDiskEstimate": True})
    record = operations.by_request("default", "cancel-before-pull")
    assert record.state == replay.json()["state"] == "failed"
    assert record.result_code == "ANDROID_DISK_PREFLIGHT_CANCELLED"
    assert docker_calls == []
    sessions.dispose()


@pytest.mark.asyncio
async def test_cancelled_started_pull_still_requires_verification(tmp_path, monkeypatch):
    database = tmp_path / "cancel-pull.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    resources = AndroidResourceRepository(sessions)
    started = asyncio.Event()
    never = asyncio.Event()

    async def admitted(_self, *, allow_unknown_disk_estimate=False):
        return None

    async def fake_docker(*args, **kwargs):
        if args[0] == "pull":
            started.set()
            await never.wait()
        return b""

    monkeypatch.setattr(mac.MacAndroidRuntime, "require_vm_disk_space", admitted)
    monkeypatch.setattr(mac, "docker", fake_docker)
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)

    class Devices:
        def list(self):
            return []

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations, images=AndroidImageService(resources, Devices(), ImageCatalog(runtime))))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        task = asyncio.create_task(client.post("/api/v1/android/management/image-pulls", json={"requestId": "cancel-after-pull", "reference": "redroid/redroid:13", "allowUnknownDiskEstimate": True}))
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert operations.by_request("default", "cancel-after-pull").state == "needs_verification"
    sessions.dispose()


def test_verify_image_pull_is_read_only_and_finalizes_only_when_image_is_observed(tmp_path):
    database = tmp_path / "verify-image.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    resources = AndroidResourceRepository(sessions)
    image = {
        "id": "image-row",
        "imageId": "sha256:" + "b" * 64,
        "name": "repo/android:14",
        "reference": "repo/android:14",
        "revision": 1,
        "state": "registered",
        "verification": {"state": "unknown"},
        "createdAt": "2026-01-01T00:00:00+00:00",
        "requestId": "pull-unknown",
    }
    resources.save("image", image)
    record = operations.accept("default", "pull-unknown", "pull-target", "pull", "digest", {"reference": image["reference"]})
    operations.transition(record.operation_id, "queued", "running", {})
    operations.transition(record.operation_id, "running", "needs_verification", {})
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations, images=SimpleNamespace(list=lambda: resources.list("image"))))

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/android/management/operations/{record.operation_id}/verify",
            json={"requestId": "pull-unknown"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "succeeded"
    assert operations.get(record.operation_id).state == "succeeded"
    sessions.dispose()


def test_verify_second_pull_uses_its_receipt_not_the_original_image_request(tmp_path):
    import asyncio

    database = tmp_path / "verify-second-pull.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    resources = AndroidResourceRepository(sessions)
    image_id = "sha256:" + "c" * 64

    class Catalog:
        async def inspect(self, _reference):
            return SimpleNamespace(image_id=image_id, source_digest="sha256:" + "d" * 64, architecture="arm64", os="linux", android_version="13", google_components="unknown")

    class Devices:
        def list(self):
            return []

    images = AndroidImageService(resources, Devices(), Catalog())
    asyncio.run(images.pull("first-pull", "redroid/redroid:13"))
    asyncio.run(images.pull("second-pull", "redroid/redroid:13"))
    record = operations.accept("default", "second-pull", "pull-target", "pull", "digest", {"reference": "redroid/redroid:13"})
    operations.transition(record.operation_id, "queued", "running", {})
    operations.transition(record.operation_id, "running", "needs_verification", {})
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations, images=images))

    with TestClient(app) as client:
        response = client.post(f"/api/v1/android/management/operations/{record.operation_id}/verify", json={"requestId": "second-pull"})

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "succeeded"
    sessions.dispose()


def test_verify_environment_check_runs_a_read_only_probe(tmp_path):
    database = tmp_path / "verify-environment.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    record = operations.accept("default", "env-unknown", "environment", "check", "environment-check-v1", {})
    operations.transition(record.operation_id, "queued", "running", {})
    operations.transition(record.operation_id, "running", "needs_verification", {})

    class Runtime:
        calls = 0

        async def environment(self):
            self.calls += 1
            return {"available": True, "platformSupported": True, "runtimeId": "test", "images": []}

    runtime = Runtime()
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), operations))

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/android/management/operations/{record.operation_id}/verify",
            json={"requestId": "env-unknown"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "succeeded"
    assert runtime.calls == 1
    sessions.dispose()


def test_verify_backup_and_restore_are_read_only_observations(tmp_path):
    database = tmp_path / "verify-backups.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    resources = AndroidResourceRepository(sessions)
    backup = {
        "id": "backup-row",
        "deviceId": "device-source",
        "imageId": "sha256:" + "c" * 64,
        "workspaceId": "default",
        "requestId": "backup-unknown",
        "state": "available",
        "formatVersion": 1,
        "sha256": "d" * 64,
        "bytes": 10,
        "createdAt": "2026-01-01T00:00:00+00:00",
    }
    resources.save("backup", backup)
    backup_operation = operations.accept("default", "backup-unknown", "device-source", "backup", "backup-digest", {})
    operations.transition(backup_operation.operation_id, "queued", "running", {})
    operations.transition(backup_operation.operation_id, "running", "needs_verification", {})
    restore_id = "restore-target"
    restore_operation = operations.accept("default", "restore-unknown", restore_id, "restore", "restore-digest", {})
    operations.transition(restore_operation.operation_id, "queued", "running", {})
    operations.transition(restore_operation.operation_id, "running", "needs_verification", {})

    class Repository:
        def list(self):
            return [{"deviceId": restore_id, "restoreRequestId": "restore-unknown", "restoreState": "restored", "dataRetained": True}]

    class Devices:
        repository = Repository()

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations, backups=SimpleNamespace(resources=resources, workspace_identity="default"), devices=Devices()))

    with TestClient(app) as client:
        backup_response = client.post(
            f"/api/v1/android/management/operations/{backup_operation.operation_id}/verify",
            json={"requestId": "backup-unknown"},
        )
        restore_response = client.post(
            f"/api/v1/android/management/operations/{restore_operation.operation_id}/verify",
            json={"requestId": "restore-unknown"},
        )

    assert backup_response.status_code == 200, backup_response.text
    assert backup_response.json()["state"] == "succeeded"
    assert restore_response.status_code == 200, restore_response.text
    assert restore_response.json()["state"] == "succeeded"
    assert operations.get(backup_operation.operation_id).state == "succeeded"
    assert operations.get(restore_operation.operation_id).state == "succeeded"
    sessions.dispose()


def test_verify_cleanup_is_read_only_and_does_not_delete_again(tmp_path):
    database = tmp_path / "verify-cleanup.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    resources = AndroidResourceRepository(sessions)
    resources.save("cleanup-operation", {"id": "cleanup-row", "workspaceId": "default", "requestId": "cleanup-unknown", "state": "succeeded", "items": []})
    record = operations.accept("default", "cleanup-unknown", "cleanup", "cleanup", "cleanup-digest", {})
    operations.transition(record.operation_id, "queued", "running", {})
    operations.transition(record.operation_id, "running", "needs_verification", {})
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations, cleanup=SimpleNamespace(resources=resources)))

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/android/management/operations/{record.operation_id}/verify",
            json={"requestId": "cleanup-unknown"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "succeeded"
    assert resources.list("cleanup-operation")[0]["state"] == "succeeded"
    sessions.dispose()


@pytest.mark.parametrize(("child_state", "expected_parent"), [("succeeded", "succeeded"), ("failed", "needs_verification")])
def test_cleanup_operation_read_reconciles_async_child_without_replaying_delete(tmp_path, child_state, expected_parent):
    from autoflow.application.android.cleanup import CleanupService

    database = tmp_path / f"cleanup-async-{child_state}.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    resources = AndroidResourceRepository(sessions)
    child = operations.accept("default", "child-delete", "device", "delete", "child-digest", {"deleteData": True})
    operations.transition(child.operation_id, "queued", "running", {})
    parent = operations.accept("default", "cleanup-async", "cleanup", "cleanup", "parent-digest", {"previewId": "p"})
    operations.transition(parent.operation_id, "queued", "running", {})
    resources.save("cleanup-operation", {"id": "cleanup-row", "workspaceId": "default", "requestId": "cleanup-async", "previewId": "p", "state": "running", "items": [{"id": "device", "state": "running", "operationId": child.operation_id}]})
    service = CleanupService(resources, operations=operations)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations, cleanup=service))
    with TestClient(app) as client:
        assert client.get("/api/v1/android/management/operations/by-request/cleanup-async").json()["state"] == "running"
        operations.transition(child.operation_id, "running", child_state, {})
        response = client.get("/api/v1/android/management/operations/by-request/cleanup-async")
    assert response.status_code == 200, response.text
    assert response.json()["state"] == expected_parent
    assert resources.list("cleanup-operation")[0]["state"] == expected_parent
    sessions.dispose()


def test_cleanup_reconcile_never_completes_a_partially_recorded_multi_item_request(tmp_path):
    from autoflow.application.android.cleanup import CleanupService

    database = tmp_path / "cleanup-partial.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    resources = AndroidResourceRepository(sessions)
    parent = operations.accept("default", "cleanup-partial", "cleanup", "cleanup", "digest", {"previewId": "p"})
    operations.transition(parent.operation_id, "queued", "running", {})
    operations.transition(parent.operation_id, "running", "needs_verification", {})
    resources.save("cleanup-operation", {"id": "partial", "workspaceId": "default", "requestId": "cleanup-partial", "previewId": "p", "state": "running", "candidates": [{"id": "a"}, {"id": "b"}], "items": [{"id": "a", "state": "succeeded"}]})
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations, cleanup=CleanupService(resources, operations=operations)))
    with TestClient(app) as client:
        response = client.get("/api/v1/android/management/operations/by-request/cleanup-partial")
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "needs_verification"
    assert resources.list("cleanup-operation")[0]["state"] != "succeeded"
    sessions.dispose()


def test_verify_cleanup_matches_the_frozen_preview_id(tmp_path):
    database = tmp_path / "verify-cleanup-preview.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    resources = AndroidResourceRepository(sessions)
    resources.save(
        "cleanup-operation",
        {
            "id": "cleanup-row",
            "workspaceId": "default",
            "requestId": "cleanup-unknown",
            "previewId": "preview-1",
            "state": "succeeded",
            "items": [],
        },
    )
    record = operations.accept(
        "default",
        "cleanup-unknown",
        "cleanup",
        "cleanup",
        "cleanup-digest",
        {"previewId": "preview-1"},
    )
    operations.transition(record.operation_id, "queued", "running", {})
    operations.transition(record.operation_id, "running", "needs_verification", {})
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(
        android_management_router(
            EnvironmentCheckService(None),
            operations,
            cleanup=SimpleNamespace(resources=resources),
        )
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/android/management/operations/{record.operation_id}/verify",
            json={"requestId": "cleanup-unknown"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "succeeded"
    sessions.dispose()


def test_verify_lifecycle_commits_operation_and_device_projection_atomically(tmp_path):
    database = tmp_path / "verify-lifecycle.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    repository = SqlAlchemyDeviceRepository(sessions)

    class Runtime:
        async def inspect(self, _device):
            return {"androidStatus": "ready"}

        async def environment(self):
            return {"available": True, "platformSupported": True, "runtimeId": "test", "images": []}

    runtime = Runtime()
    devices = AndroidDeviceService(repository, runtime)
    device = {
        "deviceId": "device-atomic",
        "name": "atomic",
        "control": "recovery_required",
        "generation": 2,
        "androidStatus": "unknown",
        "operation": {"id": "op-atomic", "action": "start", "state": "needs_verification"},
    }
    repository.save(device)
    record = operations.accept("default", "start-unknown", device["deviceId"], "start", "start-digest", {})
    device["operation"]["id"] = record.operation_id
    repository.save(device)
    operations.transition(record.operation_id, "queued", "running", {})
    operations.transition(record.operation_id, "running", "needs_verification", {})
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), operations, devices=devices))

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/android/management/operations/{record.operation_id}/verify",
            json={"requestId": "start-unknown"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "succeeded"
    persisted = repository.get(device["deviceId"])
    assert persisted["control"] == "idle"
    assert persisted["operation"]["state"] == "succeeded"
    sessions.dispose()


@pytest.mark.parametrize(
    ("delete_data", "status"),
    [(False, "retained"), (False, "missing"), (True, "missing")],
)
def test_verify_delete_accepts_the_observed_post_delete_state(tmp_path, delete_data, status):
    database = tmp_path / f"verify-delete-{delete_data}-{status}.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    repository = SqlAlchemyDeviceRepository(sessions)

    class Runtime:
        async def inspect(self, _device):
            return {"androidStatus": status}

    runtime = Runtime()
    devices = AndroidDeviceService(repository, runtime)
    device = {
        "deviceId": "device-delete",
        "name": "delete target",
        "control": "recovery_required",
        "generation": 2,
        "androidStatus": "unknown",
        "operation": {"id": "delete-op", "action": "delete", "state": "needs_verification"},
    }
    repository.save(device)
    record = operations.accept(
        "default",
        f"delete-unknown-{delete_data}-{status}",
        device["deviceId"],
        "delete",
        "delete-digest",
        {"deleteData": delete_data},
    )
    device["operation"]["id"] = record.operation_id
    repository.save(device)
    operations.transition(record.operation_id, "queued", "running", {})
    operations.transition(record.operation_id, "running", "needs_verification", {})

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), operations, devices=devices))

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/android/management/operations/{record.operation_id}/verify",
            json={"requestId": record.request_id},
        )

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "succeeded"
    assert operations.get(record.operation_id).state == "succeeded"
    sessions.dispose()


def test_unknown_pull_history_survives_restart_with_scoped_filtered_pagination(tmp_path):
    database = tmp_path / "pull-history.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    records = []
    for workspace, action, state in [
        ("default", "pull", "running"),
        ("default", "pull", "needs_verification"),
        ("foreign", "pull", "needs_verification"),
        ("default", "stop", "needs_verification"),
        ("default", "pull", "succeeded"),
    ]:
        record = operations.accept(workspace, f"request-{len(records)}", f"target-{len(records)}", action, "digest", {})
        operations.transition(record.operation_id, "queued", "running", {})
        if state != "running":
            operations.transition(record.operation_id, "running", state, {})
        records.append(record)
    sessions.dispose()
    sessions = create_session_factory(database)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    operations.recover_running("default")
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations))
    query = "/api/v1/android/management/operations?action=pull&state=needs_verification&limit=1"
    with TestClient(app) as client:
        first = client.get(query)
        assert first.status_code == 200, first.text
        assert first.json()["total"] == 2
        assert [item["operationId"] for item in first.json()["items"]] == [records[1].operation_id]
        second = client.get(f"{query}&cursor={first.json()['nextCursor']}")
        assert second.status_code == 200, second.text
        assert [item["operationId"] for item in second.json()["items"]] == [records[0].operation_id]
        assert second.json()["nextCursor"] is None
        assert second.json()["total"] == 2
        for other in records[2:]:
            assert client.get(f"{query}&cursor={other.operation_id}").status_code == 422
    sessions.dispose()
