from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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
