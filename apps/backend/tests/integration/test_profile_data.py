from pathlib import Path

import pytest

from autoflow.domain.profiles.errors import ProfileDataPathInvalid, ProfileDirectoryBusy
from autoflow.infrastructure.filesystem.profile_data import FilesystemProfileDataStore

PROFILE_ID = "00000000-0000-0000-0000-000000000001"


def test_profile_data_can_be_staged_restored_and_purged(tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    source = root / PROFILE_ID
    source.mkdir(parents=True)
    (source / "Cookies").write_text("data")
    store = FilesystemProfileDataStore(root)

    token = store.stage(PROFILE_ID)
    assert token is not None
    assert not source.exists()
    store.restore(PROFILE_ID, token)
    assert (source / "Cookies").read_text() == "data"

    token = store.stage(PROFILE_ID)
    assert token is not None
    store.purge(token)
    assert not (root / ".trash" / token).exists()


@pytest.mark.parametrize("profile_id", ["../escape", "/tmp/escape", "not-a-uuid"])
def test_profile_data_rejects_paths_outside_managed_profile_ids(
    tmp_path: Path, profile_id: str
) -> None:
    store = FilesystemProfileDataStore(tmp_path / "profiles")
    with pytest.raises(ProfileDataPathInvalid):
        store.stage(profile_id)


def test_profile_data_rejects_symlink_profile(tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    outside = tmp_path / "outside"
    outside.mkdir()
    root.mkdir()
    (root / PROFILE_ID).symlink_to(outside, target_is_directory=True)

    with pytest.raises(ProfileDataPathInvalid):
        FilesystemProfileDataStore(root).stage(PROFILE_ID)

    assert outside.is_dir()


def test_profile_data_maps_rename_failure_to_directory_busy(
    monkeypatch, tmp_path: Path
) -> None:
    root = tmp_path / "profiles"
    (root / PROFILE_ID).mkdir(parents=True)
    original_rename = Path.rename

    def fail_profile_rename(path: Path, target: Path):
        if path == root / PROFILE_ID:
            raise OSError("resource busy at /private/profile")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_profile_rename)
    with pytest.raises(ProfileDirectoryBusy) as error:
        FilesystemProfileDataStore(root).stage(PROFILE_ID)
    assert "/private/profile" not in str(error.value)


def test_retry_pending_removes_only_owned_trash_entries(tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    source = root / PROFILE_ID
    source.mkdir(parents=True)
    store = FilesystemProfileDataStore(root)
    token = store.stage(PROFILE_ID)
    assert token is not None
    unrelated = root / ".trash" / "unrelated"
    unrelated.mkdir()

    store.retry_pending()

    assert not (root / ".trash" / token).exists()
    assert unrelated.exists()
