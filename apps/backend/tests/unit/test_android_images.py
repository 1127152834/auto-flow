import asyncio
from types import SimpleNamespace

import pytest

from autoflow.application.android.devices import AndroidDeviceService
from autoflow.application.android.images import AndroidImageService
from autoflow.domain.android.ports import AndroidError


@pytest.mark.asyncio
async def test_register_inspects_server_metadata_before_persisting() -> None:
    catalog = _RegisterCatalog()
    resources = _Resources()
    service = AndroidImageService(resources, _Devices(), catalog)

    result = await service.register(
        {
            "id": "sha256:" + "c" * 64,
            "name": "候选镜像",
            "reference": "redroid/redroid:13",
            "sourceDigest": "sha256:" + "b" * 64,
            "architecture": "amd64",
            "extra": "must not persist",
        }
    )

    assert catalog.references == ["redroid/redroid:13"]
    assert result["imageId"] == "sha256:" + "c" * 64
    assert result["sourceDigest"] == "sha256:" + "d" * 64
    assert result["architecture"] == "arm64"
    assert "extra" not in result
    assert "extra" not in resources.get("image", result["id"])


@pytest.mark.asyncio
async def test_register_rejects_client_digest_when_server_inspection_disagrees() -> None:
    service = AndroidImageService(
        _Resources(),
        _Devices(),
        _RegisterCatalog(),
    )

    with pytest.raises(AndroidError) as error:
        await service.register(
            {
                "id": "sha256:" + "a" * 64,
                "name": "候选镜像",
                "reference": "redroid/redroid:13",
            }
        )

    assert error.value.code == "ANDROID_IMAGE_METADATA_MISMATCH"


@pytest.mark.asyncio
async def test_register_replay_refreshes_stored_metadata_from_server() -> None:
    image_id = "sha256:" + "e" * 64
    resources = _Resources()
    resources.save(
        "image",
        {
            "id": "stored-image",
            "imageId": image_id,
            "name": "候选镜像",
            "reference": "redroid/redroid:13",
            "revision": 1,
            "state": "registered",
            "verification": {"state": "unknown", "evidence": None},
            "sourceDigest": "client-value",
            "architecture": "amd64",
            "os": "windows",
            "androidVersion": "unknown",
            "googleComponents": "unknown",
            "references": [],
        },
    )
    service = AndroidImageService(resources, _Devices(), _CatalogFor(image_id))

    result = await service.register(
        {"id": image_id, "name": "候选镜像", "reference": "redroid/redroid:13"}
    )

    assert result["sourceDigest"] == "sha256:" + "f" * 64
    assert result["architecture"] == "arm64"
    assert resources.get("image", "stored-image")["architecture"] == "arm64"


class _RegisterCatalog:
    def __init__(self) -> None:
        self.references: list[str] = []

    async def inspect(self, reference: str) -> SimpleNamespace:
        self.references.append(reference)
        return SimpleNamespace(
            image_id="sha256:" + "c" * 64,
            source_digest="sha256:" + "d" * 64,
            architecture="arm64",
            os="linux",
            android_version="13",
            google_components="absent",
        )


@pytest.mark.asyncio
async def test_register_image_keeps_exact_reference_and_delete_checks_device_refs():
    resources = _Resources()
    devices = _Devices()
    image_id = "sha256:" + "a" * 64
    service = AndroidImageService(resources, devices, _CatalogFor(image_id))
    image = await service.register({"id": image_id, "name": "候选镜像", "reference": "redroid/redroid:13"})
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


@pytest.mark.asyncio
async def test_image_pull_holds_runtime_lock_through_catalog_publication():
    image_id = "sha256:" + "a" * 64
    runtime = _ImageRuntime()
    runtime.locked = False

    def lock():
        if runtime.locked:
            raise AndroidError("ANDROID_RUNTIME_BUSY", "busy", 409)
        runtime.locked = True

    def unlock():
        runtime.locked = False

    runtime.lock, runtime.unlock = lock, unlock
    devices = _Devices()
    devices.runtime = runtime
    resources = _Resources()

    class Catalog(_CatalogFor):
        async def pull(self, reference, *, allow_unknown_disk_estimate=False):
            assert runtime.locked, "content deletion could race a completed pull"
            return await self.inspect(reference)

    service = AndroidImageService(resources, devices, Catalog(image_id))
    result = await service.pull("pull-locked", "redroid/redroid:13")
    assert result["imageId"] == image_id
    assert not runtime.locked


@pytest.mark.asyncio
async def test_image_registration_is_idempotent_and_content_delete_requires_real_io():
    request = {"id": "sha256:" + "b" * 64, "name": "image", "reference": "redroid/redroid:13"}
    service = AndroidImageService(_Resources(), _Devices(), _CatalogFor(request["id"]))
    first = await service.register(request)
    assert (await service.register(request))["id"] == first["id"]
    with pytest.raises(AndroidError):
        service.delete(first["id"], delete_content=True)
    assert service.list()[0]["state"] == "registered"


