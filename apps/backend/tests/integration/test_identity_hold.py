"""Remediation M4 S8-2 (R4-12): an identity keeps its work copy between tasks of one batch.

The instance is *held* while no task runs — its browser is already closed, so the copy is quiet by
construction — and the identity's next task in the same batch re-attaches it instead of restoring a new
copy. Another batch waits. Nothing here saves or cleans; that is the release (S8-3).
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text

from autoflow.application.project_runs.queries import _cleanup
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.environment_models import (
    ProjectEnvironmentInstanceRow,
    ProjectEnvironmentOccupancyRow,
)
from autoflow.infrastructure.database.identities import SqlAlchemyIdentities
from autoflow.infrastructure.database.identity_models import IdentityRow
from autoflow.infrastructure.database.project_claims import SqlAlchemyProjectInputGroups
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.project_lifecycle import BUSY_INSTANCE_STATES
from tests.contract.test_project_environments import (
    PROFILE,
    _closed_instance,
    _project,
    make,
)
from tests.integration.test_identity_exclusivity import _row
from tests.integration.test_identity_runtime import POLICY, _save
from tests.integration.test_project_input_groups import (
    _add_record,
    _empty_table,
    _input,
)

BATCH = "batch-1"


@pytest.fixture
def world(tmp_path):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    factory = service.environments._session_factory
    yield client, service, project_id, SqlAlchemyIdentities(factory), factory
    factory.dispose()


def _attach(service, factory, project_id, identity_id, *, batch_id=BATCH, session_mode="perIdentity"):
    """What the claim transaction does for one task of the identity."""
    with factory() as session:
        session.execute(text("BEGIN IMMEDIATE"))
        instance = service.reserve_task_instance(
            session, project_id, str(uuid4()), str(uuid4()), POLICY, {"accounts": {"currentIdentityId": identity_id}},
            session_mode=session_mode, batch_id=batch_id,
        )
        session.commit()
    return instance


def _finish(service, instance, *, retain=False, batch_id=BATCH):
    """What End does for a perIdentity task: the browser is closed, then the instance is held."""
    closed = service.environments.set_instance_state(instance.instance_id, "closed")
    return service.environments.hold_identity_instance(
        closed.project_id, closed.instance_id, closed.instance_use_generation, batch_id=batch_id, retain=retain,
    )


def _login_marker(service, instance):
    path = service.instance_path(instance.instance_id)
    (path / "Default").mkdir(exist_ok=True)
    (path / "Default" / "Cookies").write_bytes(b"login")


def _row_of(factory, instance_id):
    with factory() as session:
        return session.get(ProjectEnvironmentInstanceRow, instance_id)


@pytest.mark.parametrize("has_login", [False, True])
def test_the_next_task_of_a_batch_reuses_the_held_copy_without_restoring_it(world, monkeypatch, has_login):
    client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号A", template_profile_id=PROFILE)
    environment_id = None
    if has_login:
        environment_id = _save(client, project_id, _closed_instance(service, project_id, b"login").instance_id)["environmentId"]
        with factory() as session:
            session.get(IdentityRow, identity.identity_id).environment_id = environment_id
            session.commit()
    first = _attach(service, factory, project_id, identity.identity_id)
    assert first.state == "reserved" and first.identity_id == identity.identity_id
    service.environments.set_instance_state(first.instance_id, "active")
    service.store.prepare_instance(first.instance_id)
    _login_marker(service, first)
    held = _finish(service, first, retain=True)
    assert held.state == "identity_held" and held.active_run_id is None and held.held_batch_id == BATCH and held.retain_on_release

    def refuse(*_args, **_kwargs):
        raise AssertionError("a re-attached copy must never be restored or re-prepared")

    monkeypatch.setattr(service.store, "restore_generation", refuse)
    monkeypatch.setattr(service.store, "prepare_instance", refuse)
    generations = []
    for _ in range(2):
        again = _attach(service, factory, project_id, identity.identity_id)
        generations.append(again.instance_use_generation)
        assert again.instance_id == first.instance_id and again.state == "active" and again.held_batch_id is None
        assert (service.instance_path(again.instance_id) / "Default" / "Cookies").read_bytes() == b"login"
        if has_login:
            with factory() as session:
                occupancy = session.get(ProjectEnvironmentOccupancyRow, environment_id)
            assert occupancy.instance_id == first.instance_id and occupancy.holder_id == again.active_task_id
        _finish(service, again)
    assert generations == [2, 3], "every re-attach gets a new use generation, so an earlier task's End is fenced off"
    assert _row_of(factory, first.instance_id).retain_on_release, "a later End without retain does not withdraw the request"


def test_another_batch_waits_for_the_held_copy(world):
    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号B", template_profile_id=PROFILE)
    first = _attach(service, factory, project_id, identity.identity_id)
    service.environments.set_instance_state(first.instance_id, "active")
    _finish(service, first)
    with pytest.raises(ProjectError) as busy:
        _attach(service, factory, project_id, identity.identity_id, batch_id="batch-2")
    assert busy.value.code == "ENVIRONMENT_BUSY" and busy.value.details["instanceId"] == first.instance_id
    assert _row_of(factory, first.instance_id).state == "identity_held"


def test_only_perIdentity_runs_take_the_held_copy(world):
    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号C", template_profile_id=PROFILE)
    first = _attach(service, factory, project_id, identity.identity_id)
    service.environments.set_instance_state(first.instance_id, "active")
    _finish(service, first)
    with pytest.raises(ProjectError) as busy:
        _attach(service, factory, project_id, identity.identity_id, session_mode=None)
    assert busy.value.code == "ENVIRONMENT_BUSY"


def test_a_held_copy_that_is_still_open_is_refused_not_reused(world):
    """After a restart a Chromium may still hold the copy; it must be checked, never taken as idle."""
    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号D", template_profile_id=PROFILE)
    first = _attach(service, factory, project_id, identity.identity_id)
    service.environments.set_instance_state(first.instance_id, "active")
    _finish(service, first)
    lock = service.instance_path(first.instance_id) / "SingletonLock"
    lock.write_text("host-1")
    with pytest.raises(ProjectError) as open_browser:
        _attach(service, factory, project_id, identity.identity_id)
    assert open_browser.value.code == "INSTANCE_NOT_QUIESCENT"
    assert _row_of(factory, first.instance_id).state == "identity_held"
    lock.unlink()
    assert _attach(service, factory, project_id, identity.identity_id).instance_id == first.instance_id


def test_re_attaching_respects_the_live_instance_limit(tmp_path):
    _client, projects, service = make(tmp_path, max_live_instances=1)
    project_id = _project(projects)
    factory = service.environments._session_factory
    identities = SqlAlchemyIdentities(factory)
    identity = identities.create(project_id, "账号E", template_profile_id=PROFILE)
    first = _attach(service, factory, project_id, identity.identity_id)
    service.environments.set_instance_state(first.instance_id, "active")
    _finish(service, first)
    other = identities.create(project_id, "账号F", template_profile_id=PROFILE)
    taker = _attach(service, factory, project_id, other.identity_id)  # fills the only live slot
    with pytest.raises(ProjectError) as full:
        _attach(service, factory, project_id, identity.identity_id)
    assert full.value.code == "CAPACITY_EXHAUSTED"
    assert _row_of(factory, first.instance_id).state == "identity_held"
    service.environments.set_instance_state(taker.instance_id, "cleaned")
    assert _attach(service, factory, project_id, identity.identity_id).instance_id == first.instance_id
    factory.dispose()


def test_a_held_copy_for_another_environment_generation_is_not_taken(world):
    client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号G", template_profile_id=PROFILE)
    first = _attach(service, factory, project_id, identity.identity_id)
    service.environments.set_instance_state(first.instance_id, "active")
    _finish(service, first)
    # The identity gained a saved login meanwhile: the held copy no longer matches what the claim resolved.
    environment_id = _save(client, project_id, _closed_instance(service, project_id, b"other").instance_id)["environmentId"]
    with factory() as session:
        session.get(IdentityRow, identity.identity_id).environment_id = environment_id
        session.commit()
    with pytest.raises(ProjectError) as stale:
        _attach(service, factory, project_id, identity.identity_id)
    assert stale.value.code == "ENVIRONMENT_BUSY"
    assert _row_of(factory, first.instance_id).state == "identity_held"


def test_holding_is_idempotent_and_refuses_a_stale_or_foreign_instance(world):
    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号H", template_profile_id=PROFILE)
    first = _attach(service, factory, project_id, identity.identity_id)
    service.environments.set_instance_state(first.instance_id, "active")
    environments = service.environments
    with pytest.raises(ProjectError) as not_quiet:  # the browser is not confirmed closed yet
        environments.hold_identity_instance(project_id, first.instance_id, 1, batch_id=BATCH, retain=False)
    assert not_quiet.value.code == "INSTANCE_OWNERSHIP_UNKNOWN"
    closed = environments.set_instance_state(first.instance_id, "closed")
    with pytest.raises(ProjectError) as stale:
        environments.hold_identity_instance(project_id, first.instance_id, 99, batch_id=BATCH, retain=False)
    assert stale.value.code == "INSTANCE_OWNERSHIP_UNKNOWN"
    held = environments.hold_identity_instance(project_id, first.instance_id, closed.instance_use_generation, batch_id=BATCH, retain=False)
    replay = environments.hold_identity_instance(project_id, first.instance_id, closed.instance_use_generation, batch_id=BATCH, retain=True)
    assert replay.state == "identity_held" and replay.updated_at >= held.updated_at and replay.retain_on_release
    plain = _closed_instance(service, project_id, b"x")  # no identity
    with pytest.raises(ProjectError):
        environments.hold_identity_instance(project_id, plain.instance_id, plain.instance_use_generation, batch_id=BATCH, retain=False)


def test_a_held_copy_is_never_cleaned_up_or_archived_away(world):
    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号I", template_profile_id=PROFILE)
    first = _attach(service, factory, project_id, identity.identity_id)
    service.environments.set_instance_state(first.instance_id, "active")
    _login_marker(service, first)
    _finish(service, first)
    assert service.environments.disposable_task_instances() == []
    service.cleanup_terminal_tasks()
    assert (service.instance_path(first.instance_id) / "Default" / "Cookies").exists()
    assert "identity_held" in BUSY_INSTANCE_STATES, "project archive/delete must not rmtree a held copy"
    assert service.environments.count_live_instances(project_id) == 0, "a closed browser does not count against the live limit"


def test_the_task_view_says_what_happens_to_the_shared_copy():
    held = SimpleNamespace(state="identity_held")

    class Session:
        def __init__(self, instance):
            self.instance = instance

        def scalar(self, _query):
            return self.instance

    pending = _cleanup(Session(held), "p", "t", SimpleNamespace(resource_request={"sessionMode": "perIdentity"}, status="succeeded", terminal=True))
    assert pending["status"] == "pending" and "共用" in pending["message"]
    moved_on = _cleanup(Session(None), "p", "t", SimpleNamespace(resource_request={"sessionMode": "perIdentity"}, status="succeeded", terminal=True))
    assert moved_on["status"] == "notRequired" and "共用" in moved_on["message"]
    ordinary = _cleanup(Session(None), "p", "t", SimpleNamespace(resource_request={}, status="succeeded", terminal=True))
    assert ordinary["status"] == "succeeded"


# --- the claim: the identity's own batch may continue, others wait --------------------------------------------------


def _claim_world(world):
    _client, _service, project_id, identities, factory = world
    table, field = _empty_table(factory, project_id, "账号")
    record = _add_record(factory, project_id, table, field, "a")
    identity = identities.create(project_id, "闲", template_profile_id=PROFILE)
    ref = record["ref"]
    with factory() as session:
        session.get(DataRecordRow, (ref["datasetGeneration"], ref["recordKey"]["type"], ref["recordKey"]["value"])).current_identity_id = identity.identity_id
        session.commit()
    plan = {"inputs": [_input(project_id, table, field, "账号")]}
    return project_id, factory, plan, plan["inputs"][0]["inputId"], identity


@pytest.mark.parametrize("state, batch_id, available", [
    ("identity_held", BATCH, True),          # the batch that holds it carries on
    ("identity_held", "batch-2", False),     # another batch waits for the release
    ("active", BATCH, False),                # a running task is never joined
    ("closed", BATCH, False),
])
def test_only_the_holding_batch_may_claim_rows_of_a_held_identity(world, state, batch_id, available):
    project_id, factory, plan, input_id, identity = _claim_world(world)
    with factory.begin() as session:
        row = _row(project_id, identity.identity_id, state)
        row.held_batch_id = BATCH
        session.add(row)
    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, plan, identity_input_id=input_id, identity_batch_id=batch_id,
        )
    assert result.status == ("ready" if available else "temporarilyBusy")
