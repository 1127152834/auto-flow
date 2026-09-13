import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import StudioJsScriptResult


def test_success_requires_variables_and_preserves_json() -> None:
    value = StudioJsScriptResult.model_validate({"requestId": "r", "claimId": "c", "success": True, "result": [1, None], "variables": {"count": 2}})
    assert value.result == [1, None]
    assert value.variables == {"count": 2}


@pytest.mark.parametrize("data", [{"success": True}, {"success": False}, {"success": "true", "variables": {}}, {"success": True, "variables": {"bad": float("nan")}}, {"success": True, "variables": {}, "result": float("inf")}])
def test_rejects_invalid_results(data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        StudioJsScriptResult.model_validate({"requestId": "r", "claimId": "c", **data})


def test_claimed_state_requires_owner() -> None:
    from autoflow.adapters.http.workflow_studio_schemas import StudioJsScriptState

    with pytest.raises(ValidationError):
        StudioJsScriptState.model_validate({"requestId": "r", "workflowId": "w", "nodeId": "n", "status": "claimed"})


def test_empty_failure_message_is_rejected() -> None:
    with pytest.raises(ValidationError):
        StudioJsScriptResult.model_validate({"requestId": "r", "claimId": "c", "success": False, "error": "   "})
