import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import StudioModuleRequiredFields

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
