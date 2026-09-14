import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioBrowserScriptContext,
    StudioBrowserScriptRequest,
    StudioBrowserScriptState,
)

CONTEXT = {"browserSessionId": "browser", "pageId": "page", "revision": 0}
REQUEST = {"requestId": "test", "context": CONTEXT, "code": "return document.title", "variables": {"值": [0, False, None]}}
STATE = {"requestId": "test", "context": CONTEXT, "status": "completed", "hasResult": True, "result": None, "error": None, "executionKind": "browser"}


def test_browser_script_wire_roundtrip():
    assert StudioBrowserScriptRequest.model_validate(REQUEST).model_dump(by_alias=True) == REQUEST
    assert StudioBrowserScriptState.model_validate(STATE).model_dump(by_alias=True) == STATE
    context = {**CONTEXT, "url": "about:blank", "activeRequestId": None}
    assert StudioBrowserScriptContext.model_validate(context).model_dump(by_alias=True) == context


@pytest.mark.parametrize("field,value", [("requestId", " "), ("code", ""), ("variables", {"x": float("inf")}), ("variables", []), ("context", {**CONTEXT, "revision": -1}), ("context", {**CONTEXT, "revision": 0.5}), ("context", {**CONTEXT, "pageId": ""})])
def test_browser_script_invalid_request(field, value):
    with pytest.raises(ValidationError):
        StudioBrowserScriptRequest.model_validate({**REQUEST, field: value})


def test_browser_script_rejects_utf8_request_over_limit():
    with pytest.raises(ValidationError):
        StudioBrowserScriptRequest.model_validate({**REQUEST, "code": "中" * 400_000})


@pytest.mark.parametrize("patch", [{"status": "failed"}, {"status": "expired"}, {"status": "running"}, {"hasResult": False, "result": 3}, {"executionKind": "unknown"}, {"error": "wrong success"}])
def test_browser_script_rejects_inconsistent_state(patch):
    with pytest.raises(ValidationError):
        StudioBrowserScriptState.model_validate({**STATE, **patch})


def test_browser_script_error_and_absent_result():
    for status in ["failed", "expired"]:
        result = StudioBrowserScriptState.model_validate({**STATE, "status": status, "hasResult": False, "error": "页面已失效"})
        assert not result.has_result
    assert not StudioBrowserScriptState.model_validate({**STATE, "hasResult": False}).has_result