@pytest.mark.asyncio
async def test_content_delete_removes_unreferenced_image_through_runtime():
    devices = _Devices()
    devices.runtime = _ImageRuntime()
    image_id = "sha256:" + "1" * 64
    service = AndroidImageService(_Resources(), devices, _CatalogFor(image_id))
    image = await service.register({"id": image_id, "name": "image", "reference": "redroid/redroid:13"})
    result = await service.delete_content(image["id"])
    assert result["state"] == "deleted"
    assert devices.runtime.deleted == [image["imageId"]]


@pytest.mark.asyncio
async def test_content_delete_accepts_the_production_android_device_service_facade():
    runtime = _ImageRuntime()
    service = AndroidDeviceService(_DeviceRepository(), runtime)
    image_id = "sha256:" + "2" * 64
    images = AndroidImageService(_Resources(), service, _CatalogFor(image_id))
    image = await images.register({"id": image_id, "name": "image", "reference": "redroid/redroid:13"})

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
    image_id = "sha256:" + "3" * 64
    service = AndroidImageService(_Resources(), devices, _CatalogFor(image_id))
    image = await service.register({"id": image_id, "name": "image", "reference": "redroid/redroid:13"})

    with pytest.raises(asyncio.CancelledError):
        await service.delete_content(image["id"], request_id="delete-cancel", expected_revision=1)

    assert service.resources.get("image", image["id"])["state"] == "delete_blocked"


@pytest.mark.asyncio
async def test_server_verification_does_not_trust_client_passed_result():
    class _CatalogMismatch:
        async def inspect(self, _reference):
            return SimpleNamespace(
                image_id="sha256:" + "9" * 64,
                source_digest="sha256:" + "8" * 64,
                architecture="arm64",
                os="linux",
                android_version="13",
                google_components="unknown",
            )

    image_id = "sha256:" + "4" * 64
    service = AndroidImageService(_Resources(), _Devices(), _CatalogFor(image_id))
    image = await service.register({"id": image_id, "name": "image", "reference": "redroid/redroid:13"})
    service.catalog = _CatalogMismatch()

    result = await service.verify_server(image["id"], {"check": "image_metadata", "result": "passed", "evidence": {"message": "client said passed"}})

    assert result["verification"]["state"] == "failed"
    record = result["verification"]["records"][-1]
    assert record["result"] == "failed"
    assert record["source"] == "server"
    assert record["evidence"]["imageId"] == "sha256:" + "9" * 64


@pytest.mark.asyncio
async def test_server_verification_does_not_pass_without_trusted_source_digest():
    class _CatalogWithoutSourceDigest:
        async def inspect(self, _reference):
            return SimpleNamespace(
                image_id="sha256:" + "6" * 64,
                source_digest=None,
                architecture="arm64",
                os="linux",
                android_version="13",
                google_components="unknown",
            )

    image_id = "sha256:" + "6" * 64
    service = AndroidImageService(_Resources(), _Devices(), _CatalogWithoutSourceDigest())
    image = await service.register({"id": image_id, "name": "image", "reference": "redroid/redroid:13"})

    result = await service.verify_server(image["id"], {"check": "image_metadata", "result": "passed", "evidence": {}})

    assert result["verification"]["state"] == "blocked"
    assert result["verification"]["records"][-1]["evidence"]["code"] == "ANDROID_IMAGE_SOURCE_UNKNOWN"


@pytest.mark.asyncio
async def test_metadata_pass_does_not_claim_google_validation_passed():
    image_id = "sha256:" + "7" * 64
    service = AndroidImageService(_Resources(), _Devices(), _CatalogFor(image_id))
    image = await service.register({"id": image_id, "name": "candidate", "reference": "redroid/redroid:13"})

    result = await service.verify_server(image["id"], {"check": "image_metadata"})

    assert result["verification"]["state"] == "passed"
    assert result["validation"] == "not_tested"
    assert result["googleComponents"] == "unknown"

    blocked = await service.verify_server(image["id"], {"check": "login"})
    assert blocked["verification"]["state"] == "passed"
    assert blocked["validation"] == "blocked"
    assert blocked["verification"]["records"][-1]["evidence"]["code"] == "ANDROID_IMAGE_CHECK_UNSUPPORTED"


