"""Remediation M4 S8-3 (R4-12): an identity's held copy is saved once, then cleaned.

The login changes of every task that reused the copy go into ONE new environment version when the
identity's instance is released — not one save per task. A copy whose browser may still be open, or whose
save fails, never becomes a published version of a torn login.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from autoflow.infrastructure.database.environment_models import (
    ProjectEnvironmentOccupancyRow,
    ProjectEnvironmentRow,
)
from autoflow.infrastructure.database.identities import SqlAlchemyIdentities
from autoflow.infrastructure.database.identity_models import IdentityRow
from tests.contract.test_project_environments import (
    PROFILE,
    _closed_instance,
    _project,
    make,
)
from tests.integration.test_identity_hold import _attach, _finish, _row_of
from tests.integration.test_identity_runtime import _save

BATCH = "batch-1"


@pytest.fixture
def world(tmp_path):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    factory = service.environments._session_factory
    yield client, service, project_id, SqlAlchemyIdentities(factory), factory
    factory.dispose()


def _task(service, factory, project_id, identity_id, marker, *, retain):
    """One perIdentity task: attach (or re-attach) the copy, log in, finish, hold."""
    instance = _attach(service, factory, project_id, identity_id)
    path = service.instance_path(instance.instance_id)
    if instance.instance_use_generation == 1 and instance.environment_id is None:
        service.store.prepare_instance(instance.instance_id)
    elif instance.instance_use_generation == 1:
        service.store.restore_generation(
            instance.environment_id, instance.source_content_generation, instance.instance_id,
            identity_package=instance.identity_package,
        )
    service.environments.set_instance_state(instance.instance_id, "active")
    (path / "Default").mkdir(exist_ok=True)
    (path / "Default" / f"login-{marker}").write_bytes(marker.encode())
    return _finish(service, instance, retain=retain)


def _environments(factory, project_id):
    with factory() as session:
        return session.query(ProjectEnvironmentRow).filter_by(project_id=project_id).order_by(ProjectEnvironmentRow.created_at).all()


def _identity(factory, identity_id):
    with factory() as session:
        return session.get(IdentityRow, identity_id).environment_id


def _with_login(client, service, factory, project_id, identity_id):
    environment_id = _save(client, project_id, _closed_instance(service, project_id, b"login").instance_id)["environmentId"]
    with factory() as session:
        session.get(IdentityRow, identity_id).environment_id = environment_id
        session.commit()
    return environment_id


def test_three_tasks_produce_one_saved_login_that_the_identity_then_uses(world):
    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号A", template_profile_id=PROFILE)
    for marker in ("one", "two", "three"):
        held = _task(service, factory, project_id, identity.identity_id, marker, retain=marker == "one")
    assert _environments(factory, project_id) == [], "nothing is saved while the identity keeps working"
    assert service.release_identity_instance(project_id, held.instance_id) is True
    saved = _environments(factory, project_id)
    assert len(saved) == 1 and saved[0].content_generation == 1
    environment_id = saved[0].id
    assert _identity(factory, identity.identity_id) == environment_id, "the saved login now belongs to the identity"
    for marker in ("one", "two", "three"):
        assert (service.store.generation_dir(environment_id, 1) / "Default" / f"login-{marker}").read_bytes() == marker.encode()
    row = _row_of(factory, held.instance_id)
    assert row.state == "cleaned" and not (service.store.root / "instances" / held.instance_id).exists()
    with factory() as session:
        assert session.get(ProjectEnvironmentOccupancyRow, environment_id) is None
    # The next task starts from the saved login, in a new copy.
    again = _attach(service, factory, project_id, identity.identity_id)
    assert again.instance_id != held.instance_id and again.environment_id == environment_id


def test_a_login_that_already_exists_gains_exactly_one_version(world):
    client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号B", template_profile_id=PROFILE)
    environment_id = _with_login(client, service, factory, project_id, identity.identity_id)
    for marker in ("one", "two", "three"):
        held = _task(service, factory, project_id, identity.identity_id, marker, retain=True)
    service.release_identity_instance(project_id, held.instance_id)
    environments = _environments(factory, project_id)
    current = next(item for item in environments if item.id == environment_id)
    assert current.content_generation == 2, "one save for three tasks, not three"
    assert len(environments) == 1
    assert (service.store.generation_dir(environment_id, 2) / "Default" / "login-three").exists()


def test_a_copy_nobody_asked_to_save_is_discarded_and_the_last_version_stands(world):
    client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号C", template_profile_id=PROFILE)
    environment_id = _with_login(client, service, factory, project_id, identity.identity_id)
    held = _task(service, factory, project_id, identity.identity_id, "one", retain=False)
    assert service.release_identity_instance(project_id, held.instance_id) is True
    assert _row_of(factory, held.instance_id).state == "cleaned"
    assert next(item for item in _environments(factory, project_id) if item.id == environment_id).content_generation == 1


def test_a_copy_whose_browser_may_still_be_open_is_neither_saved_nor_cleaned(world, caplog):
    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号D", template_profile_id=PROFILE)
    held = _task(service, factory, project_id, identity.identity_id, "one", retain=True)
    lock = service.instance_path(held.instance_id) / "SingletonLock"
    lock.write_text("host-1")
    with caplog.at_level(logging.WARNING):
        assert service.release_identity_instance(project_id, held.instance_id) is False
    assert "SingletonLock" in caplog.text or "浏览器" in caplog.text
    assert _row_of(factory, held.instance_id).state == "closing", "waits for verification; the identity stays taken"
    assert _environments(factory, project_id) == []
    assert (service.instance_path(held.instance_id) / "Default" / "login-one").exists()
    lock.unlink()
    assert service.release_identity_instance(project_id, held.instance_id) is True
    assert len(_environments(factory, project_id)) == 1


def test_a_failed_save_keeps_the_copy_for_a_person_frees_the_identity_and_says_why(world, monkeypatch, caplog):
    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号E", template_profile_id=PROFILE)
    held = _task(service, factory, project_id, identity.identity_id, "one", retain=True)

    def full_disk(*_args, **_kwargs):
        raise OSError("磁盘已满")

    monkeypatch.setattr(service.store, "publish", full_disk)
    with caplog.at_level(logging.WARNING):
        assert service.release_identity_instance(project_id, held.instance_id) is True
    assert _row_of(factory, held.instance_id).state == "retained_unsaved"
    assert (service.instance_path(held.instance_id) / "Default" / "login-one").exists(), "the work copy is kept"
    assert "STORAGE_FAILED" in caplog.text or "磁盘已满" in caplog.text or "保存" in caplog.text
    assert _attach(service, factory, project_id, identity.identity_id).instance_id != held.instance_id, "the identity works again"


def test_a_release_interrupted_after_the_save_finishes_without_a_second_environment(world, monkeypatch):
    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号F", template_profile_id=PROFILE)
    held = _task(service, factory, project_id, identity.identity_id, "one", retain=True)
    real_close = service.close_instance
    calls = {"count": 0}

    def crash(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("进程在清理前退出")
        return real_close(*args, **kwargs)

    monkeypatch.setattr(service, "close_instance", crash)
    with pytest.raises(RuntimeError):
        service.release_identity_instance(project_id, held.instance_id)
    assert _row_of(factory, held.instance_id).state == "closed" and len(_environments(factory, project_id)) == 1
    assert service.release_identity_instance(project_id, held.instance_id) is True
    assert len(_environments(factory, project_id)) == 1, "the retry replays the same save, it does not make another"
    assert _row_of(factory, held.instance_id).state == "cleaned"


def test_a_missing_work_directory_is_never_published_as_an_empty_version(world, caplog):
    import shutil

    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号G", template_profile_id=PROFILE)
    held = _task(service, factory, project_id, identity.identity_id, "one", retain=True)
    shutil.rmtree(service.store.root / "instances" / held.instance_id)
    with caplog.at_level(logging.WARNING):
        assert service.release_identity_instance(project_id, held.instance_id) is True
    assert _environments(factory, project_id) == []
    assert _row_of(factory, held.instance_id).state == "cleaned"
    assert "工作副本" in caplog.text


def test_release_and_re_attach_cannot_both_win(world):
    from autoflow.domain.projects.models import ProjectError as Error

    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号H", template_profile_id=PROFILE)
    held = _task(service, factory, project_id, identity.identity_id, "one", retain=False)
    assert service.environments.begin_identity_release(project_id, held.instance_id).state == "closing"
    with pytest.raises(Error) as busy:
        _attach(service, factory, project_id, identity.identity_id)
    assert busy.value.code == "ENVIRONMENT_BUSY"
    # And the other way round: an instance a task already took is not releasable.
    other = identities.create(project_id, "账号I", template_profile_id=PROFILE)
    first = _task(service, factory, project_id, other.identity_id, "x", retain=False)
    taken = _attach(service, factory, project_id, other.identity_id)
    assert taken.instance_id == first.instance_id
    assert service.environments.begin_identity_release(project_id, first.instance_id) is None


def test_saved_environment_names_derive_from_the_identity_and_stay_unique(world):
    _client, service, project_id, identities, factory = world
    long_name = "同名账号" * 10
    one, two = identities.create(project_id, long_name + "一", template_profile_id=PROFILE), identities.create(project_id, long_name + "二", template_profile_id=PROFILE)
    for identity in (one, two):
        held = _task(service, factory, project_id, identity.identity_id, "x", retain=True)
        assert service.release_identity_instance(project_id, held.instance_id) is True
    names = [item.name for item in _environments(factory, project_id)]
    assert len(names) == 2 and len(set(names)) == 2 and all(len(name) <= 36 for name in names)


def test_the_sweep_releases_what_has_been_idle_and_retries_what_was_interrupted(world):
    _client, service, project_id, identities, factory = world
    idle, fresh, interrupted = (identities.create(project_id, name, template_profile_id=PROFILE) for name in ("闲置", "新鲜", "中断"))
    held = {identity.name: _task(service, factory, project_id, identity.identity_id, "x", retain=True) for identity in (idle, fresh, interrupted)}
    long_ago = datetime.now(UTC) - timedelta(seconds=600)
    with factory.begin() as session:
        session.execute(text("UPDATE project_environment_instances SET updated_at = :then WHERE id = :id"), {"then": long_ago, "id": held["闲置"].instance_id})
        session.execute(text("UPDATE project_environment_instances SET state = 'closing' WHERE id = :id"), {"id": held["中断"].instance_id})
    assert service.release_due_identity_instances(idle_seconds=120, limit=5) == 2
    assert _row_of(factory, held["闲置"].instance_id).state == "cleaned"
    assert _row_of(factory, held["中断"].instance_id).state == "cleaned"
    assert _row_of(factory, held["新鲜"].instance_id).state == "identity_held", "a copy in recent use is left alone"
    assert service.release_due_identity_instances(idle_seconds=120, limit=5) == 0


def test_the_sweep_does_not_touch_instances_that_belong_to_a_run(world):
    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "运行中", template_profile_id=PROFILE)
    running = _attach(service, factory, project_id, identity.identity_id)
    service.environments.set_instance_state(running.instance_id, "active")
    plain = _closed_instance(service, project_id, b"x")  # an ordinary task copy waiting for its own cleanup
    assert service.release_due_identity_instances(idle_seconds=0, limit=5) == 0
    assert _row_of(factory, running.instance_id).state == "active" and _row_of(factory, plain.instance_id).state == "closed"
