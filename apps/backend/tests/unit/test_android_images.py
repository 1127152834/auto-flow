import asyncio

import pytest

from autoflow.application.android.devices import AndroidDeviceService
from autoflow.application.android.images import AndroidImageService
from autoflow.domain.android.ports import AndroidError


def test_register_image_keeps_exact_reference_and_delete_checks_device_refs():
    resources = _Resources()
    devices = _Devices()
    service = AndroidImageService(resources, devices)
    image = service.register({"id": "sha256:" + "a" * 64, "name": "候选镜像", "reference": "redroid/redroid:13"})
    assert image["imageId"] == "sha256:" + "a" * 64
    devices.items = [{"imageId": image["imageId"], "deleted": False}]
    with pytest.raises(AndroidError) as error:
        service.delete(image["id"])
    assert error.value.status == 409


class _Resources:
    def __init__(self): self.items = {}
    def get(self, kind, identifier):
        if (kind, identifier) not in self.items: raise AndroidError("NOT_FOUND", "not found", 404)
        return self.items[(kind, identifier)]
    def list(self, kind): return [value for (stored_kind, _), value in self.items.items() if stored_kind == kind]
    def save(self, kind, value): self.items[(kind, value["id"])] = value


class _Devices:
    def __init__(self): self.items = []
    def list(self): return self.items


class _ImageRuntime:
    def __init__(self): self.deleted = []
    async def delete_image(self, image_id): self.deleted.append(image_id)


def test_image_registration_is_idempotent_and_content_delete_requires_real_io():
    service = AndroidImageService(_Resources(), _Devices())
    request = {"id": "sha256:" + "b" * 64, "name": "image", "reference": "redroid/redroid:13"}
    first = service.register(request)
    assert service.register(request)["id"] == first["id"]
    with pytest.raises(AndroidError):
        service.delete(first["id"], delete_content=True)
    assert service.list()[0]["state"] == "registered"


@pytest.mark.asyncio
async def test_content_delete_removes_unreferenced_image_through_runtime():
    devices = _Devices()
    devices.runtime = _ImageRuntime()
    service = AndroidImageService(_Resources(), devices)
    image = service.register({"id": "sha256:" + "1" * 64, "name": "image", "reference": "redroid/redroid:13"})
    result = await service.delete_content(image["id"])
    assert result["state"] == "deleted"
    assert devices.runtime.deleted == [image["imageId"]]


@pytest.mark.asyncio
async def test_content_delete_accepts_the_production_android_device_service_facade():
    runtime = _ImageRuntime()
    service = AndroidDeviceService(_DeviceRepository(), runtime)
    images = AndroidImageService(_Resources(), service)
    image = images.register({"id": "sha256:" + "2" * 64, "name": "image", "reference": "redroid/redroid:13"})

    result = await images.delete_content(image["id"])

    assert result["state"] == "deleted"
    assert runtime.deleted == [image["imageId"]]


@pytest.mark.asyncio
async def test_content_delete_cancellation_records_blocked_state_instead_of_pending():
    class _CancelledRuntime:
        async def delete_image(self, image_id):
            raise asyncio.CancelledError()

    devices = _Devices()
    devices.runtime = _CancelledRuntime()
    service = AndroidImageService(_Resources(), devices)
    image = service.register({"id": "sha256:" + "3" * 64, "name": "image", "reference": "redroid/redroid:13"})

    with pytest.raises(asyncio.CancelledError):
        await service.delete_content(image["id"], request_id="delete-cancel", expected_revision=1)

    assert service.resources.get("image", image["id"])["state"] == "delete_blocked"


def test_image_reference_rejects_newline_or_command_option():
    service = AndroidImageService(_Resources(), _Devices())
    with pytest.raises(AndroidError) as error:
        service.register({"id": "sha256:" + "d" * 64, "name": "image", "reference": "repo:tag\n--privileged"})
    assert error.value.code == "ANDROID_IMAGE_REFERENCE_INVALID"


def test_delete_ignores_foreign_workspace_device_references():
    devices = _Devices()
    devices.runtime = type("Runtime", (), {"workspace_id": "workspace-current"})()
    service = AndroidImageService(_Resources(), devices)
    image = service.register({"id": "sha256:" + "f" * 64, "name": "image", "reference": "redroid/redroid:13"})
    devices.items = [{"deviceId": "foreign-device", "workspaceId": "workspace-other", "deleted": False, "imageId": image["imageId"]}]

    result = service.delete(image["id"], request_id="delete-foreign", expected_revision=1)

    assert result["state"] == "unregistered"


def test_verification_record_is_appended_and_server_owns_aggregate_state():
    service = AndroidImageService(_Resources(), _Devices())
    image = service.register({"id": "sha256:" + "c" * 64, "name": "image", "reference": "redroid/redroid:13"})
    result = service.verify(image["id"], {"check": "boot", "result": "blocked", "evidence": {"message": "设备不可用"}})
    assert result["verification"]["state"] == "blocked"
    assert result["verification"]["records"][0]["check"] == "boot"


@pytest.mark.asyncio
async def test_pull_registers_catalog_metadata_without_shell_arguments():
    service = AndroidImageService(_Resources(), _Devices(), _Catalog())
    image = await service.pull("request-1", "redroid/redroid:13")
    assert image["imageId"] == "sha256:" + "e" * 64
    assert image["architecture"] == "arm64"


class _Catalog:
    async def inspect(self, reference):
        assert reference == "redroid/redroid:13"
        return type("Metadata", (), {"image_id": "sha256:" + "e" * 64, "source_digest": "sha256:" + "f" * 64, "architecture": "arm64", "os": "linux", "android_version": "13", "reference": reference, "google_components": "absent"})()


class _DeviceRepository:
    def list(self):
        return []
