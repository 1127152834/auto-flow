import hashlib
import json

import pytest

from autoflow.application.android.backups import AndroidBackupService
from autoflow.application.android.cleanup import CleanupService
from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def setup(tmp_path):
    database = tmp_path / "test.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    resources = AndroidResourceRepository(sessions)
    backups = AndroidBackupService(resources, tmp_path)
    return sessions, resources, backups, CleanupService(resources, backups=backups)


def digest(items):
    return hashlib.sha256(json.dumps(items, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@pytest.mark.parametrize("area", ["staging", "final"])
def test_inventory_exposes_unregistered_module_files_and_only_deletes_frozen_selection(tmp_path, area):
    sessions, _resources, backups, cleanup = setup(tmp_path)
    directory = getattr(backups.storage, area) / "orphan"
    directory.mkdir(parents=True)
    (directory / "data.tar").write_bytes(b"temporary")
    sibling = backups.storage.stage("keep")
    (sibling / "data.tar").write_bytes(b"keep")
    inventory = cleanup.inventory(str(tmp_path.resolve()))
    prefix = "staging" if area == "staging" else "orphan"
    identifier = prefix + ":orphan"
    assert identifier in {item["id"] for item in inventory}
    preview = cleanup.preview([identifier], str(tmp_path.resolve()))
    assert preview[0]["size"] == 9
    cleanup.execute(str(tmp_path.resolve()), digest(preview), "delete-orphan")
    assert not directory.exists()
    assert (sibling / "data.tar").read_bytes() == b"keep"
    sessions.dispose()


def test_same_size_staging_replacement_invalidates_frozen_preview_after_restart(tmp_path):
    sessions, resources, backups, cleanup = setup(tmp_path)
    directory = backups.storage.stage("partial")
    path = directory / "data.tar"
    path.write_bytes(b"old-data")
    workspace = str(tmp_path.resolve())
    preview = cleanup.preview(["staging:partial"], workspace)
    path.write_bytes(b"new-data")
    fresh = CleanupService(resources, backups=AndroidBackupService(resources, tmp_path))
    with pytest.raises(AndroidError) as error:
        fresh.execute(workspace, digest(preview), "changed")
    assert error.value.status == 409
    assert path.read_bytes() == b"new-data"
    sessions.dispose()


def test_registered_backup_is_not_reported_as_orphan_and_file_changes_are_fenced(tmp_path):
    sessions, resources, backups, cleanup = setup(tmp_path)
    directory = backups.storage.stage("registered")
    path = directory / "data.tar"
    path.write_bytes(b"original")
    final = backups.storage.finalize("registered")
    resources.save("backup", {"id": "registered", "path": str(final), "workspaceId": str(tmp_path.resolve()), "state": "available", "sha256": "record-digest", "bytes": 8})
    items = cleanup.inventory(str(tmp_path.resolve()))
    assert [item["id"] for item in items] == ["registered"]
    preview = cleanup.preview(["registered"], str(tmp_path.resolve()))
    (final / "data.tar").write_bytes(b"modified")
    with pytest.raises(AndroidError) as error:
        cleanup.execute(str(tmp_path.resolve()), digest(preview), "changed-backup")
    assert error.value.status == 409
    assert final.exists()
    sessions.dispose()


def test_cleanup_cannot_delete_archive_while_backup_or_restore_holds_storage_lock(tmp_path):
    sessions, resources, backups, cleanup = setup(tmp_path)
    directory = backups.storage.stage("active")
    (directory / "data.tar").write_bytes(b"active")
    workspace = str(tmp_path.resolve())
    preview = cleanup.preview(["staging:active"], workspace)
    other_process_storage = AndroidBackupService(resources, tmp_path).storage
    with other_process_storage.lock():
        with pytest.raises(AndroidError) as error:
            cleanup.execute(workspace, digest(preview), "active-cleanup")
        assert error.value.code == "ANDROID_BACKUP_BUSY"
    assert directory.exists()
    sessions.dispose()


def test_foreign_workspace_cannot_discover_or_delete_module_files(tmp_path):
    sessions, _resources, backups, cleanup = setup(tmp_path)
    directory = backups.storage.stage("private")
    (directory / "data.tar").write_bytes(b"private")
    assert cleanup.inventory("foreign-workspace") == []
    assert cleanup.preview(["staging:private"], "foreign-workspace") == []
    assert directory.exists()
    sessions.dispose()


@pytest.mark.parametrize("replacement", ["file-link", "root-link"])
def test_cleanup_rejects_paths_replaced_by_external_links(tmp_path, replacement):
    sessions, _resources, backups, cleanup = setup(tmp_path)
    directory = backups.storage.stage("selected")
    (directory / "data.tar").write_bytes(b"original")
    workspace = str(tmp_path.resolve())
    preview = cleanup.preview(["staging:selected"], workspace)
    external = tmp_path / "external"
    external.mkdir()
    marker = external / "data.tar"
    marker.write_bytes(b"keep-external")
    if replacement == "file-link":
        (directory / "data.tar").unlink()
        (directory / "data.tar").symlink_to(marker)
    else:
        backups.storage.root.rename(tmp_path / "original-backups")
        backups.storage.root.symlink_to(external, target_is_directory=True)
    with pytest.raises(AndroidError) as error:
        cleanup.execute(workspace, digest(preview), "changed-link")
    assert error.value.status == 409
    assert marker.read_bytes() == b"keep-external"
    sessions.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["backup", "restore"])
async def test_runtime_backup_and_restore_hold_the_cleanup_lease(tmp_path, action):
    import asyncio
    import io
    import tarfile

    sessions, _resources, backups, cleanup = setup(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        archive.addfile(tarfile.TarInfo("data/file"))

    class Runtime:
        blocked = False

        async def inspect(self, _device):
            return {"androidStatus": "stopped"}

        async def backup_volume(self, _device):
            if self.blocked:
                entered.set()
                await release.wait()
            return stream.getvalue()

        async def restore_volume(self, _device, _data):
            entered.set()
            await release.wait()

    runtime = Runtime()
    source = {"deviceId": "source", "imageId": "image", "control": "idle"}
    record = await backups.create_with_runtime(source, None, runtime)
    held = backups.storage.stage("held")
    (held / "data.tar").write_bytes(b"preserve")
    workspace = str(tmp_path.resolve())
    preview = cleanup.preview(["staging:held"], workspace)
    runtime.blocked = True
    call = backups.create_with_runtime(source, None, runtime) if action == "backup" else backups.restore_data(record["id"], {"deviceId": "new", "imageId": "image"}, runtime)
    task = asyncio.create_task(call)
    try:
        await asyncio.wait_for(entered.wait(), 2)
        with pytest.raises(AndroidError) as error:
            cleanup.execute(workspace, digest(preview), "concurrent")
        assert error.value.code == "ANDROID_BACKUP_BUSY"
        assert (held / "data.tar").read_bytes() == b"preserve"
    finally:
        release.set()
        await task
        sessions.dispose()


def test_orphan_preview_freezes_source_references_from_its_manifest(tmp_path):
    sessions, _resources, backups, cleanup = setup(tmp_path)
    directory = backups.storage.stage("with-manifest")
    (directory / "data.tar").write_bytes(b"data")
    (directory / "manifest.json").write_text(json.dumps({"formatVersion": 1, "deviceId": "source-device", "imageId": "sha256:" + "a" * 64, "config": {"name": "must-not-leak"}}))
    backups.storage.finalize("with-manifest")
    preview = cleanup.preview(["orphan:with-manifest"], str(tmp_path.resolve()))
    assert preview[0]["references"] == [{"kind": "device", "id": "source-device"}, {"kind": "image", "id": "sha256:" + "a" * 64}]
    assert "must-not-leak" not in str(preview)
    sessions.dispose()


def test_unreadable_frozen_files_return_conflict_without_deletion(tmp_path, monkeypatch):
    sessions, _resources, backups, cleanup = setup(tmp_path)
    directory = backups.storage.stage("unreadable")
    (directory / "data.tar").write_bytes(b"preserve")
    workspace = str(tmp_path.resolve())
    preview = cleanup.preview(["staging:unreadable"], workspace)

    def denied(_directory):
        raise PermissionError("permission changed after preview")

    monkeypatch.setattr(backups.storage, "snapshot", denied)
    with pytest.raises(AndroidError) as error:
        cleanup.execute(workspace, digest(preview), "unreadable-cleanup")
    assert error.value.status == 409
    assert (directory / "data.tar").read_bytes() == b"preserve"
    sessions.dispose()
