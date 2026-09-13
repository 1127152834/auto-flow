import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioInputPromptRequest,
    StudioInputPromptResult,
)

PROMPT = {
    "requestId": "input-1",
    "variableName": "answer",
    "title": "输入",
    "message": "请输入",
    "defaultValue": "",
    "inputMode": "single",
}


@pytest.mark.parametrize(
    "mode",
    [
        "single",
        "multiline",
        "number",
        "integer",
        "password",
        "list",
        "file",
        "folder",
        "checkbox",
        "slider_int",
        "slider_float",
        "select_single",
        "select_multiple",
    ],
)
def test_all_frontend_input_modes_are_declared(mode):
    value = StudioInputPromptRequest.model_validate({**PROMPT, "inputMode": mode})
    assert value.input_mode == mode


@pytest.mark.parametrize("value", [0, False, None, "原文"])
def test_request_preserves_source_default_value_types(value):
    parsed = StudioInputPromptRequest.model_validate({**PROMPT, "defaultValue": value})
    assert parsed.default_value == value
    if value is False:
        assert parsed.default_value is False


def test_request_preserves_nullable_constraints_and_rejects_unknown_mode():
    parsed = StudioInputPromptRequest.model_validate(
        {**PROMPT, "minValue": None, "maxValue": None, "selectOptions": None}
    )
    assert parsed.min_value is None and parsed.select_options is None
    with pytest.raises(ValidationError):
        StudioInputPromptRequest.model_validate({**PROMPT, "inputMode": "unknown"})


@pytest.mark.parametrize("value", ["", "原文", None])
def test_result_is_literal_text_or_explicit_cancellation(value):
    assert (
        StudioInputPromptResult.model_validate(
            {"requestId": "input-1", "value": value}
        ).value
        == value
    )


@pytest.mark.parametrize("value", [False, 0, [], {}])
def test_result_rejects_non_wire_value_types(value):
    with pytest.raises(ValidationError):
        StudioInputPromptResult.model_validate({"requestId": "input-1", "value": value})
