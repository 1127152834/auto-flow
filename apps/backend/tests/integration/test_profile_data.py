from multiprocessing import get_context
from pathlib import Path

import pytest

from autoflow.domain.profiles.errors import ProfileDataPathInvalid, ProfileDirectoryBusy
from autoflow.infrastructure.filesystem.profile_data import (
    FilesystemProfileDataStore,
    FilesystemProfileUsageGuard,
)

PROFILE_ID = "00000000-0000-0000-0000-000000000001"


def _hold_profile_lock(root: str, ready, release) -> None:
    with FilesystemProfileUsageGuard(Path(root)).guard(PROFILE_ID):
        ready.set()
        release.wait(10)


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

    store.retry_pending(lambda _profile_id: False)

    assert not (root / ".trash" / token).exists()
    assert unrelated.exists()


def test_retry_pending_restores_data_still_referenced_by_database(tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    source = root / PROFILE_ID
    source.mkdir(parents=True)
    (source / "Cookies").write_text("data")
    store = FilesystemProfileDataStore(root)
    token = store.stage(PROFILE_ID)
    assert token is not None

    store.retry_pending(lambda profile_id: profile_id == PROFILE_ID)

    assert (source / "Cookies").read_text() == "data"
    assert not (root / ".trash" / token).exists()


def test_retry_pending_preserves_both_copies_on_restore_conflict(tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    source = root / PROFILE_ID
    source.mkdir(parents=True)
    store = FilesystemProfileDataStore(root)
    token = store.stage(PROFILE_ID)
    assert token is not None
    source.mkdir()

    store.retry_pending(lambda _profile_id: True)

    assert source.is_dir()
    assert (root / ".trash" / token).is_dir()


def test_retry_pending_preserves_orphan_with_chromium_activity_marker(tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    store = FilesystemProfileDataStore(root)
    token = f"{PROFILE_ID}-{'0' * 32}"
    staged = root / ".trash" / token
    staged.mkdir()
    (staged / "SingletonLock").symlink_to("host-12345")

    store.retry_pending(lambda _profile_id: False)

    assert staged.is_dir()


def test_real_cross_process_profile_lock_blocks_deletion(tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    (root / PROFILE_ID).mkdir(parents=True)
    context = get_context("spawn")
    ready = context.Event()
    release = context.Event()
    process = context.Process(target=_hold_profile_lock, args=(str(root), ready, release))
    process.start()
    try:
        assert ready.wait(5)
        with (
            pytest.raises(ProfileDirectoryBusy),
            FilesystemProfileUsageGuard(root).guard(PROFILE_ID),
        ):
            pytest.fail("an active profile lock was acquired twice")
        assert (root / PROFILE_ID).is_dir()
    finally:
        release.set()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
    assert process.exitcode == 0


def test_open_profile_with_chromium_activity_marker_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    profile = root / PROFILE_ID
    profile.mkdir(parents=True)
    cookies = profile / "Cookies"
    cookies.write_text("data")
    (profile / "SingletonLock").symlink_to("host-12345")

    with cookies.open("rb") as open_handle:
        assert open_handle.read() == b"data"
        with (
            pytest.raises(ProfileDirectoryBusy),
            FilesystemProfileUsageGuard(root).guard(PROFILE_ID),
        ):
            pytest.fail("a profile with a Chromium activity marker was not rejected")

    assert profile.is_dir()
