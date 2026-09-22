import io
import tarfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from autoflow.application.android.backups import AndroidBackupService
from autoflow.domain.android.ports import AndroidError


def test_backup_requires_stopped_unowned_device_and_uses_workspace_path(tmp_path: Path):
    service = AndroidBackupService(_Resources(), tmp_path)
    with pytest.raises(AndroidError):
        service.create({"deviceId": "d", "name": "x"}, {"androidStatus": "ready", "control": "idle"})


@pytest.mark.asyncio
async def test_runtime_backup_publishes_data_archive_and_manifest(tmp_path: Path):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        info = tarfile.TarInfo("data/settings.json")
        content = b"{}"
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    resources = _Resources()
    service = AndroidBackupService(resources, tmp_path)
    device = {"deviceId": "d", "imageId": "sha256:" + "a" * 64, "control": "idle", "ownerRunId": None, "creationConfig": {"name": "x"}}
    record = await service.create_with_runtime(device, {"androidStatus": "stopped"}, _Runtime(payload.getvalue()))
    assert record["state"] == "available"
    assert (Path(record["path"]) / "data.tar").is_file()
    assert resources.items[("backup", record["id"])]


@pytest.mark.asyncio
async def test_restore_rejects_corrupt_archive_before_runtime_write(tmp_path: Path):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        info = tarfile.TarInfo("data/settings.json")
        content = b"{}"
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    resources = _Resources()
    service = AndroidBackupService(resources, tmp_path)
    image = "sha256:" + "a" * 64
    record = await service.create_with_runtime({"deviceId": "d", "imageId": image, "control": "idle", "ownerRunId": None}, {"androidStatus": "stopped"}, _Runtime(payload.getvalue()))
    data_path = Path(record["path"]) / "data.tar"
    data_path.write_bytes(data_path.read_bytes() + b"corrupt")
    runtime = type("Runtime", (), {"restore_volume": AsyncMock()})()
    with pytest.raises(AndroidError, match="摘要"):
        await service.restore_data(record["id"], {"deviceId": "new", "imageId": image}, runtime)
    runtime.restore_volume.assert_not_awaited()


@pytest.mark.asyncio
async def test_restore_rejects_different_image_before_runtime_write(tmp_path: Path):
    resources = _Resources()
    service = AndroidBackupService(resources, tmp_path)
    image = "sha256:" + "a" * 64
    record = {"id": "backup", "state": "available", "imageId": image, "path": str(tmp_path / "missing")}
    resources.items[("backup", record["id"])] = record
    runtime = type("Runtime", (), {"restore_volume": AsyncMock()})()
    with pytest.raises(AndroidError, match="镜像"):
        await service.restore_data(record["id"], {"deviceId": "new", "imageId": "sha256:" + "b" * 64}, runtime)
    runtime.restore_volume.assert_not_awaited()


@pytest.mark.asyncio
async def test_restore_rejects_symlinked_backup_members_before_runtime_write(tmp_path: Path):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        info = tarfile.TarInfo("data/settings.json")
        content = b"{}"
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    resources = _Resources()
    service = AndroidBackupService(resources, tmp_path)
    image = "sha256:" + "a" * 64
    record = await service.create_with_runtime(
        {"deviceId": "d", "imageId": image, "control": "idle", "ownerRunId": None},
        {"androidStatus": "stopped"},
        _Runtime(payload.getvalue()),
    )
    backup_dir = Path(record["path"])
    original_manifest = backup_dir / "manifest.json"
    external_manifest = tmp_path / "external-manifest.json"
    external_manifest.write_bytes(original_manifest.read_bytes())
    original_manifest.unlink()
    original_manifest.symlink_to(external_manifest)
    runtime = type("Runtime", (), {"restore_volume": AsyncMock()})()

    with pytest.raises(AndroidError, match="链接"):
        await service.restore_data(
            record["id"], {"deviceId": "new", "imageId": image}, runtime
        )
    runtime.restore_volume.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_backup_rejects_malformed_archive_with_domain_error(tmp_path: Path):
    service = AndroidBackupService(_Resources(), tmp_path)
    device = {"deviceId": "d", "imageId": "image", "control": "idle", "ownerRunId": None}

    with pytest.raises(AndroidError, match="归档") as caught:
        await service.create_with_runtime(
            device, {"androidStatus": "stopped"}, _Runtime(b"not a tar archive")
        )

    assert caught.value.code == "ANDROID_BACKUP_INCOMPATIBLE"
    assert not list((tmp_path / "android-backups" / "staging").glob("*"))


@pytest.mark.asyncio
async def test_delete_removes_only_published_backup_files(tmp_path: Path):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        info = tarfile.TarInfo("data/settings.json")
        content = b"{}"
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    resources = _Resources()
    service = AndroidBackupService(resources, tmp_path)
    record = await service.create_with_runtime({"deviceId": "d", "imageId": "image", "control": "idle", "ownerRunId": None}, {"androidStatus": "stopped"}, _Runtime(payload.getvalue()))
    service.delete(record["id"])
    assert not Path(record["path"]).exists()
    assert resources.list("backup") == []


def test_delete_rejects_backup_root_path(tmp_path: Path):
    resources = _Resources()
    service = AndroidBackupService(resources, tmp_path)
    service.storage.final.mkdir(parents=True)
    resources.save("backup", {"id": "root", "path": str(service.storage.final), "state": "available"})
    with pytest.raises(AndroidError, match="受控"):
        service.delete("root")


def test_delete_rejects_symlinked_final_root_before_touching_external_data(tmp_path: Path):
    resources = _Resources()
    service = AndroidBackupService(resources, tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    backup_dir = external / "backup"
    backup_dir.mkdir()
    marker = backup_dir / "marker"
    marker.write_text("keep", encoding="utf-8")
    service.storage.final.parent.mkdir(parents=True, exist_ok=True)
    service.storage.final.symlink_to(external, target_is_directory=True)
    resources.save("backup", {"id": "backup", "path": str(backup_dir), "state": "available"})

    with pytest.raises(AndroidError, match="受控"):
        service.delete("backup")
    assert marker.read_text(encoding="utf-8") == "keep"


class _Resources:
    def __init__(self): self.items = {}
    def save(self, kind, item): self.items[(kind, item["id"])] = item
    def list(self, kind): return [item for (stored, _), item in self.items.items() if stored == kind]
    def delete(self, kind, identifier): self.items.pop((kind, identifier), None)


class _Runtime:
    def __init__(self, payload: bytes): self.payload = payload
    async def backup_volume(self, _device): return self.payload
