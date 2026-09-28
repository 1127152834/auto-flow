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


def test_new_digest_checks_bytes_and_legacy_digest_remains_readable(tmp_path):
    import shutil

    import pytest
    store = EnvironmentStore(tmp_path / 'store')
    instance = store.prepare_instance('legacy')
    value = instance / 'Cookies'
    value.write_bytes(b'abcd')
    legacy = store.digest(instance)
    value.write_bytes(b'efgh')
    assert store.digest(instance) == legacy
    old_generation = store.generation_dir('legacy-env', 1)
    shutil.copytree(instance, old_generation)
    (old_generation / '.digest').write_text(legacy)
    restored = store.restore_generation('legacy-env', 1, 'legacy-restored')
    assert store.digest(restored) == legacy
    assert (restored / 'Cookies').read_bytes() == b'efgh'
    assert not (restored / '.digest-version').exists()
    store.stage_candidate('v2', 'legacy')
    saved = store.publish('env', 1, 'v2')
    directory = store.generation_dir('env', 1)
    assert store.digest(directory) == saved
    (directory / 'Cookies').write_bytes(b'ijkl')
    assert store.digest(directory) != saved
    (directory / '.digest-version').write_text('unknown')
    with pytest.raises(ValueError, match='digest version'):
        store.digest(directory)
