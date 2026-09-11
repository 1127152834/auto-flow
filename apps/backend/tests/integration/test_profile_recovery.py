from pathlib import Path

from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.infrastructure.filesystem.profile_data import FilesystemProfileDataStore


class InstalledKernel:
    def is_installed(self, edition: str, version: str) -> bool:
        return edition == "public" and version == "146.0.1"


PAYLOAD = {"name": "Recovery", "browserVersion": "146.0.1"}


class FailFirstPurgeStore(FilesystemProfileDataStore):
    def __init__(self, profiles_root: Path) -> None:
        super().__init__(profiles_root)
        self.failed = False

    def purge(self, token: str) -> None:
        if not self.failed:
            self.failed = True
            raise OSError("simulated post-commit cleanup failure")
        super().purge(token)


def _app(data_dir: Path, *, profile_data_store=None):
    return create_app(
        Settings(data_dir=str(data_dir), instance_id="recovery", instance_token="secret"),
        installed_kernel_lookup=InstalledKernel(),
        profile_data_store=profile_data_store,
    )


def test_restart_restores_staged_data_when_database_delete_never_committed(
    tmp_path: Path,
) -> None:
    headers = {"x-autoflow-token": "secret"}
    with TestClient(_app(tmp_path), headers=headers) as client:
        profile = client.post("/api/v1/profiles", json=PAYLOAD).json()
        source = client.app.state.paths.profiles / profile["id"]
        source.mkdir()
        (source / "Cookies").write_text("data")

    store = FilesystemProfileDataStore(tmp_path / "workspace" / "profiles")
    token = store.stage(profile["id"])
    assert token is not None

    with TestClient(_app(tmp_path), headers=headers) as recovered:
        assert recovered.get(f"/api/v1/profiles/{profile['id']}").status_code == 200
        assert (source / "Cookies").read_text() == "data"
        assert not (store.trash / token).exists()


def test_restart_purges_staged_data_after_database_delete_committed(tmp_path: Path) -> None:
    headers = {"x-autoflow-token": "secret"}
    store = FailFirstPurgeStore(tmp_path / "workspace" / "profiles")
    with TestClient(_app(tmp_path, profile_data_store=store), headers=headers) as client:
        profile = client.post("/api/v1/profiles", json=PAYLOAD).json()
        source = client.app.state.paths.profiles / profile["id"]
        source.mkdir()
        (source / "Cookies").write_text("data")
        deleted = client.delete(f"/api/v1/profiles/{profile['id']}")
        assert deleted.status_code == 204
        assert client.get(f"/api/v1/profiles/{profile['id']}").status_code == 404
        pending = list(store.trash.iterdir())
        assert len(pending) == 1

    with TestClient(_app(tmp_path), headers=headers):
        assert not pending[0].exists()


def test_restart_preserves_staged_data_when_restore_fails(
    monkeypatch, tmp_path: Path
) -> None:
    headers = {"x-autoflow-token": "secret"}
    with TestClient(_app(tmp_path), headers=headers) as client:
        profile = client.post("/api/v1/profiles", json=PAYLOAD).json()
        source = client.app.state.paths.profiles / profile["id"]
        source.mkdir()
        store = FilesystemProfileDataStore(client.app.state.paths.profiles)
        token = store.stage(profile["id"])
        assert token is not None

    original_rename = Path.rename

    def fail_restore(path: Path, target: Path):
        if path == store.trash / token:
            raise OSError("restore unavailable")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_restore)
    with TestClient(_app(tmp_path), headers=headers):
        assert (store.trash / token).is_dir()
        assert not source.exists()
