import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioExecutionLogPage,
    StudioWorkflowRunPage,
)


def test_execution_log_page_accepts_ordered_camel_case_wire_data() -> None:
    page = StudioExecutionLogPage.model_validate(
        {
            "runId": "run-1",
            "workflowId": "workflow-1",
            "items": [
                {"sequence": 9, "id": "log-9", "timestamp": "2026-09-14T00:00:00Z", "level": "info", "message": "开始"},
                {"sequence": 10, "id": "log-10", "timestamp": "2026-09-14T00:00:01Z", "level": "success", "message": "完成", "nodeId": "node-1", "duration": 12.5},
            ],
            "total": 10,
            "nextCursor": 2,
        }
    )

    assert page.model_dump(by_alias=True)["items"][1]["nodeId"] == "node-1"


@pytest.mark.parametrize(
    "items,total",
    [
        ([{"sequence": 2, "id": "b", "timestamp": "t", "level": "info", "message": "b"}, {"sequence": 1, "id": "a", "timestamp": "t", "level": "info", "message": "a"}], 2),
        ([{"sequence": 1, "id": "a", "timestamp": "t", "level": "info", "message": "a"}], 0),
    ],
)
def test_execution_log_page_rejects_invalid_order_or_total(items: list[dict], total: int) -> None:
    with pytest.raises(ValidationError):
        StudioExecutionLogPage.model_validate({"runId": "run", "workflowId": "workflow", "items": items, "total": total, "nextCursor": None})


def test_run_history_requires_independent_run_identity() -> None:
    page = StudioWorkflowRunPage.model_validate(
        {
            "items": [
                {
                    "runId": "run-2",
                    "workflowId": "workflow-1",
                    "documentId": "document-1",
                    "workflowName": "登录流程",
                    "status": "completed",
                    "startedAt": "2026-09-14T00:00:00Z",
                    "finishedAt": "2026-09-14T00:00:01Z",
                    "logCount": 10,
                }
            ],
            "total": 1,
            "nextCursor": None,
        }
    )

    assert page.items[0].run_id == "run-2"
    assert page.items[0].workflow_id == "workflow-1"
