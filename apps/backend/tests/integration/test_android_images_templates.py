from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_fleet import android_fleet_router
from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.devices import AndroidDeviceService
from autoflow.application.android.diagnostics import EnvironmentCheckService
from autoflow.application.android.fleet import AndroidFleet
from autoflow.application.android.images import AndroidImageService
from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)

IMAGE_A = "sha256:" + "a" * 64
IMAGE_B = "sha256:" + "b" * 64
PROFILE_ID = "22222222-2222-4222-8222-222222222222"


@pytest.mark.parametrize("instance_type", ["persistent", "temporary"])
@pytest.mark.parametrize("source", [{}, {"sourceDeviceId": None}, {"sourceDeviceId": "11111111-1111-4111-8111-111111111111"}])
def test_persisted_batch_request_replays_through_current_http(tmp_path: Path, instance_type, source) -> None:
    sessions = _database(tmp_path)
    resources = AndroidResourceRepository(sessions)
    profile = {**_profile(), "revision": 1}
    profile.pop("archived")
    # a92f0688's BatchCreate dump had all these fields, quantity default 3,
    # and neither sourceDeviceId nor allowUnknownDiskEstimate.
    request = {**_batch_request(profile), "quantity": 3, "instanceType": instance_type, **source}
    saved = {
        "id": request["batchId"],
        "createdAt": "2026-09-21T12:00:00+00:00",
        "request": request,
        "profile": profile,
        "items": [{"deviceId": str(uuid4()), "name": f"快照实例 {i + 1:02d}", "state": "succeeded", "error": None} for i in range(3)],
        "state": "succeeded",
    }
    resources.save("batch", saved)
    sessions.dispose()
    sessions = create_session_factory(tmp_path / "android-images-templates.sqlite3")
    resources = AndroidResourceRepository(sessions)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_fleet_router(AndroidFleet(None, resources, None, None), None))
    try:
        with TestClient(app) as client:
            for replay_request in (request, {**request, "allowUnknownDiskEstimate": False}):
                replay = client.post("/api/v1/android/batches", json=replay_request)
                assert replay.status_code == 202, replay.text
                assert replay.json()["id"] == saved["id"]
                assert replay.json()["items"] == saved["items"]
                assert replay.json()["state"] == "succeeded"
            changed_source = None if source.get("sourceDeviceId") else "11111111-1111-4111-8111-111111111111"
            for change in ({"sourceDeviceId": changed_source}, {"allowUnknownDiskEstimate": True}):
                conflict = client.post("/api/v1/android/batches", json={**request, **change})
                assert conflict.status_code == 409
                assert conflict.json()["error"]["code"] == "ANDROID_REQUEST_CONFLICT"
            new_temporary = client.post("/api/v1/android/batches", json={**request, "batchId": str(uuid4()), "instanceType": "temporary"})
            assert new_temporary.status_code == 409
            assert new_temporary.json()["error"]["code"] == "ANDROID_TEMPORARY_DISABLED"
        assert resources.list("batch") == [saved]
    finally:
        sessions.dispose()


def test_image_and_pull_receipt_publish_in_one_sqlite_transaction(tmp_path: Path) -> None:
    sessions = _database(tmp_path)
    resources = AndroidResourceRepository(sessions)
    with pytest.raises(KeyError):
        resources.save_many([("image", {"id": str(uuid4()), "imageId": IMAGE_A}), ("image_pull_receipt", {"requestId": "interrupted"})])
    assert resources.list("image") == []
    assert resources.list("image_pull_receipt") == []
    sessions.dispose()


@pytest.mark.asyncio
async def test_image_profile_batch_restart_keeps_original_image_after_tag_retag(tmp_path: Path) -> None:
    sessions = _database(tmp_path)
    resources = AndroidResourceRepository(sessions)
    devices_repo = SqlAlchemyDeviceRepository(sessions)
    runtime = _ScenarioRuntime()
    devices = AndroidDeviceService(devices_repo, runtime)
    fleet = AndroidFleet(devices, resources, None, None)
    images = AndroidImageService(resources, devices, _ScenarioCatalog([IMAGE_A, IMAGE_B]))

    await images.register({"id": IMAGE_A, "name": "基础镜像", "reference": "redroid/redroid:13"})
    profile = fleet.save_profile(_profile(image_id=IMAGE_A))
    batch = fleet.batch(_batch_request(profile))
    await fleet.tick()
    await _wait_management(devices)
    await fleet.tick()

    created = devices_repo.get(batch["items"][0]["deviceId"])
    assert created["imageId"] == IMAGE_A
    assert created["creationConfig"]["imageId"] == IMAGE_A
    assert batch["profile"]["imageId"] == IMAGE_A

    # A registry tag may now point at a different immutable digest. The existing profile/device
    # keeps its frozen digest until the user explicitly edits the profile.
    await images.register({"id": IMAGE_B, "name": "基础镜像新摘要", "reference": "redroid/redroid:13"})
    edited = fleet.save_profile({**profile, "imageId": IMAGE_B, "revision": profile["revision"]})
    assert edited["revision"] == profile["revision"] + 1

    request = {"requestId": "restart-existing", "action": "restart", "deleteData": False}
    devices.management.operate(created["deviceId"], request)
    await _wait_management(devices)

    assert runtime.restart_images == [IMAGE_A]
    assert devices_repo.get(created["deviceId"])["imageId"] == IMAGE_A
    sessions.dispose()


