import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioCommandLookup,
    StudioCommandReceipt,
)
from autoflow.bootstrap.schema_export import export_schema


@pytest.mark.parametrize("success", [True, False])
def test_command_envelopes_preserve_identity_and_specific_result(success):
    payload = {"commandId": "original", "success": success, "details": {"node": "n"}}
    assert StudioCommandReceipt.model_validate(payload).model_dump(by_alias=True) == payload
    lookup = {**payload, "httpStatus": 200 if success else 409}
    assert StudioCommandLookup.model_validate(lookup).model_dump(by_alias=True) == lookup


@pytest.mark.parametrize("payload", [
    {}, {"commandId": "original"}, {"commandId": "", "success": True},
    {"commandId": "   ", "success": True}, {"commandId": 1, "success": True},
    {"commandId": "original", "success": "true"},
    {"commandId": "original", "success": 1}, [], None,
])
def test_command_receipt_rejects_invalid_envelopes(payload):
    with pytest.raises(ValidationError):
        StudioCommandReceipt.model_validate(payload)


@pytest.mark.parametrize("status", [0, 199, 600, 200.5, "200", True, None])
def test_command_lookup_requires_an_integer_http_result(status):
    with pytest.raises(ValidationError):
        StudioCommandLookup.model_validate({"commandId": "original", "success": True, "httpStatus": status})


def test_studio_envelopes_are_available_without_automation_routes():
    schema = export_schema()
    receipt = schema["components"]["schemas"]["StudioCommandReceipt"]
    assert receipt["required"] == ["commandId", "success"]
    assert receipt["additionalProperties"] is True
    assert "httpStatus" in schema["components"]["schemas"]["StudioCommandLookup"]["required"]
    assert not any("/events/commands" in path for path in schema["paths"])
