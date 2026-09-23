import socket
import sys

import pytest

from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore


def test_publish_restore_and_digest_ignore_file_bytes(tmp_path):
    store = EnvironmentStore(tmp_path / "store")
    instance = store.prepare_instance("instance-1")
    (instance / "Default").mkdir()
    (instance / "Default" / "Cookies").write_bytes(b"secret-cookie")
    (instance / "SingletonLock").symlink_to("host-12345")
    (instance / "SingletonCookie").write_text("lock")
    digest = store.stage_candidate("save-1", "instance-1")
    published = store.publish("env-1", 1, "save-1")
    assert published == digest
    generation = store.generation_dir("env-1", 1)
    assert not (generation / "SingletonLock").exists()
    assert not (generation / "SingletonCookie").exists()
    restored = store.restore_generation("env-1", 1, "instance-2")
    assert (restored / "Default" / "Cookies").read_bytes() == b"secret-cookie"
    assert not (restored / "SingletonLock").exists()
    other = EnvironmentStore(tmp_path / "other")
    copy = other.prepare_instance("instance-3")
    (copy / "Default").mkdir()
    (copy / "Default" / "Cookies").write_bytes(b"SECRET-COOKIE")
    assert other.digest(copy) == store.digest(instance)


@pytest.mark.skipif(sys.platform != "darwin", reason="Chromium macOS singleton ownership")
def test_runtime_lock_ignores_socket_only_after_local_owner_exits(tmp_path, monkeypatch):
    import autoflow.infrastructure.filesystem.environment_store as module

    store = EnvironmentStore(tmp_path / "store")
    instance = store.prepare_instance("instance-1")
    socket_path = tmp_path / "orphan-socket"
    socket_path.touch()
    (instance / "SingletonSocket").symlink_to(socket_path)
    lock = instance / "SingletonLock"
    lock.symlink_to(f"{socket.gethostname()}-12345")

    monkeypatch.setattr(module, "process_identity_is_alive", lambda pid, birth: False, raising=False)
    assert not store.runtime_lock_present("instance-1")

    (instance / f"{socket.gethostname()}-12345").touch()
    assert store.runtime_lock_present("instance-1")
    (instance / f"{socket.gethostname()}-12345").unlink()

    def replace_owner(_pid, _birth):
        lock.unlink()
        lock.symlink_to(f"{socket.gethostname()}-54321")
        return False

    monkeypatch.setattr(module, "process_identity_is_alive", replace_owner)
    assert store.runtime_lock_present("instance-1")
    lock.unlink()
    lock.symlink_to(f"{socket.gethostname()}-12345")

    monkeypatch.setattr(module, "process_identity_is_alive", lambda pid, birth: True)
    assert store.runtime_lock_present("instance-1")

    lock.unlink()
    lock.symlink_to("other-host-12345")
    monkeypatch.setattr(module, "process_identity_is_alive", lambda pid, birth: False)
    assert store.runtime_lock_present("instance-1")

    lock.unlink()
    assert store.runtime_lock_present("instance-1")

    (instance / "SingletonSocket").unlink()
    lock.symlink_to("malformed")
    assert store.runtime_lock_present("instance-1")