@pytest.mark.asyncio
async def test_archive_increments_revision_and_archived_profile_cannot_create_batch(tmp_path: Path) -> None:
    sessions = _database(tmp_path)
    resources = AndroidResourceRepository(sessions)
    devices_repo = SqlAlchemyDeviceRepository(sessions)
    runtime = _ScenarioRuntime()
    devices = AndroidDeviceService(devices_repo, runtime)
    fleet = AndroidFleet(devices, resources, None, None)
    profile = fleet.save_profile(_profile())

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), profiles=resources))
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/android/management/profiles/{profile['id']}/archive",
            json={"requestId": "archive-1", "expectedRevision": profile["revision"]},
        )

    assert response.status_code == 200
    assert response.json()["revision"] == profile["revision"] + 1
    profile_id = profile["id"]
    with TestClient(app) as client:
        conflict = client.post(
            f"/api/v1/android/management/profiles/{profile_id}/archive",
            json={"requestId": "archive-stale", "expectedRevision": profile["revision"]},
        )
    assert conflict.status_code == 409
    archived = resources.get("profile", profile["id"])
    assert archived["archived"] is True
    assert archived["revision"] == profile["revision"] + 1

    with pytest.raises(AndroidError, match="归档"):
        fleet.batch(_batch_request(archived))
    sessions.dispose()


@pytest.mark.asyncio
async def test_batch_confirmation_is_frozen_and_source_confirmation_is_not_inherited(tmp_path: Path) -> None:
    sessions = _database(tmp_path)
    resources = AndroidResourceRepository(sessions)
    repository = SqlAlchemyDeviceRepository(sessions)
    devices = AndroidDeviceService(repository, _ScenarioRuntime())
    fleet = AndroidFleet(devices, resources, None, None)
    profile = fleet.save_profile(_profile())
    source = devices.runtime.new_device({**_batch_request(profile), "deviceId": str(uuid4()), "imageId": IMAGE_A})
    source["creationConfig"] = {**_batch_request(profile), "imageId": IMAGE_A, "dpi": 320, "cpu": 1, "memoryMb": 1536, "allowUnknownDiskEstimate": True}
    repository.save(source)

    plain = fleet.batch({**_batch_request(profile), "sourceDeviceId": source["deviceId"]})
    confirmed = fleet.batch({**_batch_request(profile), "allowUnknownDiskEstimate": True})
    with pytest.raises(AndroidError) as conflict:
        fleet.batch({**plain["request"], "allowUnknownDiskEstimate": True})
    assert conflict.value.code == "ANDROID_REQUEST_CONFLICT"
    await fleet.tick()
    await _wait_management(devices)
    await fleet.tick()
    await _wait_management(devices)

    assert "allowUnknownDiskEstimate" not in repository.get(plain["items"][0]["deviceId"])["creationConfig"]
    assert repository.get(confirmed["items"][0]["deviceId"])["creationConfig"]["allowUnknownDiskEstimate"] is True
    sessions.dispose()


def _database(tmp_path: Path):
    path = tmp_path / "android-images-templates.sqlite3"
    migrate_database(path)
    return create_session_factory(path)


def _profile(*, image_id: str = IMAGE_A) -> dict[str, Any]:
    return {
        "id": PROFILE_ID,
        "revision": 0,
        "name": "标准模板",
        "imageId": image_id,
        "width": 720,
        "height": 1280,
        "dpi": 320,
        "cpu": 1,
        "memoryMb": 1536,
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
        "shellRoot": "unknown",
        "applicationRoot": "unknown",
        "archived": False,
    }


def _batch_request(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "batchId": str(uuid4()),
        "name": "快照实例",
        "profileId": profile["id"],
        "profileRevision": profile["revision"],
        "quantity": 1,
        "instanceType": "persistent",
        "start": False,
        "width": profile["width"],
        "height": profile["height"],
        "locale": profile["locale"],
        "timezone": profile["timezone"],
    }


