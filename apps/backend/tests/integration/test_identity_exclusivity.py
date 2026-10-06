"""Remediation M4 S8-1 (R4-06): one live instance per identity, whether or not it has a saved login.

Before, exclusivity came only from the environment occupancy (keyed by environment id), so an identity
without a saved login — exactly the first-login case — could open two browsers at once, and the claim
never looked at occupancy, so a busy identity's row ended in an uncaught ENVIRONMENT_BUSY.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.environment_models import (
    ProjectEnvironmentInstanceRow,
)
from autoflow.infrastructure.database.identities import SqlAlchemyIdentities
from autoflow.infrastructure.database.identity_models import IdentityRow
from autoflow.infrastructure.database.project_claims import SqlAlchemyProjectInputGroups
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from tests.contract.test_project_environments import (
    PROFILE,
    _closed_instance,
    _project,
    make,
)
from tests.integration.test_identity_runtime import POLICY, _save
from tests.integration.test_project_input_groups import (
    _add_record,
    _empty_table,
    _input,
)


@pytest.fixture
def world(tmp_path):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    factory = service.environments._session_factory
    yield client, service, project_id, SqlAlchemyIdentities(factory), factory
    factory.dispose()


def _resolve(service, factory, project_id, identity_id):
    with factory() as session:
        return service.environments.resolve_source_in_session(
            session, project_id, POLICY, {"accounts": {"currentIdentityId": identity_id}},
        )


def _reserve(service, factory, project_id, identity_id):
    resolved = _resolve(service, factory, project_id, identity_id)
    return service.reserve(
        project_id, resolved, task_id=str(uuid4()), run_id=str(uuid4()), holder_kind="task", holder_id=str(uuid4()),
    )


def _instances(factory, identity_id):
    with factory() as session:
        return session.query(ProjectEnvironmentInstanceRow).filter_by(identity_id=identity_id).all()


def _with_login(client, service, factory, project_id, identity_id):
    environment_id = _save(client, project_id, _closed_instance(service, project_id, b"login").instance_id)["environmentId"]
    with factory() as session:
        session.get(IdentityRow, identity_id).environment_id = environment_id
        session.commit()
    return environment_id


@pytest.mark.parametrize("has_login", [False, True])
def test_a_second_instance_for_a_busy_identity_is_refused_and_leaves_no_row(world, has_login):
    client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号A", template_profile_id=PROFILE)
    if has_login:
        _with_login(client, service, factory, project_id, identity.identity_id)
    first = _reserve(service, factory, project_id, identity.identity_id)
    assert first.identity_id == identity.identity_id
    with pytest.raises(ProjectError) as busy:
        _reserve(service, factory, project_id, identity.identity_id)
    assert busy.value.code == "ENVIRONMENT_BUSY"
    assert busy.value.details["holderKind"] == "identity" and busy.value.details["instanceId"] == first.instance_id
    assert [row.id for row in _instances(factory, identity.identity_id)] == [first.instance_id]


def test_other_identities_and_runs_without_an_identity_are_not_affected(world):
    _client, service, project_id, identities, factory = world
    one, two = identities.create(project_id, "账号一", template_profile_id=PROFILE), identities.create(project_id, "账号二", template_profile_id=PROFILE)
    _reserve(service, factory, project_id, one.identity_id)
    _reserve(service, factory, project_id, two.identity_id)
    first = _closed_instance(service, project_id, b"x")  # newFromProfile: no identity
    second = _closed_instance(service, project_id, b"y")
    assert first.identity_id is None and second.identity_id is None


@pytest.mark.parametrize("state, frees_the_identity", [
    ("cleaned", True), ("retained_unsaved", True),
    # The work copy still exists in these states, so the identity stays taken.
    ("active", False), ("closed", False), ("cleaning", False), ("cleanup_failed", False), ("unknown", False), ("saving", False),
])
def test_an_identity_is_free_again_only_once_its_work_copy_is_released(world, state, frees_the_identity):
    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号B", template_profile_id=PROFILE)
    first = _reserve(service, factory, project_id, identity.identity_id)
    service.environments.set_instance_state(first.instance_id, state)
    if frees_the_identity:
        assert _reserve(service, factory, project_id, identity.identity_id).instance_id != first.instance_id
    else:
        with pytest.raises(ProjectError) as busy:
            _reserve(service, factory, project_id, identity.identity_id)
        assert busy.value.code == "ENVIRONMENT_BUSY"


def test_the_database_itself_refuses_two_live_instances_for_one_identity(world):
    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号C", template_profile_id=PROFILE)
    _reserve(service, factory, project_id, identity.identity_id)
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.add(_row(project_id, identity.identity_id, "active"))


def _row(project_id, identity_id, state):
    now = datetime.now(UTC)
    return ProjectEnvironmentInstanceRow(
        id=str(uuid4()), project_id=project_id, environment_id=None, state=state, source="newFromProfile",
        source_content_generation=None, instance_use_generation=1, profile_id=PROFILE, identity_package={},
        identity_id=identity_id, created_at=now, updated_at=now,
    )


@pytest.mark.parametrize("action", ["regenerate_seed", "delete"])
def test_an_identity_in_use_cannot_change_its_seed_or_be_deleted(world, action):
    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号D", template_profile_id=PROFILE)
    held = _reserve(service, factory, project_id, identity.identity_id)
    with pytest.raises(ProjectError) as refused:
        getattr(identities, action)(project_id, identity.identity_id)
    assert refused.value.code == "IDENTITY_IN_USE" and refused.value.status == 409
    service.environments.set_instance_state(held.instance_id, "cleaned")
    getattr(identities, action)(project_id, identity.identity_id)


# --- the claim waits for a busy identity instead of failing -------------------------------------------------------


def _claim_world(world):
    _client, _service, project_id, identities, factory = world
    table, field = _empty_table(factory, project_id, "账号")
    busy_row, free_row = _add_record(factory, project_id, table, field, "a"), _add_record(factory, project_id, table, field, "b")
    busy, free = identities.create(project_id, "忙", template_profile_id=PROFILE), identities.create(project_id, "闲", template_profile_id=PROFILE)
    for record, identity in ((busy_row, busy), (free_row, free)):
        ref = record["ref"]
        with factory() as session:
            session.get(DataRecordRow, (ref["datasetGeneration"], ref["recordKey"]["type"], ref["recordKey"]["value"])).current_identity_id = identity.identity_id
            session.commit()
    plan = {"inputs": [_input(project_id, table, field, "账号")]}
    return project_id, factory, plan, plan["inputs"][0]["inputId"], busy, busy_row, free_row


def _take(factory, project_id, identity_id, state="active"):
    with factory.begin() as session:
        session.add(_row(project_id, identity_id, state))


def test_rows_of_a_busy_identity_wait_and_the_next_free_row_is_taken(world):
    project_id, factory, plan, input_id, busy, busy_row, free_row = _claim_world(world)
    _take(factory, project_id, busy.identity_id)

    def chosen(**options):
        with factory() as session:
            result = SqlAlchemyProjectInputGroups(session).select_required(project_id, plan, **options)
        return result.status, {item.record_ref.record_key.value for item in result.inputs}

    assert chosen(identity_input_id=input_id) == ("ready", {free_row["ref"]["recordKey"]["value"]})
    only_busy = {input_id: [_ref(project_id, plan, busy_row)]}
    assert chosen(identity_input_id=input_id, candidate_restriction=only_busy)[0] == "temporarilyBusy"
    # An automation not running as identities does not look at identity occupancy.
    assert chosen(candidate_restriction=only_busy)[0] == "ready"


def test_when_every_row_is_a_busy_identity_the_batch_waits(world):
    project_id, factory, plan, input_id, busy, _busy_row, free_row = _claim_world(world)
    _take(factory, project_id, busy.identity_id)
    with factory() as session:
        free_identity = session.get(DataRecordRow, (free_row["ref"]["datasetGeneration"], free_row["ref"]["recordKey"]["type"], free_row["ref"]["recordKey"]["value"])).current_identity_id
    _take(factory, project_id, free_identity)
    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(project_id, plan, identity_input_id=input_id)
    assert result.status == "temporarilyBusy"


def test_an_identity_that_becomes_busy_between_prepare_and_commit_is_caught_on_revalidation(world):
    project_id, factory, plan, input_id, busy, busy_row, _free_row = _claim_world(world)
    with factory() as session:
        prepared = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, plan, identity_input_id=input_id,
            candidate_restriction={input_id: [_ref(project_id, plan, busy_row)]},
        )
    assert prepared.status == "ready"
    _take(factory, project_id, busy.identity_id)
    with factory() as session:
        again = SqlAlchemyProjectInputGroups(session).revalidate_selected(project_id, plan, prepared, identity_input_id=input_id)
    assert again.status == "temporarilyBusy"


def _ref(project_id, plan, record):
    from autoflow.domain.project_data.identity import RecordKey
    from autoflow.domain.project_runs.input_selection import RecordRef

    ref = record["ref"]
    return RecordRef(project_id, ref["tableId"], ref["datasetGeneration"], RecordKey(ref["recordKey"]["type"], ref["recordKey"]["value"]))
