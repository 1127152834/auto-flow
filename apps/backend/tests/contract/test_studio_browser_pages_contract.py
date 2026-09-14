import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioBrowserPageCommand,
    StudioBrowserPages,
)


def test_target_can_be_missing_without_selecting_another_page():
    state = StudioBrowserPages.model_validate({
        "sessionId": "browser", "revision": 2, "targetPageId": None,
        "pages": [{"pageId": "remaining", "title": "页面", "url": "about:blank"}],
    })
    assert state.target_page_id is None


@pytest.mark.parametrize("patch", [
    {"targetPageId": "missing"}, {"revision": True}, {"revision": -1},
    {"pages": [{"pageId": "p", "title": "", "url": ""}] * 2},
])
def test_invalid_page_identity_is_rejected(patch):
    with pytest.raises(ValidationError):
        StudioBrowserPages.model_validate({
            "sessionId": "b", "revision": 0, "targetPageId": None, "pages": [], **patch,
        })


@pytest.mark.parametrize("action", ["select", "focus", "navigate"])
def test_page_commands_share_identity_and_revision(action):
    command = StudioBrowserPageCommand.model_validate({
        "sessionId": "b", "pageId": "p", "expectedRevision": 2,
        "action": action, "url": "http://local.test" if action == "navigate" else None,
    })
    assert command.session_id == "b"
    assert command.expected_revision == 2


def test_navigation_requires_an_explicit_url():
    with pytest.raises(ValidationError):
        StudioBrowserPageCommand.model_validate({
            "sessionId": "b", "pageId": "p", "expectedRevision": 2, "action": "navigate",
        })
