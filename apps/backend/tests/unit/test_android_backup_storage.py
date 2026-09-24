from pathlib import Path, PurePosixPath

import pytest

from autoflow.providers.android.backup_storage import (
    BackupStorage,
    validate_archive_path,
)


def test_parent_traversal_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_archive_path(PurePosixPath("../outside"))


def test_absolute_and_device_entries_are_rejected() -> None:
    with pytest.raises(ValueError):
        validate_archive_path(PurePosixPath("/etc/passwd"))
    with pytest.raises(ValueError):
        validate_archive_path(PurePosixPath("dev/null"), entry_type="char")


def test_internal_relative_path_is_allowed() -> None:
    validate_archive_path(PurePosixPath("data/shared_prefs/settings.xml"))


def test_storage_rejects_symlinked_staging_and_publishes_private_files(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "backups"
    root.mkdir()
    (root / "staging").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        BackupStorage(root).stage("backup")

    (root / "staging").unlink()
    storage = BackupStorage(root)
    staged = storage.stage("backup")
    file = staged / "data.tar"
    file.write_bytes(b"data")
    file.chmod(0o644)
    final = storage.finalize("backup")
    assert final.is_dir() and (final / "data.tar").read_bytes() == b"data"
    assert final.stat().st_mode & 0o777 == 0o700
    assert (final / "data.tar").stat().st_mode & 0o777 == 0o600


def test_storage_rejects_symlinked_root_before_writing_outside(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "backups"
    root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        BackupStorage(root).stage("backup")
    assert list(outside.iterdir()) == []


def test_all_backup_directories_are_private_even_with_permissive_umask(tmp_path):
    import os

    root = tmp_path / "backups"
    previous = os.umask(0)
    try:
        staged = BackupStorage(root).stage("backup")
    finally:
        os.umask(previous)
    for directory in (root, root / "staging", staged):
        assert directory.stat().st_mode & 0o777 == 0o700


def test_publication_syncs_files_before_rename_and_parent_directories_after(tmp_path, monkeypatch):
    import os
    import stat

    storage = BackupStorage(tmp_path / "backups")
    stage = storage.stage("backup")
    (stage / "data.tar").write_bytes(b"data")
    (stage / "manifest.json").write_bytes(b"manifest")
    events = []
    fsync, replace = os.fsync, os.replace

    def sync(fd):
        events.append("file" if stat.S_ISREG(os.fstat(fd).st_mode) else "directory")
        fsync(fd)

    def publish(source, target):
        events.append("rename")
        replace(source, target)

    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "replace", publish)
    storage.finalize("backup")
    position = events.index("rename")
    assert events[:position].count("file") == 2
    assert "directory" in events[:position]
    assert events[position + 1:].count("directory") >= 2


def test_post_rename_sync_failure_does_not_leave_a_published_backup(tmp_path, monkeypatch):
    import os

    storage = BackupStorage(tmp_path / "backups")
    stage = storage.stage("backup")
    (stage / "data.tar").write_bytes(b"data")
    fsync = os.fsync
    failed = False

    def sync(fd):
        nonlocal failed
        if (storage.final / "backup").exists() and not failed:
            failed = True
            raise OSError("injected directory fsync failure")
        fsync(fd)

    monkeypatch.setattr(os, "fsync", sync)
    with pytest.raises(OSError, match="fsync failure"):
        storage.finalize("backup")
    assert not (storage.final / "backup").exists()


def test_first_backup_space_budget_includes_all_missing_directories(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from autoflow.domain.android.ports import AndroidError
    from autoflow.providers.android import backup_storage

    storage = backup_storage.BackupStorage(tmp_path / "backups")
    free = 16384  # Two archive blocks, one manifest block and only one directory block.
    monkeypatch.setattr(backup_storage.shutil, "disk_usage", lambda _path: SimpleNamespace(free=free))
    monkeypatch.setattr(backup_storage.os, "statvfs", lambda _path: SimpleNamespace(f_frsize=4096))
    with pytest.raises(AndroidError) as rejected:
        storage.require_space(8192, 100)
    assert rejected.value.code == "ANDROID_DISK_SPACE_INSUFFICIENT"
    free = 28672  # Plus all four initially missing directories.
    storage.require_space(8192, 100)
    assert not storage.root.exists()
