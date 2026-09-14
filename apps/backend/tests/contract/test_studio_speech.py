import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioSpeechRequest,
    StudioSpeechResult,
    StudioSpeechState,
)

REQUEST = {"requestId": "request", "workflowId": "flow", "nodeId": "node",
           "text": "通知", "lang": "zh-CN", "rate": 1, "pitch": 1, "volume": 0}


def test_speech_zero_volume_and_wire_names():
    assert StudioSpeechRequest.model_validate(REQUEST).model_dump(by_alias=True) == REQUEST


@pytest.mark.parametrize("field,value", [
    ("requestId", " "), ("text", ""), ("lang", ""), ("rate", 0),
    ("pitch", 3), ("volume", -1), ("volume", "0"), ("rate", float("inf")),
])
def test_speech_invalid_request(field, value):
    with pytest.raises(ValidationError):
        StudioSpeechRequest.model_validate({**REQUEST, field: value})


def test_speech_failure_requires_error():
    with pytest.raises(ValidationError):
        StudioSpeechResult(requestId="request", claimId="claim", success=False)
    assert StudioSpeechResult(requestId="request", claimId="claim", success=True).success


def test_claimed_speech_requires_owner():
    with pytest.raises(ValidationError):
        StudioSpeechState(requestId="request", workflowId="flow", nodeId="node", status="claimed")
