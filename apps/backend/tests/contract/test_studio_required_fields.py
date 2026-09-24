import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import StudioModuleRequiredFields
from autoflow.domain.workflows.scope import APPROVED_NODE_TYPES

FIXTURE = Path(__file__).resolve().parents[4] / 'apps/desktop/src/renderer/domains/workflows/development/module-required-fields.json'
BASE = {'schemaRevision': 'fixture', 'coveredModules': ['demo'], 'requiredFields': {'demo': ['url']}, 'conditionalRequired': {}, 'fieldLabels': {'demo': {'url': '网址'}}}


def test_frozen_metadata_roundtrip():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert StudioModuleRequiredFields.model_validate(data).model_dump(by_alias=True) == data


@pytest.mark.parametrize('patch', [
    {'coveredModules': ['demo', 'demo']}, {'coveredModules': ['']}, {'schemaRevision': ''},
    {'requiredFields': {'foreign': ['url']}}, {'requiredFields': {'demo': ['']}}, {'requiredFields': {'demo': ['url', 'url']}},
    {'fieldLabels': {'demo': {'url': 1}}}, {'fieldLabels': {'demo': {'url': ''}}}, {'success': True},
    {'conditionalRequired': {'demo': {'field': '', 'default': None, 'map': {}}}},
    {'conditionalRequired': {'demo': {'field': 'mode', 'map': {}}}},
    {'conditionalRequired': {'demo': {'field': 'mode', 'default': None, 'map': {'first': ['url', 'url']}}}},
])
def test_invalid_metadata_rejected(patch):
    with pytest.raises(ValidationError):
        StudioModuleRequiredFields.model_validate({**BASE, **patch})


def test_conditional_metadata_and_empty_rules():
    data = {**BASE, 'requiredFields': {}, 'conditionalRequired': {'demo': {'field': 'mode', 'default': 'first', 'map': {'first': ['url'], 'empty': []}}}}
    assert StudioModuleRequiredFields.model_validate(data).model_dump(by_alias=True) == data


def test_production_metadata_route_serves_frozen_rules_and_requires_instance_auth(client):
    response = client.get('/api/system/module-required-fields')
    assert response.status_code == 200
    data = response.json()
    assert data == json.loads(FIXTURE.read_text(encoding='utf-8'))
    assert len(data['coveredModules']) == 213
    assert data['requiredFields']['open_page'] == ['url']
    assert data['fieldLabels']['open_page']['url'] == '要打开的网页 URL'
    assert not {'project_data', 'project_manual', 'project_end'} & set(data['coveredModules'])
    assert client.get('/api/system/module-required-fields', headers={'x-autoflow-token': 'wrong'}).status_code == 401


@pytest.mark.parametrize('content', [None, '{"schemaRevision":"broken"}'])
def test_missing_or_corrupt_packaged_rules_are_not_reported_as_empty(client, tmp_path, monkeypatch, content):
    from autoflow.adapters.http import workflow_metadata

    path = tmp_path / 'rules.json'
    if content is not None:
        path.write_text(content, encoding='utf-8')
    monkeypatch.setattr(workflow_metadata, 'METADATA_PATH', path)
    reader = TestClient(client.app, raise_server_exceptions=False, headers={'x-autoflow-token': 'secret'})
    try:
        assert reader.get('/api/system/module-required-fields').status_code == 500
    finally:
        reader.close()


def test_real_required_fields_route_preserves_frozen_rules_and_approved_scope(client):
    response = client.get('/api/system/module-required-fields')
    assert response.status_code == 200, response.text
    data = response.json()
    assert StudioModuleRequiredFields.model_validate(data).model_dump(by_alias=True) == data
    assert set(data['coveredModules']) == APPROVED_NODE_TYPES
    assert len(data['coveredModules']) == 213
    assert data == json.loads(FIXTURE.read_text(encoding='utf-8'))
    assert data['conditionalRequired']['wait'] == {
        'field': 'waitType', 'default': 'time',
        'map': {'time': [], 'selector': ['selector'], 'navigation': []},
    }
    assert data['requiredFields']['send_email'] == ['recipientEmail', 'emailSubject', 'emailContent']
    # The source has this rule, but the approved Studio scope excludes the node.
    assert 'keyboard_action' not in data['coveredModules']
    assert 'group' not in data['requiredFields'] and 'note' not in data['requiredFields']
    assert 'open_page' in data['fieldLabels']
    assert client.get('/api/system/module-required-fields').json() == data
    assert client.post('/api/system/module-required-fields', json={}).status_code == 405


def test_required_fields_requires_existing_sidecar_authentication(client):
    client.headers.clear()
    response = client.get('/api/system/module-required-fields')
    assert response.status_code == 401
    assert response.json()['error']['code'] == 'SIDECAR_UNAUTHORIZED'


def test_required_fields_has_real_openapi_operation(client):
    schema = client.app.openapi()
    operation = schema['paths']['/api/system/module-required-fields']['get']
    assert operation['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/StudioModuleRequiredFields')
    assert '401' in operation['responses']
