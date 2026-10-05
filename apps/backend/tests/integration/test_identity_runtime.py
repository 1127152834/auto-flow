"""Remediation M4 S4 (R4-03): tasks run as the record's identity — its seed, region and saved login."""

from __future__ import annotations

from uuid import uuid4

import pytest

from autoflow.application.workflows.browser_resources import _with_identity
from autoflow.domain.environments.identity import profile_from_request
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.identities import SqlAlchemyIdentities
from autoflow.infrastructure.database.identity_models import IdentityRow
from tests.contract.test_project_environments import (
    PROFILE,
    _closed_instance,
    _project,
    make,
)

POLICY = {"source": "inputIdentity", "inputId": "accounts"}


def _save(client, project_id, instance_id):
    return client.post(
        f"/api/v1/projects/{project_id}/environment-saves",
        headers={"Idempotency-Key": str(uuid4())},
        json={"instanceId": instance_id, "mode": "saveAs", "expectedUseGeneration": 1, "executionGeneration": 1, "name": "登录环境"},
    ).json()["outcome"]["saved"]


@pytest.fixture
def world(tmp_path):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    factory = service.environments._session_factory
    return client, service, project_id, SqlAlchemyIdentities(factory), factory


def _resolve(service, factory, project_id, identity_id):
    with factory() as session:
        return service.environments.resolve_source_in_session(
            session, project_id, POLICY, {"accounts": {"currentIdentityId": identity_id}},
        )


def test_an_identity_with_a_saved_login_restores_it_and_brings_its_own_seed(world):
    client, service, project_id, identities, factory = world
    instance = _closed_instance(service, project_id, b"login")
    environment_id = _save(client, project_id, instance.instance_id)["environmentId"]
    identity = identities.create(project_id, "账号A", region={"timezone": "Europe/Berlin", "locale": "de-DE"})
    with factory() as session:
        session.get(IdentityRow, identity.identity_id).environment_id = environment_id
        session.commit()
    resolved = _resolve(service, factory, project_id, identity.identity_id)
    assert resolved.environment_ref is not None and resolved.environment_ref.environment_id == environment_id
    assert resolved.identity == {"identityId": identity.identity_id, "seed": identity.seed, "region": {"timezone": "Europe/Berlin", "locale": "de-DE"}}
    # The saved package keeps its old seed; the launched browser takes the identity's.
    profile = _with_identity(profile_from_request({**resolved.identity_package, "profileId": PROFILE}), resolved.identity)
    assert profile.fingerprint_seed == identity.seed
    assert (profile.spec.timezone, profile.spec.locale) == ("Europe/Berlin", "de-DE")


def test_an_identity_without_a_login_starts_from_its_template(world):
    _client, service, project_id, identities, factory = world
    identity = identities.create(project_id, "账号B", template_profile_id=PROFILE)
    resolved = _resolve(service, factory, project_id, identity.identity_id)
    assert resolved.environment_ref is None and resolved.profile_id == PROFILE
    assert resolved.identity["seed"] == identity.seed


def test_a_record_without_an_identity_is_refused_with_a_clear_reason(world):
    _client, service, project_id, _identities, factory = world
    with pytest.raises(ProjectError) as raised:
        _resolve(service, factory, project_id, None)
    assert raised.value.code == "IDENTITY_REQUIRED"


@pytest.mark.parametrize("already_has_login", [False, True])
def test_a_login_saved_for_a_record_goes_to_its_identity_once(world, already_has_login):
    from autoflow.infrastructure.database.project_data_models import DataRecordRow
    from tests.contract.test_project_environments import _account_record

    client, service, project_id, identities, factory = world
    account = _account_record(service, project_id)
    identity = identities.create(project_id, "账号C")
    existing = None
    if already_has_login:
        existing = _save(client, project_id, _closed_instance(service, project_id, b"old").instance_id)["environmentId"]
    with factory() as session:
        session.get(DataRecordRow, (account["datasetGeneration"], "uuid", account["key"])).current_identity_id = identity.identity_id
        session.get(IdentityRow, identity.identity_id).environment_id = existing
        session.commit()
    instance = _closed_instance(service, project_id, b"new-login")
    saved = client.post(
        f"/api/v1/projects/{project_id}/environment-saves",
        headers={"Idempotency-Key": str(uuid4())},
        json={"instanceId": instance.instance_id, "mode": "saveAs", "expectedUseGeneration": 1, "executionGeneration": 1,
              "name": "账号C登录", "recordTargets": [{"recordRef": account["recordRef"], "expectedLinkRevision": 1, "replaceAllowed": False}]},
    ).json()
    new_environment = saved["outcome"]["saved"]["environmentId"]
    with factory() as session:
        linked = session.get(IdentityRow, identity.identity_id).environment_id
    assert linked == (existing if already_has_login else new_environment)
