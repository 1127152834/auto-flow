import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioSelectorTestRequest,
    StudioSelectorTestResult,
)


def test_request_defaults_preserve_source_protocol():
    value = StudioSelectorTestRequest.model_validate({"selector": "#target"})
    assert value.highlight is True
    assert value.hints is None


@pytest.mark.parametrize("payload", [
    {"selector": 12}, {"selector": ""}, {"selector": "  "},
    {"selector": "#target", "highlight": "true"},
    {"selector": "#target", "hints": []},
])
def test_invalid_requests_are_rejected(payload):
    with pytest.raises(ValidationError):
        StudioSelectorTestRequest.model_validate(payload)


@pytest.mark.parametrize("count", [0, 1, 4])
def test_zero_one_many_results_roundtrip(count):
    value = StudioSelectorTestResult.model_validate({
        "success": True, "matched": count > 0, "count": count,
        "tried": [{"selector": "#target", "count": count}],
    })
    restored = StudioSelectorTestResult.model_validate(value.model_dump(by_alias=True))
    assert restored == value


@pytest.mark.parametrize("extra", [
    {"count": -1}, {"count": 1.5}, {"count": "1"}, {"count": True},
    {"count": 9007199254740992}, {"count": 0}, {"matched": False},
    {"element": {"text": 123}}, {"tried": "invalid"},
])
def test_invalid_results_are_rejected(extra):
    with pytest.raises(ValidationError):
        StudioSelectorTestResult.model_validate({
            "success": True, "matched": True, "count": 1, **extra,
        })
