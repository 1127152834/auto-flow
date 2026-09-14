import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioPickerSessionRequest,
    StudioPickerSessionStartRequest,
    StudioPickerSessionState,
    StudioSelectorTestRequest,
)


def test_picker_start_and_state_roundtrip():
    request = {'sessionId': 'picker', 'url': 'https://example.test', 'browserConfig': {'locale': 'zh-CN'}}
    assert StudioPickerSessionStartRequest.model_validate(request).model_dump(by_alias=True) == request
    state = {'success': True, 'sessionId': 'picker', 'active': True, 'selected': False}
    assert StudioPickerSessionState.model_validate(state).model_dump(by_alias=True) == state
    assert StudioPickerSessionRequest.model_validate({'sessionId': 'picker'}).model_dump(by_alias=True) == {'sessionId': 'picker'}


@pytest.mark.parametrize('patch', [{'sessionId': ''}, {'sessionId': ' '}, {'sessionId': 1}, {'url': False}, {'browserConfig': []}, {'extra': 1}])
def test_picker_start_rejects_invalid_requests(patch):
    with pytest.raises(ValidationError):
        StudioPickerSessionStartRequest.model_validate({'sessionId': 'picker', **patch})


@pytest.mark.parametrize('patch', [{'success': False}, {'sessionId': ''}, {'active': 'true'}, {'selected': 1}, {'selected': None}])
def test_picker_state_is_unambiguous(patch):
    with pytest.raises(ValidationError):
        StudioPickerSessionState.model_validate({'success': True, 'sessionId': 'picker', 'active': True, **patch})


def test_selector_test_retains_optional_session_binding():
    assert StudioSelectorTestRequest.model_validate({'selector': '#target'}).session_id is None
    assert StudioSelectorTestRequest.model_validate({'selector': '#target', 'sessionId': 'picker'}).session_id == 'picker'
    with pytest.raises(ValidationError):
        StudioSelectorTestRequest.model_validate({'selector': '#target', 'sessionId': ' '})
