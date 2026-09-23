import hashlib
import io
import tarfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

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
    record = {"id": "backup", "state": "available", "imageId": image, "workspaceId": str(tmp_path.resolve()), "path": str(tmp_path / "missing")}
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "device",
    [
        {"deviceId": "new", "imageId": "sha256:" + "a" * 64, "androidStatus": "ready"},
        {"deviceId": "new", "imageId": "sha256:" + "a" * 64, "androidStatus": "retained"},
        {"deviceId": "new", "imageId": "sha256:" + "a" * 64, "androidStatus": "stopped", "control": "manual"},
        {"deviceId": "new", "imageId": "sha256:" + "a" * 64, "androidStatus": "stopped", "control": "idle", "ownerRunId": "run-1"},
    ],
)
async def test_restore_requires_stopped_unowned_target_before_runtime_write(tmp_path: Path, device):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        info = tarfile.TarInfo("data/settings.json")
        info.size = 2
        archive.addfile(info, io.BytesIO(b"{}"))
    resources = _Resources()
    service = AndroidBackupService(resources, tmp_path)
    image = device["imageId"]
    record = await service.create_with_runtime(
        {"deviceId": "source", "imageId": image, "control": "idle", "ownerRunId": None},
        {"androidStatus": "stopped"},
        _Runtime(payload.getvalue()),
    )
    runtime = type("Runtime", (), {"restore_volume": AsyncMock()})()

    with pytest.raises(AndroidError, match="停止") as caught:
        await service.restore_data(record["id"], device, runtime)

    assert caught.value.code == "ANDROID_BACKUP_REQUIRES_STOPPED"
    runtime.restore_volume.assert_not_awaited()


@pytest.mark.asyncio
async def test_restore_rejects_unsupported_archive_attributes_before_runtime_write(tmp_path: Path):
    valid_payload = io.BytesIO()
    with tarfile.open(fileobj=valid_payload, mode="w") as archive:
        info = tarfile.TarInfo("data/settings.json")
        info.size = 2
        archive.addfile(info, io.BytesIO(b"{}"))
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w", format=tarfile.PAX_FORMAT) as archive:
        info = tarfile.TarInfo("data/settings.json")
        info.size = 2
        info.pax_headers["LIBARCHIVE.xattr.security.selinux"] = "untrusted_u:object_r:app_data_file:s0"
        archive.addfile(info, io.BytesIO(b"{}"))
    resources = _Resources()
    service = AndroidBackupService(resources, tmp_path)
    image = "sha256:" + "a" * 64
    record = await service.create_with_runtime(
        {"deviceId": "source", "imageId": image, "control": "idle", "ownerRunId": None},
        {"androidStatus": "stopped"},
        _Runtime(valid_payload.getvalue()),
    )
    data_path = Path(record["path"]) / "data.tar"
    data_path.write_bytes(payload.getvalue())
    digest = hashlib.sha256()
    size = 0
    for path in sorted(Path(record["path"]).iterdir()):
        content = path.read_bytes()
        digest.update(content)
        size += len(content)
    record.update(sha256=digest.hexdigest(), bytes=size)
    resources.save("backup", record)
    runtime = type("Runtime", (), {"restore_volume": AsyncMock()})()

    with pytest.raises(AndroidError, match="属性"):
        await service.restore_data(
            record["id"],
            {"deviceId": "new", "imageId": image, "androidStatus": "stopped", "control": "idle"},
            runtime,
        )

    runtime.restore_volume.assert_not_awaited()


@pytest.mark.asyncio
async def test_restore_writes_the_exact_bytes_that_passed_digest_validation(tmp_path, monkeypatch):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        archive.addfile(tarfile.TarInfo("data/file"))
    resources = _Resources()
    service = AndroidBackupService(resources, tmp_path)
    record = await service.create_with_runtime(
        {"deviceId": "source", "imageId": "image", "control": "idle"},
        {"androidStatus": "stopped"}, _Runtime(payload.getvalue()),
    )
    original_read = Path.read_bytes
    reads = 0

    def changing_read(path):
        nonlocal reads
        if path.name == "data.tar":
            reads += 1
            if reads > 1:
                return b"changed after validation"
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", changing_read)
    runtime = type("Runtime", (), {"restore_volume": AsyncMock()})()
    operations = Mock()
    service.operations = operations
    await service.restore_data(record["id"], {"deviceId": "new", "imageId": "image", "generation": 1, "restoreState": "pending", "restoreRequestId": "request", "restoreBackupId": record["id"], "creationConfig": {"restoreRequestId": "request", "restoreBackupId": record["id"], "start": False}}, runtime)
    assert runtime.restore_volume.await_args.args[1] == payload.getvalue()
    assert reads == 1
    operations.verify_restore_target.assert_called_once()