@pytest.mark.asyncio
async def test_unknown_content_delete_can_converge_via_server_verification():
    class _Runtime:
        async def delete_image(self, _image_id):
            raise TimeoutError("lost response")

        async def inspect_image(self, _image_id):
            raise AndroidError("ANDROID_IMAGE_NOT_FOUND", "镜像不存在", 404)

    devices = _Devices()
    devices.runtime = _Runtime()
    image_id = "sha256:" + "5" * 64
    service = AndroidImageService(_Resources(), devices, _CatalogFor(image_id))
    image = await service.register({"id": image_id, "name": "image", "reference": "redroid/redroid:13"})

    with pytest.raises(AndroidError) as error:
        await service.delete_content(image["id"], request_id="delete-unknown", expected_revision=1)
    assert error.value.code == "ANDROID_IMAGE_DELETE_RESULT_UNKNOWN"

    result = await service.verify_delete_content(image["id"], "delete-unknown")

    assert result["state"] == "deleted"
    assert service.resources.get("image", image["id"])["state"] == "deleted"


@pytest.mark.asyncio
async def test_delete_verification_checks_exact_digest_before_falling_back_to_catalog_tag():
    class _Runtime:
        async def delete_image(self, _image_id):
            raise TimeoutError("lost response")

    class _Catalog:
        async def inspect(self, _reference):
            return SimpleNamespace(image_id="sha256:" + "8" * 64)

    devices = _Devices()
    devices.runtime = _Runtime()
    image_id = "sha256:" + "7" * 64
    service = AndroidImageService(_Resources(), devices, _CatalogFor(image_id))
    image = await service.register({"id": image_id, "name": "image", "reference": "redroid/redroid:13"})
    service.catalog = _Catalog()

    with pytest.raises(AndroidError):
        await service.delete_content(image["id"], request_id="delete-tag", expected_revision=1)

    result = await service.verify_delete_content(image["id"], "delete-tag")

    assert result["state"] == "deleted"


@pytest.mark.asyncio
async def test_image_reference_rejects_newline_or_command_option():
    service = AndroidImageService(_Resources(), _Devices())
    with pytest.raises(AndroidError) as error:
        await service.register({"id": "sha256:" + "d" * 64, "name": "image", "reference": "repo:tag\n--privileged"})
    assert error.value.code == "ANDROID_IMAGE_REFERENCE_INVALID"


@pytest.mark.asyncio
async def test_delete_ignores_foreign_workspace_device_references():
    devices = _Devices()
    devices.runtime = type("Runtime", (), {"workspace_id": "workspace-current"})()
    image_id = "sha256:" + "f" * 64
    service = AndroidImageService(_Resources(), devices, _CatalogFor(image_id))
    image = await service.register({"id": image_id, "name": "image", "reference": "redroid/redroid:13"})
    devices.items = [{"deviceId": "foreign-device", "workspaceId": "workspace-other", "deleted": False, "imageId": image["imageId"]}]

    result = service.delete(image["id"], request_id="delete-foreign", expected_revision=1)

    assert result["state"] == "unregistered"


@pytest.mark.asyncio
async def test_content_delete_keeps_image_referenced_by_current_workspace_backup(tmp_path):
    devices = _Devices()
    devices.runtime = _ImageRuntime()
    devices.runtime.workspace_id = "runtime-workspace-hash"
    devices.runtime.workspace = tmp_path
    image_id = "sha256:" + "a" * 64
    resources = _Resources()
    service = AndroidImageService(resources, devices, _CatalogFor(image_id))
    image = await service.register({"id": image_id, "name": "image", "reference": "redroid/redroid:13"})
    resources.save("backup", {"id": "backup-1", "imageId": image_id, "workspaceId": str(tmp_path.resolve()), "state": "available"})

    with pytest.raises(AndroidError) as error:
        await service.delete_content(image["id"])

    assert error.value.code == "ANDROID_IMAGE_REFERENCED"
    assert devices.runtime.deleted == []


@pytest.mark.asyncio
async def test_content_delete_ignores_foreign_workspace_backup(tmp_path):
    devices = _Devices()
    devices.runtime = _ImageRuntime()
    devices.runtime.workspace_id = "runtime-workspace-hash"
    devices.runtime.workspace = tmp_path
    image_id = "sha256:" + "b" * 64
    resources = _Resources()
    service = AndroidImageService(resources, devices, _CatalogFor(image_id))
    image = await service.register({"id": image_id, "name": "image", "reference": "redroid/redroid:13"})
    resources.save("backup", {"id": "foreign", "imageId": image_id, "workspaceId": str(tmp_path / "other"), "state": "available"})

    result = await service.delete_content(image["id"])

    assert result["state"] == "deleted"
    assert devices.runtime.deleted == [image_id]


@pytest.mark.asyncio
async def test_verification_record_is_appended_and_server_owns_aggregate_state():
    image_id = "sha256:" + "c" * 64
    service = AndroidImageService(_Resources(), _Devices(), _CatalogFor(image_id))
    image = await service.register({"id": image_id, "name": "image", "reference": "redroid/redroid:13"})
    result = service.verify(image["id"], {"check": "boot", "result": "blocked", "evidence": {"message": "设备不可用"}})
    assert result["verification"]["state"] == "blocked"
    assert result["verification"]["records"][0]["check"] == "boot"


