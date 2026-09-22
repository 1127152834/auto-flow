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