class _ScenarioCatalog:
    def __init__(self, image_ids: list[str]) -> None:
        self.image_ids = iter(image_ids)

    async def inspect(self, _reference: str) -> Any:
        return type(
            "Metadata",
            (),
            {
                "image_id": next(self.image_ids),
                "source_digest": "sha256:" + "f" * 64,
                "architecture": "arm64",
                "os": "linux",
                "android_version": "13",
                "google_components": "unknown",
            },
        )()


async def _wait_management(devices: AndroidDeviceService) -> None:
    if devices.management.task is not None:
        await devices.management.task


class _ScenarioRuntime:
    workspace_id = "workspace"

    def __init__(self) -> None:
        self.restart_images: list[str] = []
        self.locked = 0

    async def environment(self) -> dict[str, Any]:
        return {
            "available": True,
            "platformSupported": True,
            "runtimeId": "test-redroid",
            "images": [{"id": IMAGE_A, "name": "基础镜像", "reference": "redroid/redroid:13"}],
        }

    def lock(self) -> None:
        self.locked += 1

    def unlock(self) -> None:
        self.locked -= 1

    def new_device(self, config: dict[str, Any]) -> dict[str, Any]:
        return {
            **config,
            "runtimeId": "test-redroid",
            "workspaceId": self.workspace_id,
            "volumeId": f"{config['deviceId']}-data",
            "containerId": f"{config['deviceId']}-container",
            "androidStatus": "unknown",
            "ownerRunId": None,
            "control": "idle",
            "generation": 0,
        }

    async def manage(self, device: dict[str, Any], request: dict[str, Any], stage, save) -> None:
        if request["action"] == "restart":
            self.restart_images.append(device["imageId"])
        device["androidStatus"] = "stopped"
        save()

    async def inspect(self, device: dict[str, Any]) -> dict[str, Any]:
        return {"androidStatus": "stopped", "dockerStatus": "stopped", "imageId": device["imageId"]}


@pytest.mark.asyncio
@pytest.mark.parametrize('state', ['unregistered', 'deleted', 'delete_pending', 'delete_blocked', 'delete_needs_verification'])
@pytest.mark.parametrize('check', ['image_metadata', 'unsupported'])
async def test_metadata_verification_preserves_image_lifecycle(tmp_path, state, check):
    sessions = _database(tmp_path)
    resources = AndroidResourceRepository(sessions)
    image = {'id': 'image', 'imageId': IMAGE_A, 'reference': 'local:fixture', 'state': state,
             'revision': 2, 'deleteRequestId': 'delete-original', 'workspaceId': 'workspace'}
    resources.save('image', image)
    service = AndroidImageService(resources, AndroidDeviceService(SqlAlchemyDeviceRepository(sessions), _ScenarioRuntime()), _ScenarioCatalog([IMAGE_A]))
    try:
        await service.verify_server('image', {'check': check})
    except AndroidError as error:
        assert error.code == 'ANDROID_IMAGE_STATE_CONFLICT'
    assert resources.get('image', 'image') == image
    sessions.dispose()


@pytest.mark.asyncio
async def test_metadata_probe_serializes_with_delete_and_keeps_delete_receipt(tmp_path):
    import asyncio

    sessions = _database(tmp_path)
    resources = AndroidResourceRepository(sessions)
    started, release = asyncio.Event(), asyncio.Event()

    class Runtime(_ScenarioRuntime):
        def lock(self):
            if self.locked:
                raise AndroidError('ANDROID_RUNTIME_BUSY', 'busy', 409)
            self.locked = 1

    class Catalog(_ScenarioCatalog):
        async def inspect(self, reference):
            started.set()
            await release.wait()
            return await super().inspect(reference)

    runtime = Runtime()
    service = AndroidImageService(resources, AndroidDeviceService(SqlAlchemyDeviceRepository(sessions), runtime), Catalog([IMAGE_A]))
    resources.save('image', {'id': 'image', 'imageId': IMAGE_A, 'reference': 'local:fixture', 'state': 'registered', 'revision': 1})
    task = asyncio.create_task(service.verify_server('image', {'check': 'image_metadata'}))
    await started.wait()
    blocked = False
    try:
        service.delete('image', request_id='delete-original', expected_revision=1)
    except AndroidError as error:
        assert error.code == 'ANDROID_RUNTIME_BUSY'
        blocked = True
    release.set()
    await task
    if blocked:
        service.delete('image', request_id='delete-original', expected_revision=1)
    persisted = resources.get('image', 'image')
    assert persisted['state'] == 'unregistered'
    assert persisted['revision'] == 2
    assert persisted['deleteRequestId'] == 'delete-original'
    assert runtime.locked == 0
    sessions.dispose()