@pytest.mark.asyncio
async def test_pull_registers_catalog_metadata_without_shell_arguments():
    service = AndroidImageService(_Resources(), _Devices(), _Catalog())
    image = await service.pull("request-1", "redroid/redroid:13")
    assert image["imageId"] == "sha256:" + "e" * 64
    assert image["architecture"] == "arm64"


@pytest.mark.asyncio
async def test_second_pull_of_registered_digest_has_its_own_durable_receipt():
    resources = _Resources()
    catalog = _Catalog()
    service = AndroidImageService(resources, _Devices(), catalog)
    first = await service.pull("pull-1", "redroid/redroid:13")

    second = await service.pull("pull-2", "redroid/redroid:13")

    assert second["imageId"] == first["imageId"]
    assert len(resources.list("image_pull_receipt")) == 2
    assert await service.verify_pull("pull-2", "redroid/redroid:13")


@pytest.mark.asyncio
async def test_pull_verification_keeps_runtime_lock_until_operation_is_committed():
    image_id = "sha256:" + "a" * 64
    runtime = _ImageRuntime()
    runtime.locked = False
    runtime.lock = lambda: setattr(runtime, "locked", True)
    runtime.unlock = lambda: setattr(runtime, "locked", False)
    devices = _Devices()
    devices.runtime = runtime

    class Catalog(_CatalogFor):
        async def inspect(self, reference):
            assert runtime.locked
            return await super().inspect(reference)

    service = AndroidImageService(_Resources(), devices, Catalog(image_id))
    await service.pull("pending-pull", "redroid/redroid:13")
    completed = []

    def complete():
        assert runtime.locked, "image deletion could race the operation transition"
        completed.append(True)
        return True

    assert await service.verify_pull("pending-pull", "redroid/redroid:13", on_verified=complete)
    assert completed == [True]
    assert not runtime.locked


@pytest.mark.asyncio
async def test_first_pull_crash_between_catalog_and_receipt_does_not_publish_half_record():
    class InterruptedResources(_Resources):
        def save(self, kind, value):
            if kind == "image_pull_receipt":
                raise RuntimeError("interrupted before receipt")
            super().save(kind, value)

        def save_many(self, _rows):
            raise RuntimeError("interrupted before transaction commit")

    resources = InterruptedResources()
    service = AndroidImageService(resources, _Devices(), _Catalog())

    with pytest.raises(RuntimeError):
        await service.pull("pull-interrupted", "redroid/redroid:13")

    assert resources.list("image") == []
    assert resources.list("image_pull_receipt") == []


@pytest.mark.asyncio
async def test_verify_legacy_first_pull_backfills_missing_receipt_after_runtime_check():
    resources = _Resources()
    service = AndroidImageService(resources, _Devices(), _Catalog())
    image = await service.pull("pull-legacy", "redroid/redroid:13")
    resources.items = {key: value for key, value in resources.items.items() if key[0] != "image_pull_receipt"}

    assert await service.verify_pull("pull-legacy", "redroid/redroid:13")
    assert resources.list("image_pull_receipt")[0]["imageId"] == image["imageId"]


@pytest.mark.asyncio
async def test_repull_of_deleted_digest_restores_current_catalog_state():
    devices = _Devices()
    devices.runtime = _ImageRuntime()
    image_id = "sha256:" + "e" * 64
    service = AndroidImageService(_Resources(), devices, _CatalogFor(image_id))
    first = await service.pull("pull-before-delete", "redroid/redroid:13")
    await service.delete_content(first["id"])

    second = await service.pull("pull-after-delete", "redroid/redroid:13")

    assert second["state"] == "registered"
    assert second["revision"] > first["revision"]
    assert await service.verify_pull("pull-after-delete", "redroid/redroid:13")


class _Catalog:
    async def inspect(self, reference):
        assert reference == "redroid/redroid:13"
        return type("Metadata", (), {"image_id": "sha256:" + "e" * 64, "source_digest": "sha256:" + "f" * 64, "architecture": "arm64", "os": "linux", "android_version": "13", "reference": reference, "google_components": "absent"})()


class _CatalogFor:
    def __init__(self, image_id: str):
        self.image_id = image_id

    async def inspect(self, reference):
        return SimpleNamespace(
            image_id=self.image_id,
            source_digest="sha256:" + "f" * 64,
            architecture="arm64",
            os="linux",
            android_version="13",
            reference=reference,
            google_components="unknown",
        )


class _DeviceRepository:
    def list(self):
        return []
