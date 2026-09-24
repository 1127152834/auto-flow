import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioRunResultPage,
    StudioRunVariableTrackingPage,
)


def test_result_page_preserves_run_execution_and_typed_values() -> None:
    data = {"runId": "run", "workflowId": "flow", "items": [
        {"sequence": 1, "nodeId": "repeat", "executionId": "iteration-1", "values": {"nested": {"ok": True}}, "largeValues": {"html": "摘要"}},
        {"sequence": 2, "nodeId": "repeat", "executionId": "iteration-2", "values": {"nested": None}},
    ], "total": 200, "throughSequence": 200, "nextCursor": 2}
    result = StudioRunResultPage.model_validate(data).model_dump(by_alias=True)
    assert result["items"][0]["values"]["nested"] == {"ok": True}
    assert result["items"][1]["executionId"] == "iteration-2"


@pytest.mark.parametrize("sequences,total,cutoff", [([2, 1], 2, 2), ([1, 1], 2, 2), ([1, 3], 2, 2), ([1, 2], 1, 2)])
@pytest.mark.parametrize("diagnostic", [False, True])
def test_result_and_diagnostic_pages_reject_order_total_and_cutoff(sequences: list[int], total: int, cutoff: int, diagnostic: bool) -> None:
    if diagnostic:
        rows = [{"sequence": seq, "executionId": "exec", "timestamp": "t", "variable_name": "x", "old_value": None, "new_value": 1,
                 "node_id": "node", "node_name": "节点", "operation": "create", "value_type": "number"} for seq in sequences]
        with pytest.raises(ValidationError):
            StudioRunVariableTrackingPage.model_validate({"runId": "run", "tracking": rows, "total": total, "throughSequence": cutoff})
    else:
        rows = [{"sequence": seq, "nodeId": "node", "executionId": "exec", "values": {}} for seq in sequences]
        with pytest.raises(ValidationError):
            StudioRunResultPage.model_validate({"runId": "run", "workflowId": "flow", "items": rows, "total": total, "throughSequence": cutoff})


def test_diagnostic_page_preserves_source_snake_case_and_new_identity_aliases() -> None:
    page = StudioRunVariableTrackingPage.model_validate({"runId": "run", "total": 1, "throughSequence": 4, "tracking": [
        {"sequence": 4, "executionId": "exec-4", "timestamp": "t", "variable_name": "x", "old_value": None, "new_value": None,
         "node_id": "node", "node_name": "节点", "operation": "update", "value_type": "object", "largeValues": {"new_value": "大对象"}}
    ]}).model_dump(by_alias=True)
    assert page["tracking"][0]["variable_name"] == "x"
    assert page["tracking"][0]["largeValues"] == {"new_value": "大对象"}


def test_diagnostic_page_accepts_loop_scope_exit() -> None:
    page = StudioRunVariableTrackingPage.model_validate(
        {
            "runId": "run",
            "total": 1,
            "throughSequence": 1,
            "tracking": [
                {
                    "sequence": 1,
                    "executionId": "loop-exit",
                    "timestamp": "2026-09-22T00:00:00Z",
                    "variable_name": "item",
                    "old_value": "乙",
                    "new_value": None,
                    "node_id": "repeat",
                    "node_name": "遍历列表",
                    "operation": "scope_exit",
                    "value_type": "null",
                }
            ],
        }
    )

    assert page.tracking[0].operation == "scope_exit"