@pytest.mark.asyncio
async def test_backup_rechecks_live_state_even_when_caller_supplies_stopped_snapshot(tmp_path):
    service = AndroidBackupService(_Resources(), tmp_path)
    runtime = type("Runtime", (), {"inspect": AsyncMock(return_value={"androidStatus": "ready"}), "backup_volume": AsyncMock()})()
    with pytest.raises(AndroidError, match="停止"):
        await service.create_with_runtime(
            {"deviceId": "source", "imageId": "image", "control": "idle"},
            {"androidStatus": "stopped"}, runtime,
        )
    runtime.inspect.assert_awaited_once()
    runtime.backup_volume.assert_not_awaited()


@pytest.mark.asyncio
async def test_restore_cannot_overwrite_its_source_device(tmp_path):
    resources = _Resources()
    resources.save("backup", {"id": "backup", "deviceId": "source", "imageId": "image", "workspaceId": str(tmp_path.resolve()), "state": "available"})
    service = AndroidBackupService(resources, tmp_path)
    runtime = type("Runtime", (), {"restore_volume": AsyncMock()})()
    with pytest.raises(AndroidError) as error:
        await service.restore_data("backup", {"deviceId": "source", "imageId": "image"}, runtime)
    assert error.value.code == "ANDROID_RESTORE_TARGET_INVALID"
    runtime.restore_volume.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("formatVersion", 2),
    ("formatVersion", True),
    ("deviceId", "different-source"),
    ("imageId", "sha256:" + "b" * 64),
    ("config", {"name": "forged"}),
])
async def test_restore_rejects_rehashed_manifest_that_disagrees_with_catalog(tmp_path: Path, field, value):
    import json

    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        info = tarfile.TarInfo("data/settings.json")
        info.size = 2
        archive.addfile(info, io.BytesIO(b"{}"))
    resources = _Resources()
    service = AndroidBackupService(resources, tmp_path)
    image = "sha256:" + "a" * 64
    record = await service.create_with_runtime(
        {"deviceId": "source", "imageId": image, "creationConfig": {"name": "original"}, "control": "idle", "ownerRunId": None},
        {"androidStatus": "stopped"}, _Runtime(payload.getvalue()),
    )
    directory = Path(record["path"])
    manifest = json.loads((directory / "manifest.json").read_bytes())
    manifest[field] = value
    (directory / "manifest.json").write_text(json.dumps(manifest))
    files = sorted(directory.iterdir())
    record.update(sha256=hashlib.sha256(b"".join(path.read_bytes() for path in files)).hexdigest(), bytes=sum(path.stat().st_size for path in files))
    resources.save("backup", record)
    runtime = type("Runtime", (), {"restore_volume": AsyncMock()})()

    with pytest.raises(AndroidError) as error:
        await service.restore_data(record["id"], {"deviceId": "new", "imageId": image, "androidStatus": "stopped", "control": "idle"}, runtime)
    assert error.value.code == "ANDROID_BACKUP_INCOMPATIBLE"
    runtime.restore_volume.assert_not_awaited()


@pytest.mark.asyncio
async def test_restore_rejects_backup_owned_by_another_workspace(tmp_path: Path):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        info = tarfile.TarInfo("data/settings.json")
        info.size = 2
        archive.addfile(info, io.BytesIO(b"{}"))
    resources = _Resources()
    service = AndroidBackupService(resources, tmp_path)
    record = await service.create_with_runtime(
        {"deviceId": "source", "imageId": "image", "control": "idle", "ownerRunId": None},
        {"androidStatus": "stopped"}, _Runtime(payload.getvalue()),
    )
    record["workspaceId"] = str(tmp_path / "another-workspace")
    resources.save("backup", record)
    runtime = type("Runtime", (), {"restore_volume": AsyncMock()})()
    with pytest.raises(AndroidError) as error:
        await service.restore_data(record["id"], {"deviceId": "new", "imageId": "image", "androidStatus": "stopped", "control": "idle"}, runtime)
    assert error.value.code == "ANDROID_BACKUP_NOT_FOUND"
    runtime.restore_volume.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("target", [
    {"deviceId": "new", "imageId": "image", "androidStatus": "stopped", "control": "idle"},
    {"deviceId": "new", "imageId": "image", "androidStatus": "stopped", "control": "idle", "generation": 1, "restoreState": "pending", "restoreRequestId": "request", "restoreBackupId": "other", "creationConfig": {"start": False}},
])
async def test_direct_restore_rejects_existing_or_wrong_backup_target(tmp_path: Path, target):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        info = tarfile.TarInfo("data/settings.json")
        info.size = 2
        archive.addfile(info, io.BytesIO(b"{}"))
    service = AndroidBackupService(_Resources(), tmp_path)
    record = await service.create_with_runtime(
        {"deviceId": "source", "imageId": "image", "control": "idle", "ownerRunId": None},
        {"androidStatus": "stopped"}, _Runtime(payload.getvalue()),
    )
    runtime = type("Runtime", (), {"restore_volume": AsyncMock()})()
    with pytest.raises(AndroidError) as error:
        await service.restore_data(record["id"], target, runtime)
    assert error.value.code == "ANDROID_RESTORE_TARGET_INVALID"
    runtime.restore_volume.assert_not_awaited()
