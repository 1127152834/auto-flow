from dataclasses import replace
from uuid import uuid4

import pytest

from autoflow.domain.environments.identity import (
    identity_from_request,
    request_from_identity,
)
from autoflow.domain.workflows.runtime import WorkflowRuntimeError
from tests.contract.test_project_environments import PROFILE, _project, make
from tests.unit.test_workflow_browser_resources import resources


def test_identity_is_detached_and_rejects_private_or_inconsistent_fields(tmp_path, valid_profile_values):
    browser, _, profile = resources(tmp_path, valid_profile_values)
    frozen = browser.freeze(profile.id)
    identity = identity_from_request(frozen)
    restored = request_from_identity(identity)
    restored['frozenConfiguration']['profileSpec']['extension_paths'].append('/changed')
    assert identity['frozenConfiguration']['profileSpec']['extension_paths'] == []
    assert frozen['frozenConfiguration']['profileSpec']['extension_paths'] == []
    for invalid in ({**identity, 'password': 'secret'}, {**identity, 'kernelId': 'licensed:unknown'}):
        with pytest.raises(WorkflowRuntimeError) as caught:
            request_from_identity(invalid)
        assert caught.value.code == 'WORKFLOW_RESOURCE_INVALID'
        assert 'secret' not in str(caught.value)
    for invalid in (None, {}, {'schemaVersion': True}, {'schemaVersion': 2}):
        with pytest.raises(WorkflowRuntimeError) as caught:
            request_from_identity(invalid)
        assert caught.value.code == 'ENVIRONMENT_IDENTITY_UNVERIFIED'


def test_save_and_restore_keep_the_instance_identity_with_its_content(tmp_path, valid_profile_values):
    browser, _, profile = resources(tmp_path, valid_profile_values)
    identity = identity_from_request(browser.freeze(profile.id))
    identity['profileId'] = PROFILE
    _, projects, service = make(tmp_path)
    project_id = _project(projects)
    source = replace(service.resolve(project_id, {'source': 'newFromProfile', 'profileId': PROFILE}), identity_package=identity)
    instance = service.reserve(project_id, source, task_id=str(uuid4()), run_id=str(uuid4()), holder_kind='task', holder_id=str(uuid4()))
    identity['frozenConfiguration']['fingerprintSeed'] = 999
    stored = service.get_instance(project_id, instance.instance_id)
    assert stored.identity_package['frozenConfiguration']['fingerprintSeed'] == 42
    (service.instance_path(instance.instance_id) / 'Cookies').write_bytes(b'original-login')
    service.environments.set_instance_state(instance.instance_id, 'closed')
    saved = service.publish_new(project_id, name='独立身份', notes='', profile_id=PROFILE, instance_id=instance.instance_id)
    source = service.resolve(project_id, {'source': 'fixedEnvironment', 'environmentId': saved.ref.environment_id})
    assert source.identity_package['frozenConfiguration']['fingerprintSeed'] == 42
    restored = service.reserve(project_id, source, task_id=str(uuid4()), run_id=str(uuid4()), holder_kind='task', holder_id=str(uuid4()))
    assert (service.instance_path(restored.instance_id) / 'Cookies').read_bytes() == b'original-login'
    assert restored.identity_package == stored.identity_package
    assert 'frozenConfiguration' not in repr(saved.to_dict())


def test_candidate_identity_comes_from_host_and_published_tampering_is_rejected(tmp_path, valid_profile_values):
    import json

    from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore

    browser, _, profile = resources(tmp_path, valid_profile_values)
    identity = identity_from_request(browser.freeze(profile.id))
    store = EnvironmentStore(tmp_path / 'store')
    directory = store.prepare_instance('instance')
    (directory / '.autoflow-identity.json').write_text('{"password":"browser-controlled"}')
    store.stage_candidate('save', 'instance', identity_package=identity)
    store.publish('environment', 1, 'save')
    assert store.generation_identity('environment', 1)['frozenConfiguration']['fingerprintSeed'] == 42
    path = store.generation_dir('environment', 1) / '.autoflow-identity.json'
    changed = json.loads(path.read_text())
    changed['frozenConfiguration']['fingerprintSeed'] = 43
    path.write_text(json.dumps(changed, sort_keys=True, separators=(',', ':')))
    with pytest.raises(WorkflowRuntimeError) as caught:
        store.generation_identity('environment', 1)
    assert caught.value.code == 'ENVIRONMENT_IDENTITY_UNVERIFIED'


def test_reservation_rejects_a_saved_generation_changed_since_resolution(tmp_path):
    from autoflow.domain.projects.models import ProjectError
    from tests.contract.test_project_environments import _closed_instance

    _, projects, service = make(tmp_path)
    project_id = _project(projects)
    instance = _closed_instance(service, project_id, b'login-v1')
    saved = service.publish_new(project_id, name='versioned', notes='', profile_id=PROFILE, instance_id=instance.instance_id)
    selected = service.resolve(project_id, {'source': 'fixedEnvironment', 'environmentId': saved.ref.environment_id})
    (service.instance_path(instance.instance_id) / 'Default' / 'Cookies').write_bytes(b'login-v2')
    service.publish_update(project_id, saved.ref.environment_id, instance.instance_id)
    with pytest.raises(ProjectError) as caught:
        service.reserve(project_id, selected, task_id=str(uuid4()), run_id=str(uuid4()), holder_kind='task', holder_id=str(uuid4()))
    assert caught.value.code == 'SAVE_GENERATION_CONFLICT'
    assert service.get(project_id, saved.ref.environment_id)[1] is None
