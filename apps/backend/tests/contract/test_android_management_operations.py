from types import SimpleNamespace

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

        async def pull(self, _reference):
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
