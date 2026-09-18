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
