import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import StudioBrowserStatus


@pytest.mark.parametrize("is_open", [False, True])
@pytest.mark.parametrize("picker_active", [False, True])
def test_browser_status_preserves_independent_reported_flags(is_open, picker_active):
    value = StudioBrowserStatus.model_validate({"isOpen": is_open, "pickerActive": picker_active})
    assert value.model_dump(by_alias=True) == {
        "isOpen": is_open,
        "pickerActive": picker_active,
        "projectId": None,
        "phase": "closed",
        "sessionId": None,
        "profileId": None,
        "pickerSessionId": None,
    }


@pytest.mark.parametrize("payload", [
    {}, {"isOpen": True}, {"isOpen": "false", "pickerActive": False},
    {"isOpen": False, "pickerActive": 1},
])
def test_invalid_flags_are_rejected(payload):
    with pytest.raises(ValidationError):
        StudioBrowserStatus.model_validate(payload)
