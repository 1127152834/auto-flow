from pathlib import Path

import pytest

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.infrastructure.filesystem.paths import AppPaths


def test_paths_are_children_of_injected_data_dir(tmp_path):
    paths = AppPaths.from_data_dir(tmp_path)

    assert paths.data_dir == tmp_path
    assert paths.database == tmp_path / "data" / "autoflow.sqlite3"
    assert paths.logs == tmp_path / "logs"
    assert paths.workspace == tmp_path / "workspace"
    assert paths.cache == tmp_path / "cache"
    assert paths.temp == tmp_path / "tmp"


def test_paths_require_an_absolute_data_dir():
    with pytest.raises(ValueError, match="data directory must be absolute"):
        AppPaths.from_data_dir(Path("relative"))


def test_bootstrap_creates_app_directories(tmp_path):
    paths = AppPaths.from_data_dir(tmp_path)

    create_app(Settings(data_dir=str(tmp_path), instance_id="test"))

    for directory in (paths.data_dir, paths.logs, paths.workspace, paths.cache, paths.temp):
        assert directory.is_dir()
