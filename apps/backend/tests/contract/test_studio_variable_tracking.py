import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioVariableTrackingCleared,
    StudioVariableTrackingResult,
)

RECORD = {
    "timestamp": "2026-09-14T00:00:00Z", "variable_name": "result", "old_value": None,
    "new_value": {"text": "中文"}, "node_id": "node", "node_name": "脚本",
    "operation": "create", "value_type": "object",
}


def test_tracking_preserves_frozen_wire_names():
    result = StudioVariableTrackingResult(tracking=[RECORD], count=1)
    assert result.model_dump(by_alias=True)["tracking"][0] == RECORD


@pytest.mark.parametrize("payload", [
    {"tracking": [], "count": 1}, {"tracking": [], "count": "0"},
    {"tracking": [dict(RECORD, operation="delete")], "count": 1},
    {"tracking": [dict(RECORD, new_value=float("nan"))], "count": 1},
])
def test_tracking_rejects_invalid_records(payload):
    with pytest.raises(ValidationError):
        StudioVariableTrackingResult.model_validate(payload)


@pytest.mark.parametrize("message", ["", " "])
def test_clear_requires_acknowledgement(message):
    with pytest.raises(ValidationError):
        StudioVariableTrackingCleared(message=message)
