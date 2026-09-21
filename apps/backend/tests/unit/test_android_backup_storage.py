from pathlib import PurePosixPath

import pytest

from autoflow.providers.android.backup_storage import validate_archive_path


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
